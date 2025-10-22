"""
Geolocation Tool Routes.

Handles country/region selection and standardized area attribution for reporting.
Per original functionality: Provides geolocation lookup and reporting standardization.
"""

import logging
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user

from app.services.geolocation.geolocation_service import GeolocationService

logger = logging.getLogger(__name__)

# Create blueprint
geolocation_bp = Blueprint('geolocation', __name__, url_prefix='/tools/geolocation')


def get_geolocation_service() -> GeolocationService:
    """Get geolocation service instance."""
    db_path = current_app.config['GEOLOCATION_DB_PATH']
    return GeolocationService(db_path)


@geolocation_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display geolocation tool country selection interface.

    Query Parameters:
        selected (str): Pipe-separated list of pre-selected countries

    Returns:
        Rendered geolocation tool template
    """
    logger.info(f"User {current_user.id} accessed geolocation tool")

    try:
        service = get_geolocation_service()
        all_countries = service.get_all_countries()

        # Get pre-selected countries from query parameter
        selected_param = request.args.get('selected', '')
        pre_selected = []
        if selected_param:
            pre_selected = [c.strip() for c in selected_param.split('|') if c.strip()]
            logger.info(f"Pre-selecting {len(pre_selected)} countries: {pre_selected}")
        else:
            logger.info("No pre-selected countries")

        return render_template(
            'tools/geolocation.html',
            countries=all_countries,
            pre_selected=pre_selected if pre_selected else []
        )

    except Exception as e:
        logger.error(f"Error loading geolocation tool: {e}", exc_info=True)
        flash(
            'An error occurred while loading the geolocation tool. Please try again.',
            'danger'
        )
        return redirect(url_for('landing.tools'))


@geolocation_bp.route('/process', methods=['POST'])
@login_required
def process():
    """
    Process country selection and generate area attribution.

    Accepts a list of selected countries, determines area attribution,
    and returns formatted reporting strings.

    Returns:
        Rendered results template or redirect with error
    """
    try:
        # Get selected countries from form
        selected_countries = request.form.getlist('countries')

        if not selected_countries:
            flash('No countries selected. Please select at least one country.', 'warning')
            return redirect(url_for('geolocation.index'))

        logger.info(f"Processing {len(selected_countries)} selected country/countries")

        # Process selection
        service = get_geolocation_service()
        results = service.process_selection(selected_countries)

        # Convert DataFrame to list of dicts for template
        country_data_list = results['country_data'].to_dict('records')

        logger.info(f"Area attribution: {results['area_attribution']}")

        return render_template(
            'tools/geolocation_results.html',
            selected_countries=results['countries'],
            country_data=country_data_list,
            area_attribution=results['area_attribution'],
            affected_locations=results['affected_locations']
        )

    except Exception as e:
        logger.error(f"Error processing country selection: {e}", exc_info=True)
        flash(
            'An error occurred while processing your selection. Please try again.',
            'danger'
        )
        return redirect(url_for('geolocation.index'))


@geolocation_bp.route('/api/countries', methods=['GET'])
@login_required
def get_countries():
    """
    Get list of all countries as JSON.

    Returns:
        JSON response with country list
    """
    try:
        service = get_geolocation_service()
        countries = service.get_all_countries()

        return jsonify({
            'count': len(countries),
            'countries': countries
        })

    except Exception as e:
        logger.error(f"Error fetching countries: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch countries'}), 500


@geolocation_bp.route('/api/country-data', methods=['POST'])
@login_required
def get_country_data():
    """
    Get data for selected countries as JSON.

    Accepts JSON payload with 'countries' array.

    Returns:
        JSON response with country data and area attribution
    """
    try:
        data = request.get_json()
        countries = data.get('countries', [])

        if not countries:
            return jsonify({'error': 'No countries provided'}), 400

        service = get_geolocation_service()
        results = service.process_selection(countries)

        # Convert DataFrame to list of dicts
        country_data_list = results['country_data'].to_dict('records')

        return jsonify({
            'countries': results['countries'],
            'country_data': country_data_list,
            'area_attribution': results['area_attribution'],
            'affected_locations': results['affected_locations']
        })

    except Exception as e:
        logger.error(f"Error fetching country data: {e}", exc_info=True)
        return jsonify({'error': 'Failed to fetch country data'}), 500
