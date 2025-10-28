"""
Summary Revision Tool Routes.

Handles text input, AI-powered revision, and results display.
Per FR-007: AI-powered content revision using OpenAI GPT-4.
"""

import logging
import uuid
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.services.summary_revision.revision_service import get_revision_service, RevisionService
from app.concurrency_manager import get_openai_queue

logger = logging.getLogger(__name__)

# Create blueprint
summary_revision_bp = Blueprint('summary_revision', __name__, url_prefix='/tools/summary-revision')

# Allowed file extensions for text upload
ALLOWED_EXTENSIONS = {'txt', 'md', 'text'}

# Store results temporarily
_results_cache = {}


def allowed_file(filename: str) -> bool:
    """Check if filename has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@summary_revision_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display summary revision tool input form.

    Returns:
        Rendered summary revision template
    """
    logger.info(f"User {current_user.id} accessed summary revision tool")

    # Get available models
    available_models = RevisionService.AVAILABLE_MODELS

    return render_template(
        'tools/summary_revision.html',
        available_models=available_models
    )


@summary_revision_bp.route('/revise', methods=['POST'])
@login_required
def revise():
    """
    Process text revision request.

    Accepts text input and revision options,
    performs AI revision, and redirects to results page.

    Returns:
        Redirect to results page or error response
    """
    try:
        # Get text input
        text_input = request.form.get('text_input', '').strip()

        # Validate input
        if not text_input:
            flash('Please provide text to revise.', 'danger')
            return redirect(url_for('summary_revision.index'))

        # Get revision options
        model_name = request.form.get('model_name', 'gpt-4.1')
        use_canadian_english = request.form.get('use_canadian_english') == 'on'

        # Validate model
        if model_name not in RevisionService.AVAILABLE_MODELS:
            flash(f'Invalid model: {model_name}', 'danger')
            return redirect(url_for('summary_revision.index'))

        logger.info(
            f"Revision request: model={model_name}, canadian={use_canadian_english}, "
            f"length={len(text_input)}"
        )

        # Get revision service
        service = get_revision_service()

        # Check if OpenAI queue is enabled
        queue = get_openai_queue()

        if queue.enabled:
            # Use queue for rate limiting
            request_id = f"revision_{uuid.uuid4()}"

            # Create result entry immediately
            result_id = str(uuid.uuid4())
            _results_cache[result_id] = {
                'status': 'processing',
                'revision_result': None,
                'comparison': None,
                'highlighted_text': None,
                'markdown_text': None,
                'options': {
                    'model_name': model_name,
                    'use_canadian_english': use_canadian_english
                }
            }

            # Queue the revision request
            def process_revision():
                """Callback to process revision."""
                result = service.revise_text(
                    text_input,
                    model_name,
                    use_canadian_english
                )

                # Get comparison and highlighting if successful
                comparison = None
                highlighted_text = None
                markdown_text = None
                if result['success']:
                    comparison = service.compare_texts(
                        result['original_text'],
                        result['revised_text']
                    )
                    highlighted_text = service.highlight_changes(
                        result['original_text'],
                        result['revised_text']
                    )
                    markdown_text = service.convert_to_markdown(
                        result['revised_text']
                    )

                # Update cache
                _results_cache[result_id]['status'] = 'completed'
                _results_cache[result_id]['revision_result'] = result
                _results_cache[result_id]['comparison'] = comparison
                _results_cache[result_id]['highlighted_text'] = highlighted_text
                _results_cache[result_id]['markdown_text'] = markdown_text

            queue.enqueue(
                request_id,
                process_revision
            )

            logger.info(f"Queued revision request: {request_id} -> result_id: {result_id}")
            flash('Your revision request has been queued. Processing...', 'info')

        else:
            # Process immediately
            result = service.revise_text(
                text_input,
                model_name,
                use_canadian_english
            )

            # Get comparison and highlighting if successful
            comparison = None
            highlighted_text = None
            markdown_text = None
            if result['success']:
                comparison = service.compare_texts(
                    result['original_text'],
                    result['revised_text']
                )
                highlighted_text = service.highlight_changes(
                    result['original_text'],
                    result['revised_text']
                )
                markdown_text = service.convert_to_markdown(
                    result['revised_text']
                )

            # Store results
            result_id = str(uuid.uuid4())
            _results_cache[result_id] = {
                'status': 'completed',
                'revision_result': result,
                'comparison': comparison,
                'highlighted_text': highlighted_text,
                'markdown_text': markdown_text,
                'options': {
                    'model_name': model_name,
                    'use_canadian_english': use_canadian_english
                }
            }

            logger.info(f"Revision complete. Result ID: {result_id}")

            if result['success']:
                flash('Text revision completed successfully!', 'success')
            else:
                flash(f'Revision failed: {result.get("error", "Unknown error")}', 'danger')

        return redirect(url_for('summary_revision.results', result_id=result_id))

    except Exception as e:
        logger.error(f"Error processing revision: {e}", exc_info=True)
        flash('An error occurred while processing your request. Please try again.', 'danger')
        return redirect(url_for('summary_revision.index'))


@summary_revision_bp.route('/results/<result_id>')
@login_required
def results(result_id: str):
    """
    Display revision results with side-by-side comparison.

    Args:
        result_id: Unique identifier for results

    Returns:
        Rendered results template
    """
    # Get results from cache
    results_data = _results_cache.get(result_id)

    if not results_data:
        flash('Results not found or expired. Please submit a new revision request.', 'warning')
        return redirect(url_for('summary_revision.index'))

    logger.info(f"User {current_user.id} viewing results {result_id}")

    return render_template(
        'tools/summary_revision_results.html',
        results=results_data,
        result_id=result_id,
        available_models=RevisionService.AVAILABLE_MODELS
    )


@summary_revision_bp.route('/api/status/<result_id>')
@login_required
def get_status(result_id: str):
    """
    Get processing status for queued revision.

    Args:
        result_id: Unique identifier for results

    Returns:
        JSON response with status
    """
    results_data = _results_cache.get(result_id)

    if not results_data:
        return jsonify({'error': 'Results not found'}), 404

    return jsonify({
        'result_id': result_id,
        'status': results_data['status'],
        'completed': results_data['status'] == 'completed'
    })


@summary_revision_bp.route('/api/download/<result_id>')
@login_required
def download_revised(result_id: str):
    """
    Download revised text as a file.

    Args:
        result_id: Unique identifier for results

    Returns:
        Text file download
    """
    results_data = _results_cache.get(result_id)

    if not results_data:
        flash('Results not found or expired.', 'warning')
        return redirect(url_for('summary_revision.index'))

    result = results_data.get('revision_result')

    if not result or not result['success']:
        flash('No revised text available to download.', 'warning')
        return redirect(url_for('summary_revision.results', result_id=result_id))

    from flask import Response

    # Create file response
    revised_text = result['revised_text']

    response = Response(
        revised_text,
        mimetype='text/plain',
        headers={
            'Content-Disposition': 'attachment; filename=revised_text.txt'
        }
    )

    logger.info(f"User {current_user.id} downloaded revised text from {result_id}")

    return response
