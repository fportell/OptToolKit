"""
DR-Tracker Builder Tool Routes.

Complete rebuild for Daily Report (health surveillance) processing.
Replaces Discrepancy Report functionality.
"""

import logging
import uuid
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, Response
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.services.dr_tracker import get_tracker_service

logger = logging.getLogger(__name__)

# Create blueprint
dr_tracker_bp = Blueprint('dr_tracker', __name__, url_prefix='/tools/dr-tracker')

# Session-based cache for entries (in-memory)
# Key: session_id, Value: {entries, metadata, timestamp}
_session_cache = {}

# Session timeout: 2 hours
SESSION_TIMEOUT = timedelta(hours=2)


def cleanup_expired_sessions():
    """Remove expired sessions from cache."""
    now = datetime.utcnow()
    expired = [
        sid for sid, data in _session_cache.items()
        if now - data['timestamp'] > SESSION_TIMEOUT
    ]
    for sid in expired:
        del _session_cache[sid]
        logger.info(f"Cleaned up expired session: {sid}")


@dr_tracker_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display HTML file upload page.

    Returns:
        Rendered DR-Tracker upload template
    """
    logger.info(f"User {current_user.id} accessed DR-Tracker tool")

    # Cleanup expired sessions
    cleanup_expired_sessions()

    return render_template('tools/dr_tracker.html')


@dr_tracker_bp.route('/process', methods=['POST'])
@login_required
def process():
    """
    Process uploaded HTML file.

    Accepts HTML file upload, sanitizes, extracts with OpenAI,
    matches hazards, and creates session.

    Returns:
        JSON response with session_id or error
    """
    try:
        # Validate file upload
        if 'html_file' not in request.files:
            return jsonify({'success': False, 'error': 'No file uploaded'}), 400

        file = request.files['html_file']

        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        # Validate file extension
        filename = secure_filename(file.filename)
        if not filename.lower().endswith(('.html', '.htm')):
            return jsonify({'success': False, 'error': 'Invalid file type. Please upload .html or .htm file'}), 400

        # Read file bytes
        file_bytes = file.read()

        # Validate file size (5MB max)
        max_size = current_app.config.get('DR_TRACKER_MAX_FILE_SIZE', 5 * 1024 * 1024)
        if len(file_bytes) > max_size:
            return jsonify({
                'success': False,
                'error': f'File too large. Maximum size is {max_size / (1024 * 1024):.1f}MB'
            }), 400

        logger.info(f"Processing HTML file: {filename} ({len(file_bytes)} bytes)")

        # Get timeout configuration
        timeout = current_app.config.get('DR_TRACKER_TIMEOUT', 120)

        # Get service and process
        service = get_tracker_service()
        result = service.process_html_upload(file_bytes, timeout)

        if not result.success:
            logger.error(f"Processing failed: {result.error}")
            return jsonify({
                'success': False,
                'error': result.error or 'Processing failed'
            }), 500

        # Create session
        session_id = str(uuid.uuid4())
        _session_cache[session_id] = {
            'entries': [entry.to_dict() for entry in result.entries],
            'metadata': result.metadata,
            'timestamp': datetime.utcnow(),
            'filename': filename,
            'original_file': file_bytes  # Store original file for viewing
        }

        logger.info(f"Session created: {session_id} with {len(result.entries)} entries")

        return jsonify({
            'success': True,
            'session_id': session_id,
            'entry_count': len(result.entries),
            'processing_time': result.metadata.get('processing_time', 0)
        })

    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': f'An error occurred: {str(e)}'
        }), 500


@dr_tracker_bp.route('/edit/<session_id>')
@login_required
def edit(session_id: str):
    """
    Display editable table for entries.

    Args:
        session_id: Unique session identifier

    Returns:
        Rendered editor template
    """
    # Check session exists
    if session_id not in _session_cache:
        flash('Session expired or not found. Please upload the file again.', 'warning')
        return redirect(url_for('dr_tracker.index'))

    # Check session not expired
    session_data = _session_cache[session_id]
    if datetime.utcnow() - session_data['timestamp'] > SESSION_TIMEOUT:
        del _session_cache[session_id]
        flash('Session expired. Please upload the file again.', 'warning')
        return redirect(url_for('dr_tracker.index'))

    logger.info(f"User {current_user.id} viewing editor for session {session_id}")

    # Get service to load reference data
    service = get_tracker_service()

    return render_template(
        'tools/dr_tracker_editor.html',
        entries=session_data['entries'],
        hazards=service.load_hazards(),
        program_areas=service.load_program_areas(),
        session_id=session_id,
        metadata=session_data['metadata'],
        filename=session_data.get('filename', 'Unknown')
    )


@dr_tracker_bp.route('/api/update/<session_id>', methods=['POST'])
@login_required
def update_entry(session_id: str):
    """
    Update a single entry in the session.

    Args:
        session_id: Unique session identifier

    Request JSON:
        {
            "index": int,
            "entry": {...updated entry data...}
        }

    Returns:
        JSON response with success status
    """
    try:
        # Validate session
        if session_id not in _session_cache:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Get request data
        data = request.json
        entry_index = data.get('index')
        updated_entry = data.get('entry')

        if entry_index is None or updated_entry is None:
            return jsonify({'success': False, 'error': 'Invalid request data'}), 400

        # Validate index
        session_data = _session_cache[session_id]
        if entry_index < 0 or entry_index >= len(session_data['entries']):
            return jsonify({'success': False, 'error': 'Invalid entry index'}), 400

        # Update entry
        session_data['entries'][entry_index] = updated_entry
        session_data['timestamp'] = datetime.utcnow()  # Refresh session

        logger.info(f"Updated entry {entry_index} in session {session_id}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error updating entry: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@dr_tracker_bp.route('/api/update-all/<session_id>', methods=['POST'])
@login_required
def update_all_entries(session_id: str):
    """
    Update all entries in the session at once.

    Useful for batch updates from the editor.

    Args:
        session_id: Unique session identifier

    Request JSON:
        {
            "entries": [...all entries...]
        }

    Returns:
        JSON response with success status
    """
    try:
        # Validate session
        if session_id not in _session_cache:
            return jsonify({'success': False, 'error': 'Session not found'}), 404

        # Get request data
        data = request.json
        updated_entries = data.get('entries')

        if not updated_entries or not isinstance(updated_entries, list):
            return jsonify({'success': False, 'error': 'Invalid entries data'}), 400

        # Update all entries
        session_data = _session_cache[session_id]
        session_data['entries'] = updated_entries
        session_data['timestamp'] = datetime.utcnow()  # Refresh session

        logger.info(f"Updated all {len(updated_entries)} entries in session {session_id}")

        return jsonify({'success': True, 'count': len(updated_entries)})

    except Exception as e:
        logger.error(f"Error updating all entries: {e}", exc_info=True)
        return jsonify({'success': False, 'error': str(e)}), 500


@dr_tracker_bp.route('/download/<session_id>')
@login_required
def download(session_id: str):
    """
    Download Excel file with macros (.xlsm).

    Generates two-sheet Excel workbook with VBA macros embedded.

    Args:
        session_id: Unique session identifier

    Returns:
        Excel file download response
    """
    try:
        # Validate session
        if session_id not in _session_cache:
            flash('Session expired or not found.', 'warning')
            return redirect(url_for('dr_tracker.index'))

        session_data = _session_cache[session_id]

        logger.info(f"User {current_user.id} downloading Excel for session {session_id}")

        # Get service
        service = get_tracker_service()

        # Convert dict entries back to DREntry objects
        from app.services.dr_tracker.models import DREntry
        entries = [DREntry.from_dict(e) for e in session_data['entries']]

        # Generate Excel
        excel_bytes = service.export_to_excel_with_macros(entries)

        # Generate filename with timestamp
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f'dr_tracker_{timestamp}.xlsm'

        logger.info(f"Generated Excel file: {filename} ({len(excel_bytes)} bytes)")

        return Response(
            excel_bytes,
            mimetype='application/vnd.ms-excel.sheet.macroEnabled.12',
            headers={
                'Content-Disposition': f'attachment; filename={filename}'
            }
        )

    except Exception as e:
        logger.error(f"Error generating Excel: {e}", exc_info=True)
        flash(f'Error generating Excel file: {str(e)}', 'danger')
        return redirect(url_for('dr_tracker.edit', session_id=session_id))


@dr_tracker_bp.route('/api/session/<session_id>/status')
@login_required
def session_status(session_id: str):
    """
    Get session status and metadata.

    Args:
        session_id: Unique session identifier

    Returns:
        JSON response with session info
    """
    if session_id not in _session_cache:
        return jsonify({'exists': False}), 404

    session_data = _session_cache[session_id]

    # Check if expired
    age = datetime.utcnow() - session_data['timestamp']
    is_expired = age > SESSION_TIMEOUT

    return jsonify({
        'exists': True,
        'expired': is_expired,
        'entry_count': len(session_data['entries']),
        'age_seconds': age.total_seconds(),
        'metadata': session_data['metadata']
    })


@dr_tracker_bp.route('/api/session/<session_id>', methods=['DELETE'])
@login_required
def delete_session(session_id: str):
    """
    Delete a session manually.

    Args:
        session_id: Unique session identifier

    Returns:
        JSON response with success status
    """
    if session_id in _session_cache:
        del _session_cache[session_id]
        logger.info(f"Session deleted: {session_id}")
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Session not found'}), 404


@dr_tracker_bp.route('/view-source/<session_id>')
@login_required
def view_source(session_id: str):
    """
    View original HTML source file for a session.

    Args:
        session_id: Unique session identifier

    Returns:
        HTML file response
    """
    # Validate session
    if session_id not in _session_cache:
        flash('Session expired or not found.', 'warning')
        return redirect(url_for('dr_tracker.index'))

    session_data = _session_cache[session_id]

    # Check if original file exists in session
    if 'original_file' not in session_data:
        flash('Original file not available for this session.', 'warning')
        return redirect(url_for('dr_tracker.edit', session_id=session_id))

    logger.info(f"User {current_user.id} viewing source for session {session_id}")

    # Serve the original HTML file
    return Response(
        session_data['original_file'],
        mimetype='text/html',
        headers={
            'Content-Disposition': f'inline; filename={session_data["filename"]}'
        }
    )
