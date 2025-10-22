"""
DR-Tracker Builder Tool Routes.

Handles prompt input, DR generation, and export functionality.
Per FR-008: Generate structured DR-Tracker reports from text prompts.
"""

import logging
import uuid
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, Response
from flask_login import login_required, current_user

from app.services.dr_tracker.tracker_service import get_tracker_service
from app.concurrency_manager import get_openai_queue

logger = logging.getLogger(__name__)

# Create blueprint
dr_tracker_bp = Blueprint('dr_tracker', __name__, url_prefix='/tools/dr-tracker')

# Store results temporarily
_results_cache = {}


@dr_tracker_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display DR-Tracker builder input form.

    Returns:
        Rendered DR-Tracker template
    """
    logger.info(f"User {current_user.id} accessed DR-Tracker tool")
    return render_template('tools/dr_tracker.html')


@dr_tracker_bp.route('/generate', methods=['POST'])
@login_required
def generate():
    """
    Process DR generation request.

    Accepts text prompt, generates structured DR entries using AI,
    and redirects to results page.

    Returns:
        Redirect to results page or error response
    """
    try:
        # Get prompt input
        prompt = request.form.get('prompt', '').strip()

        # Validate input
        if not prompt:
            flash('Please provide a description of the DR entries to generate.', 'danger')
            return redirect(url_for('dr_tracker.index'))

        if len(prompt) > 10000:
            flash('Prompt is too long. Maximum 10,000 characters allowed.', 'danger')
            return redirect(url_for('dr_tracker.index'))

        # Get timeout configuration
        timeout = current_app.config.get('DR_TRACKER_TIMEOUT_SECONDS', 120)

        logger.info(f"DR generation request (length: {len(prompt)}, timeout: {timeout}s)")

        # Get service
        service = get_tracker_service()

        # Check if OpenAI queue is enabled
        queue = get_openai_queue()

        if queue.enabled:
            # Use queue for rate limiting
            request_id = f"dr_tracker_{uuid.uuid4()}"

            # Create result entry immediately
            result_id = str(uuid.uuid4())
            _results_cache[result_id] = {
                'status': 'processing',
                'generation_result': None,
                'validation': None
            }

            # Queue the generation request
            def process_generation():
                """Callback to process DR generation."""
                result = service.generate_from_prompt(prompt, timeout)

                # Validate entries if successful
                validation = None
                if result['success'] and result['entries']:
                    validation = service.validate_entries(result['entries'])

                # Update cache
                _results_cache[result_id]['status'] = 'completed'
                _results_cache[result_id]['generation_result'] = result
                _results_cache[result_id]['validation'] = validation

            queue.enqueue(request_id, process_generation)

            logger.info(f"Queued DR generation: {request_id} -> result_id: {result_id}")
            flash('Your DR generation request has been queued. Processing...', 'info')

        else:
            # Process immediately
            result = service.generate_from_prompt(prompt, timeout)

            # Validate entries if successful
            validation = None
            if result['success'] and result['entries']:
                validation = service.validate_entries(result['entries'])

            # Store results
            result_id = str(uuid.uuid4())
            _results_cache[result_id] = {
                'status': 'completed',
                'generation_result': result,
                'validation': validation
            }

            logger.info(f"DR generation complete. Result ID: {result_id}")

            if result['success']:
                flash(f'Successfully generated {result["count"]} DR entries!', 'success')
            else:
                flash(f'Generation failed: {result.get("error", "Unknown error")}', 'danger')

        return redirect(url_for('dr_tracker.results', result_id=result_id))

    except Exception as e:
        logger.error(f"Error processing generation: {e}", exc_info=True)
        flash('An error occurred while processing your request. Please try again.', 'danger')
        return redirect(url_for('dr_tracker.index'))


@dr_tracker_bp.route('/results/<result_id>')
@login_required
def results(result_id: str):
    """
    Display generation results with preview and export options.

    Args:
        result_id: Unique identifier for results

    Returns:
        Rendered results template
    """
    # Get results from cache
    results_data = _results_cache.get(result_id)

    if not results_data:
        flash('Results not found or expired. Please submit a new generation request.', 'warning')
        return redirect(url_for('dr_tracker.index'))

    logger.info(f"User {current_user.id} viewing results {result_id}")

    return render_template(
        'tools/dr_tracker_results.html',
        results=results_data,
        result_id=result_id
    )


@dr_tracker_bp.route('/api/status/<result_id>')
@login_required
def get_status(result_id: str):
    """
    Get processing status for queued generation.

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


@dr_tracker_bp.route('/download/<result_id>/<format>')
@login_required
def download(result_id: str, format: str):
    """
    Download DR entries in specified format.

    Args:
        result_id: Unique identifier for results
        format: Export format (csv, json, xlsx)

    Returns:
        File download response
    """
    # Validate format
    if format not in ['csv', 'json', 'xlsx']:
        flash('Invalid export format', 'danger')
        return redirect(url_for('dr_tracker.results', result_id=result_id))

    # Get results
    results_data = _results_cache.get(result_id)

    if not results_data:
        flash('Results not found or expired.', 'warning')
        return redirect(url_for('dr_tracker.index'))

    result = results_data.get('generation_result')

    if not result or not result['success']:
        flash('No DR entries available to download.', 'warning')
        return redirect(url_for('dr_tracker.results', result_id=result_id))

    entries = result['entries']

    if not entries:
        flash('No entries to export.', 'warning')
        return redirect(url_for('dr_tracker.results', result_id=result_id))

    # Get service
    service = get_tracker_service()

    try:
        # Generate export based on format
        if format == 'csv':
            content = service.export_to_csv(entries)
            mimetype = 'text/csv'
            filename = f'dr_tracker_{result_id[:8]}.csv'

            response = Response(
                content,
                mimetype=mimetype,
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )

        elif format == 'json':
            content = service.export_to_json(entries)
            mimetype = 'application/json'
            filename = f'dr_tracker_{result_id[:8]}.json'

            response = Response(
                content,
                mimetype=mimetype,
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )

        elif format == 'xlsx':
            content = service.export_to_xlsx(entries)
            mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            filename = f'dr_tracker_{result_id[:8]}.xlsx'

            response = Response(
                content,
                mimetype=mimetype,
                headers={'Content-Disposition': f'attachment; filename={filename}'}
            )

        logger.info(f"User {current_user.id} downloaded {format.upper()} from {result_id}")
        return response

    except Exception as e:
        logger.error(f"Error generating {format} export: {e}", exc_info=True)
        flash(f'Error generating {format.upper()} export: {str(e)}', 'danger')
        return redirect(url_for('dr_tracker.results', result_id=result_id))
