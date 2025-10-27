"""
DR Knowledge Chatbot Routes.

Modern RAG implementation with rate limiting and upload support.
Per chatbot_revised.md: 20 q/m rate limiting, all users can upload.
"""

import logging
import uuid
from flask import Blueprint, render_template, request, jsonify, session
from flask_login import login_required, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename

from app.services.chatbot.chatbot_service import get_chatbot_service
from app.concurrency_manager import get_openai_queue

logger = logging.getLogger(__name__)

# Initialize rate limiter
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"]
)

# Create blueprint
chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/tools/chatbot')


def get_user_chat_history():
    """Get current user's chat history from session."""
    if 'chatbot_history' not in session:
        session['chatbot_history'] = []
    return session['chatbot_history']


def add_to_chat_history(role: str, content: str):
    """Add message to current user's chat history."""
    history = get_user_chat_history()
    history.append({'role': role, 'content': content})

    # Limit history to last 20 messages
    if len(history) > 20:
        history = history[-20:]

    session['chatbot_history'] = history
    session.modified = True


@chatbot_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display chatbot interface.

    Returns:
        Rendered chatbot template
    """
    logger.info(f"User {current_user.id} accessed chatbot")

    # Get service stats
    try:
        service = get_chatbot_service()
        logger.info(f"Service type: {type(service)}")
        stats = service.get_stats()
        logger.info(f"Stats retrieved: {stats}")
    except Exception as e:
        logger.error(f"Error getting stats: {e}", exc_info=True)
        # Provide default stats if error
        stats = {
            'loaded': False,
            'document_count': 0,
            'chunk_count': 0,
            'model_loaded': False,
            'model_name': None,
            'embedding_dimension': None,
            'last_update': None
        }

    # Get chat history
    history = get_user_chat_history()

    return render_template(
        'tools/chatbot.html',
        stats=stats,
        history=history
    )


@chatbot_bp.route('/send', methods=['POST'])
@login_required
@limiter.limit("20/minute")  # 20 queries per minute rate limit
def send_message():
    """
    Process chat message and return AI response.

    Accepts JSON with 'message' field.

    Returns:
        JSON response with AI reply and context
    """
    try:
        # Get message from request
        data = request.get_json()

        if not data or 'message' not in data:
            return jsonify({'error': 'No message provided'}), 400

        message = data['message'].strip()

        if not message:
            return jsonify({'error': 'Empty message'}), 400

        if len(message) > 1000:
            return jsonify({'error': 'Message too long (max 1000 characters)'}), 400

        logger.info(f"Chat message from {current_user.id}: '{message[:50]}...'")

        # Get service
        service = get_chatbot_service()

        # Check if knowledge base is loaded
        if not service.knowledge_base is None:
            stats = service.get_stats()
            if not stats['loaded']:
                return jsonify({
                    'error': 'Knowledge base not loaded. Please contact administrator.'
                }), 503

        # Get chat history
        history = get_user_chat_history()

        # Check if OpenAI queue is enabled
        queue = get_openai_queue()

        if queue.enabled:
            # Use queue (but still process synchronously for chat)
            # The queue is mainly for rate limiting, not async processing
            request_id = f"chatbot_{uuid.uuid4()}"

            result_holder = {}

            def process_chat():
                """Callback to process chat."""
                result = service.chat(message, history, include_context=True)
                result_holder['result'] = result

            # Enqueue and wait for result (synchronous for better UX)
            # Increased timeout to 90s for complex queries that require analysis
            queue_request = queue.enqueue(request_id, process_chat)
            queue.wait_for_request(request_id, timeout=90)

            result = result_holder.get('result')

            if not result:
                return jsonify({'error': 'Chat processing timeout'}), 504

        else:
            # Process immediately
            result = service.chat(message, history, include_context=True)

        if not result['success']:
            return jsonify({'error': result.get('error', 'Chat failed')}), 500

        # Add to chat history
        add_to_chat_history('user', message)
        add_to_chat_history('assistant', result['response'])

        # Format context for response
        context_summary = []
        if result['context_used']:
            for ctx in result['context_used']:
                context_summary.append({
                    'score': round(ctx['score'], 3),
                    'preview': ctx['text'][:200] + '...' if len(ctx['text']) > 200 else ctx['text']
                })

        response_data = {
            'response': result['response'],
            'context': context_summary,
            'processing_time': round(result['processing_time'], 2)
        }

        logger.info(f"Chat response sent (time: {result['processing_time']:.2f}s)")

        return jsonify(response_data)

    except Exception as e:
        logger.error(f"Error processing chat message: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred processing your message'}), 500


@chatbot_bp.route('/clear', methods=['POST'])
@login_required
def clear_history():
    """
    Clear chat history for current user.

    Returns:
        JSON response confirming clear
    """
    session['chatbot_history'] = []
    session.modified = True

    logger.info(f"Chat history cleared for {current_user.id}")

    return jsonify({'success': True, 'message': 'Chat history cleared'})


@chatbot_bp.route('/stats', methods=['GET'])
@login_required
def get_stats():
    """
    Get chatbot statistics.

    Returns:
        JSON response with knowledge base stats
    """
    service = get_chatbot_service()
    stats = service.get_stats()

    return jsonify(stats)


@chatbot_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    """
    Get chat history for current user.

    Returns:
        JSON response with chat history
    """
    history = get_user_chat_history()

    return jsonify({
        'history': history,
        'count': len(history)
    })


@chatbot_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    """
    Upload new Excel database file.

    GET: Show upload interface
    POST: Process uploaded file

    Returns:
        GET: Rendered upload template
        POST: JSON response with upload result
    """
    if request.method == 'GET':
        # Get upload history
        service = get_chatbot_service()
        upload_history = service.update_service.get_upload_history(limit=10)

        return render_template(
            'tools/chatbot_upload.html',
            upload_history=upload_history
        )

    # POST - process upload
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400

        # Validate file extension
        if not file.filename.endswith('.xlsx'):
            return jsonify({'error': 'Only .xlsx files are allowed'}), 400

        logger.info(f"User {current_user.id} uploading file: {file.filename}")

        # Process upload
        service = get_chatbot_service()
        logger.info("Starting upload processing...")
        result = service.update_service.process_upload(
            excel_file=file,
            uploaded_by=str(current_user.id)
        )
        logger.info(f"Upload processing completed. Success: {result.success}, Message: {result.message}")

        if result.success:
            logger.info(f"Upload successful: {result.version_id}, changes: {result.changes}")
            return jsonify({
                'success': True,
                'message': result.message,
                'version_id': result.version_id,
                'changes': result.changes
            })
        else:
            logger.error(f"Upload failed: {result.error}")
            return jsonify({
                'success': False,
                'error': result.error
            }), 500

    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@chatbot_bp.route('/update-history', methods=['GET'])
@login_required
def update_history():
    """
    Get database update history.

    Returns:
        JSON response with update history
    """
    try:
        service = get_chatbot_service()
        history = service.update_service.get_upload_history(limit=20)

        return jsonify({
            'success': True,
            'history': history,
            'count': len(history)
        })

    except Exception as e:
        logger.error(f"Error getting update history: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@chatbot_bp.route('/database-stats', methods=['GET'])
@login_required
def database_stats():
    """
    Get detailed database statistics.

    Returns:
        JSON response with statistics
    """
    try:
        service = get_chatbot_service()
        stats = service.get_stats()

        # Get metadata stats
        metadata_stats = service.metadata_service.get_statistics()

        combined_stats = {
            **stats,
            'date_range': metadata_stats.get('date_range', {}),
            'top_hazards': metadata_stats.get('top_hazards', []),
            'top_locations': metadata_stats.get('top_locations', [])
        }

        return jsonify(combined_stats)

    except Exception as e:
        logger.error(f"Error getting database stats: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500
