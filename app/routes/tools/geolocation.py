"""
Geolocation Tool Routes.

Handles image upload, EXIF extraction, and map visualization.
Per FR-006: Extract GPS coordinates from images and display on interactive maps.
"""

import logging
import uuid
from pathlib import Path
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.services.geolocation.exif_extractor import ExifExtractor
from app.services.geolocation.map_generator import MapGenerator

logger = logging.getLogger(__name__)

# Create blueprint
geolocation_bp = Blueprint('geolocation', __name__, url_prefix='/tools/geolocation')

# Allowed file extensions
ALLOWED_EXTENSIONS = {'jpg', 'jpeg', 'png'}

# Store results temporarily (in production, use Redis or database)
_results_cache = {}


def allowed_file(filename: str) -> bool:
    """Check if filename has allowed extension."""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@geolocation_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display geolocation tool upload form.

    Returns:
        Rendered geolocation upload template
    """
    logger.info(f"User {current_user.id} accessed geolocation tool")
    return render_template('tools/geolocation.html')


@geolocation_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """
    Handle image upload and EXIF extraction.

    Accepts multiple image files, extracts EXIF data, generates map,
    and redirects to results page.

    Returns:
        Redirect to results page or error response
    """
    try:
        # Check if files were uploaded
        if 'images' not in request.files:
            flash('No files uploaded. Please select at least one image.', 'danger')
            return redirect(url_for('geolocation.index'))

        files = request.files.getlist('images')

        if not files or all(file.filename == '' for file in files):
            flash('No files selected. Please choose at least one image.', 'danger')
            return redirect(url_for('geolocation.index'))

        # Validate file count
        max_files = 20
        if len(files) > max_files:
            flash(f'Too many files. Maximum {max_files} images allowed.', 'danger')
            return redirect(url_for('geolocation.index'))

        # Get options
        show_path = request.form.get('show_path') == 'on'
        cluster_markers = request.form.get('cluster_markers') == 'on'
        tile_layer = request.form.get('tile_layer', 'OpenStreetMap')

        # Create temporary directory for uploads
        upload_dir = Path(current_app.instance_path) / 'uploads' / str(uuid.uuid4())
        upload_dir.mkdir(parents=True, exist_ok=True)

        # Save and process files
        uploaded_files = []
        for file in files:
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = upload_dir / filename

                # Check file size
                file.seek(0, 2)  # Seek to end
                file_size = file.tell()
                file.seek(0)  # Reset

                max_size = current_app.config['MAX_UPLOAD_SIZE_MB'] * 1024 * 1024
                if file_size > max_size:
                    flash(
                        f'File {filename} is too large '
                        f'(max {current_app.config["MAX_UPLOAD_SIZE_MB"]} MB).',
                        'warning'
                    )
                    continue

                # Save file
                file.save(str(filepath))
                uploaded_files.append(filepath)

                logger.info(f"Saved file: {filename} ({file_size} bytes)")

        if not uploaded_files:
            flash('No valid image files uploaded. Please upload JPEG or PNG images.', 'danger')
            return redirect(url_for('geolocation.index'))

        # Extract EXIF data from all images
        logger.info(f"Extracting EXIF data from {len(uploaded_files)} file(s)")
        exif_data = ExifExtractor.extract_from_multiple(uploaded_files)

        # Count images with GPS data
        gps_count = sum(1 for data in exif_data if data.get('has_gps'))

        if gps_count == 0:
            flash(
                'No GPS data found in uploaded images. '
                'Please upload images with EXIF GPS coordinates.',
                'warning'
            )

            # Still show results page with error info
            result_id = str(uuid.uuid4())
            _results_cache[result_id] = {
                'exif_data': exif_data,
                'map_html': None,
                'options': {
                    'show_path': show_path,
                    'cluster_markers': cluster_markers,
                    'tile_layer': tile_layer
                },
                'stats': {
                    'total_images': len(exif_data),
                    'images_with_gps': 0,
                    'images_with_exif': sum(1 for d in exif_data if d.get('has_exif'))
                }
            }

            return redirect(url_for('geolocation.results', result_id=result_id))

        # Generate map
        logger.info(f"Generating map for {gps_count} location(s)")

        if show_path and gps_count >= 2:
            # Sort by datetime if available
            sorted_data = sorted(
                exif_data,
                key=lambda x: x.get('datetime') or '',
                reverse=False
            )
            map_html = MapGenerator.create_map_with_path(sorted_data, tile_layer)
        else:
            map_html = MapGenerator.create_map(exif_data, tile_layer, cluster_markers)

        # Store results
        result_id = str(uuid.uuid4())
        _results_cache[result_id] = {
            'exif_data': exif_data,
            'map_html': map_html,
            'options': {
                'show_path': show_path,
                'cluster_markers': cluster_markers,
                'tile_layer': tile_layer
            },
            'stats': {
                'total_images': len(exif_data),
                'images_with_gps': gps_count,
                'images_with_exif': sum(1 for d in exif_data if d.get('has_exif'))
            }
        }

        logger.info(f"Processing complete. Result ID: {result_id}")
        flash(f'Successfully processed {gps_count} image(s) with GPS data.', 'success')

        return redirect(url_for('geolocation.results', result_id=result_id))

    except Exception as e:
        logger.error(f"Error processing upload: {e}", exc_info=True)
        flash(
            'An error occurred while processing your images. Please try again.',
            'danger'
        )
        return redirect(url_for('geolocation.index'))


@geolocation_bp.route('/results/<result_id>')
@login_required
def results(result_id: str):
    """
    Display results with map and EXIF data.

    Args:
        result_id: Unique identifier for results

    Returns:
        Rendered results template
    """
    # Get results from cache
    results_data = _results_cache.get(result_id)

    if not results_data:
        flash('Results not found or expired. Please upload images again.', 'warning')
        return redirect(url_for('geolocation.index'))

    logger.info(f"User {current_user.id} viewing results {result_id}")

    return render_template(
        'tools/geolocation_results.html',
        results=results_data,
        result_id=result_id
    )


@geolocation_bp.route('/api/coordinates/<result_id>')
@login_required
def get_coordinates(result_id: str):
    """
    Get GPS coordinates as JSON for export.

    Args:
        result_id: Unique identifier for results

    Returns:
        JSON response with coordinate data
    """
    results_data = _results_cache.get(result_id)

    if not results_data:
        return jsonify({'error': 'Results not found'}), 404

    # Extract coordinates
    coordinates = []
    for data in results_data['exif_data']:
        if data.get('has_gps'):
            coord_info = {
                'filename': data['filename'],
                'latitude': data['latitude'],
                'longitude': data['longitude'],
                'altitude': data.get('altitude'),
                'datetime': data.get('datetime'),
                'formatted': ExifExtractor.format_coordinates(
                    data['latitude'],
                    data['longitude']
                )
            }
            coordinates.append(coord_info)

    return jsonify({
        'result_id': result_id,
        'count': len(coordinates),
        'coordinates': coordinates
    })
