"""
RSS Manager Routes.

Handles RSS subscription management endpoints.
Per FR-013: RSS feed management with OPML export (integrated Python implementation).
"""

import logging
import json
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, Response
from flask_login import login_required, current_user

from app.services.rss_manager.rss_service import get_rss_service

logger = logging.getLogger(__name__)

# Create blueprint
rss_manager_bp = Blueprint('rss_manager', __name__, url_prefix='/tools/rss-manager')


@rss_manager_bp.route('/', methods=['GET'])
@login_required
def index():
    """
    Display RSS Manager dashboard with statistics.

    Returns:
        Rendered dashboard template
    """
    logger.info(f"User {current_user.id} accessed RSS Manager dashboard")

    service = get_rss_service()
    stats = service.get_dashboard_stats()

    return render_template(
        'tools/rss_manager/index.html',
        stats=stats
    )


@rss_manager_bp.route('/subscriptions', methods=['GET'])
@login_required
def list_subscriptions():
    """
    List RSS subscriptions with filtering, search, and pagination.

    Query Parameters:
        language: Filter by language code
        country: Filter by country code
        type: Filter by organization type
        scope: Filter by geographic scope
        search: Full-text search query
        page: Page number (default: 1)
        per_page: Items per page (default: 50, 0=all)

    Returns:
        Rendered subscriptions list template
    """
    service = get_rss_service()

    # Get query parameters
    language = request.args.get('language', '').strip() or None
    country = request.args.get('country', '').strip() or None
    org_type = request.args.get('type', '').strip() or None
    scope = request.args.get('scope', '').strip() or None
    search_query = request.args.get('search', '').strip() or None
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 50))

    # Get subscriptions
    result = service.get_all_subscriptions(
        language=language,
        country=country,
        org_type=org_type,
        scope=scope,
        search_query=search_query,
        page=page,
        per_page=per_page
    )

    logger.info(
        f"User {current_user.id} listed subscriptions: "
        f"total={result['total']}, page={page}, per_page={per_page}"
    )

    return render_template(
        'tools/rss_manager/list.html',
        subscriptions=result['subscriptions'],
        total=result['total'],
        page=result['page'],
        per_page=result['per_page'],
        total_pages=result['total_pages'],
        filters={
            'language': language,
            'country': country,
            'type': org_type,
            'scope': scope,
            'search': search_query
        },
        organization_types=service.ORGANIZATION_TYPES,
        scopes=service.SCOPES
    )


@rss_manager_bp.route('/subscriptions/add', methods=['GET'])
@login_required
def add_form():
    """
    Show add subscription form.

    Returns:
        Rendered add form template
    """
    service = get_rss_service()

    return render_template(
        'tools/rss_manager/add.html',
        organization_types=service.ORGANIZATION_TYPES,
        scopes=service.SCOPES
    )


@rss_manager_bp.route('/subscriptions/add', methods=['POST'])
@login_required
def add_subscription():
    """
    Create a new RSS subscription.

    Form Data:
        xml_url: RSS feed URL (required)
        html_url: Website URL (required)
        language: ISO 639-1 code (required)
        title: Organization name (required)
        type: Organization type (required)
        scope: Geographic scope (required)
        country: ISO 3166-1 alpha-3 code (required)
        subdivision: ISO 3166-2 code (optional)

    Returns:
        Redirect to subscriptions list
    """
    service = get_rss_service()

    data = {
        'xml_url': request.form.get('xml_url', '').strip(),
        'html_url': request.form.get('html_url', '').strip(),
        'language': request.form.get('language', '').strip(),
        'title': request.form.get('title', '').strip(),
        'type': request.form.get('type', '').strip(),
        'scope': request.form.get('scope', '').strip(),
        'country': request.form.get('country', '').strip(),
        'subdivision': request.form.get('subdivision', 'N/A').strip() or 'N/A'
    }

    result = service.create_subscription(data)

    if result['success']:
        flash(f'Subscription "{data["title"]}" added successfully!', 'success')
        logger.info(f"User {current_user.id} created subscription: {result['rss_id']}")
        return redirect(url_for('rss_manager.list_subscriptions'))
    else:
        flash(f'Error adding subscription: {result["error"]}', 'danger')
        logger.warning(f"User {current_user.id} failed to create subscription: {result['error']}")
        return redirect(url_for('rss_manager.add_form'))


@rss_manager_bp.route('/subscriptions/<rss_id>/edit', methods=['GET'])
@login_required
def edit_form(rss_id: str):
    """
    Show edit subscription form.

    Args:
        rss_id: Subscription ID

    Returns:
        Rendered edit form template
    """
    service = get_rss_service()
    subscription = service.get_subscription(rss_id)

    if not subscription:
        flash('Subscription not found.', 'danger')
        return redirect(url_for('rss_manager.list_subscriptions'))

    return render_template(
        'tools/rss_manager/edit.html',
        subscription=subscription,
        organization_types=service.ORGANIZATION_TYPES,
        scopes=service.SCOPES
    )


@rss_manager_bp.route('/subscriptions/<rss_id>/edit', methods=['POST'])
@login_required
def edit_subscription(rss_id: str):
    """
    Update an existing subscription.

    Args:
        rss_id: Subscription ID

    Form Data:
        Same as add_subscription

    Returns:
        Redirect to subscriptions list
    """
    service = get_rss_service()

    data = {
        'xml_url': request.form.get('xml_url', '').strip(),
        'html_url': request.form.get('html_url', '').strip(),
        'language': request.form.get('language', '').strip(),
        'title': request.form.get('title', '').strip(),
        'type': request.form.get('type', '').strip(),
        'scope': request.form.get('scope', '').strip(),
        'country': request.form.get('country', '').strip(),
        'subdivision': request.form.get('subdivision', 'N/A').strip() or 'N/A'
    }

    result = service.update_subscription(rss_id, data)

    if result['success']:
        flash(f'Subscription "{data["title"]}" updated successfully!', 'success')
        logger.info(f"User {current_user.id} updated subscription: {rss_id}")
        return redirect(url_for('rss_manager.list_subscriptions'))
    else:
        flash(f'Error updating subscription: {result["error"]}', 'danger')
        logger.warning(f"User {current_user.id} failed to update subscription: {result['error']}")
        return redirect(url_for('rss_manager.edit_form', rss_id=rss_id))


@rss_manager_bp.route('/subscriptions/<rss_id>/delete', methods=['POST'])
@login_required
def delete_subscription(rss_id: str):
    """
    Delete a subscription (soft delete with backup).

    Args:
        rss_id: Subscription ID

    Returns:
        Redirect to subscriptions list
    """
    service = get_rss_service()
    result = service.delete_subscription(rss_id)

    if result['success']:
        flash('Subscription deleted successfully (can be restored from Backup page).', 'success')
        logger.info(f"User {current_user.id} deleted subscription: {rss_id}")
    else:
        flash(f'Error deleting subscription: {result["error"]}', 'danger')
        logger.warning(f"User {current_user.id} failed to delete subscription: {result['error']}")

    return redirect(url_for('rss_manager.list_subscriptions'))


@rss_manager_bp.route('/subscriptions/bulk-delete', methods=['POST'])
@login_required
def bulk_delete():
    """
    Delete multiple subscriptions.

    Form Data:
        selected_ids: Comma-separated RSS IDs

    Returns:
        Redirect to subscriptions list
    """
    service = get_rss_service()

    # Get selected IDs
    selected_ids = request.form.get('selected_ids', '').strip()
    if not selected_ids:
        flash('No subscriptions selected.', 'warning')
        return redirect(url_for('rss_manager.list_subscriptions'))

    rss_ids = [id.strip() for id in selected_ids.split(',') if id.strip()]

    result = service.bulk_delete(rss_ids)

    if result['success']:
        flash(f'Deleted {result["deleted_count"]} subscriptions successfully.', 'success')
        logger.info(f"User {current_user.id} bulk deleted {result['deleted_count']} subscriptions")
    else:
        flash(f'Error deleting subscriptions: {result["error"]}', 'danger')

    return redirect(url_for('rss_manager.list_subscriptions'))


# =========================================================================
# Export Routes
# =========================================================================

@rss_manager_bp.route('/export', methods=['GET'])
@login_required
def export_page():
    """
    Show export options page.

    Returns:
        Rendered export page template
    """
    return render_template('tools/rss_manager/export.html')


@rss_manager_bp.route('/export/opml', methods=['POST'])
@login_required
def export_opml():
    """
    Export subscriptions to OPML file.

    Form Data:
        export_type: 'all', 'selected', or 'filtered'
        selected_ids: Comma-separated IDs (for selected)
        collection_name: Name for OPML collection
        language, country, type, scope: Filters (for filtered)

    Returns:
        OPML file download
    """
    service = get_rss_service()

    export_type = request.form.get('export_type', 'all')
    collection_name = request.form.get('collection_name', 'RSS Subscriptions').strip()

    if export_type == 'selected':
        # Export selected
        selected_ids = request.form.get('selected_ids', '').strip()
        if not selected_ids:
            flash('No subscriptions selected for export.', 'warning')
            return redirect(url_for('rss_manager.list_subscriptions'))

        rss_ids = [id.strip() for id in selected_ids.split(',') if id.strip()]
        opml_content = service.export_to_opml(rss_ids=rss_ids, collection_name=collection_name)

    elif export_type == 'filtered':
        # Export with filters
        filters = {
            'language': request.form.get('language', '').strip() or None,
            'country': request.form.get('country', '').strip() or None,
            'type': request.form.get('type', '').strip() or None,
            'scope': request.form.get('scope', '').strip() or None
        }
        opml_content = service.export_to_opml(filters=filters, collection_name=collection_name)

    else:
        # Export all
        opml_content = service.export_to_opml(collection_name=collection_name)

    # Generate filename
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{collection_name.replace(' ', '_')}_{timestamp}.opml"

    logger.info(f"User {current_user.id} exported OPML: {filename}")

    return Response(
        opml_content,
        mimetype='application/xml',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )


# =========================================================================
# Backup & Restore Routes
# =========================================================================

@rss_manager_bp.route('/backup', methods=['GET'])
@login_required
def backup_page():
    """
    Show backup and restore page with deleted subscriptions.

    Returns:
        Rendered backup page template
    """
    service = get_rss_service()
    deleted = service.get_deleted_subscriptions()

    logger.info(f"User {current_user.id} accessed backup page")

    return render_template(
        'tools/rss_manager/backup.html',
        deleted_subscriptions=deleted
    )


@rss_manager_bp.route('/backup/restore/<int:deleted_id>', methods=['POST'])
@login_required
def restore_subscription(deleted_id: int):
    """
    Restore a deleted subscription.

    Args:
        deleted_id: ID from deleted_subscriptions table

    Returns:
        Redirect to backup page
    """
    service = get_rss_service()
    result = service.restore_subscription(deleted_id)

    if result['success']:
        flash('Subscription restored successfully!', 'success')
        logger.info(f"User {current_user.id} restored subscription ID: {deleted_id}")
    else:
        flash(f'Error restoring subscription: {result["error"]}', 'danger')
        logger.warning(f"User {current_user.id} failed to restore subscription: {result['error']}")

    return redirect(url_for('rss_manager.backup_page'))


@rss_manager_bp.route('/backup/create', methods=['POST'])
@login_required
def create_backup():
    """
    Create a manual JSON backup of all subscriptions.

    Returns:
        JSON file download
    """
    service = get_rss_service()

    # Get all subscriptions
    result = service.get_all_subscriptions(per_page=0)
    subscriptions = result['subscriptions']

    # Convert to JSON
    backup_data = {
        'created_at': datetime.now().isoformat(),
        'total_count': len(subscriptions),
        'subscriptions': subscriptions
    }

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"rss_backup_{timestamp}.json"

    logger.info(f"User {current_user.id} created backup: {filename}")

    return Response(
        json.dumps(backup_data, indent=2),
        mimetype='application/json',
        headers={
            'Content-Disposition': f'attachment; filename={filename}'
        }
    )
