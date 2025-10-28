"""
RSS Subscription Manager Service.

Provides comprehensive RSS subscription management integrated into OpsToolKit.
Replaces the legacy Node.js service with native Python/Flask implementation.
"""

import logging
import sqlite3
import hashlib
import json
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
from flask import current_app

from app.services.rss_manager.query_parser import (
    parse_query,
    is_advanced_query,
    QueryParseError
)

logger = logging.getLogger(__name__)


class RSSService:
    """
    RSS subscription management service.

    Provides CRUD operations, search, filtering, OPML export, and import functionality.
    """

    # Valid organization types
    ORGANIZATION_TYPES = [
        'Academic Institution',
        'Government Agency',
        'Media Outlet',
        'Non-Governmental Organization',
        'Professional Association',
        'Public Health Agency',
        'Scientific Journal'
    ]

    # Valid scopes
    SCOPES = ['International', 'National', 'Local']

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize RSS service.

        Args:
            db_path: Path to SQLite database file. If None, uses config.
        """
        self.db_path = db_path

    def _get_db_path(self) -> Path:
        """Get database path from config or use provided path."""
        if self.db_path:
            return self.db_path

        # Try to get from Flask config
        try:
            base_dir = Path(current_app.config.get('BASE_DIR', Path(__file__).parent.parent.parent.parent))
            return base_dir / 'app' / 'data' / 'rss_subscriptions.db'
        except RuntimeError:
            # Outside application context
            base_dir = Path(__file__).parent.parent.parent.parent
            return base_dir / 'app' / 'data' / 'rss_subscriptions.db'

    def _get_connection(self) -> sqlite3.Connection:
        """
        Get database connection.

        Returns:
            sqlite3.Connection: Database connection with row factory
        """
        db_path = self._get_db_path()
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _generate_rss_id(self, xml_url: str) -> str:
        """
        Generate RSS ID from XML URL.

        Args:
            xml_url: RSS feed URL

        Returns:
            str: First 16 characters of SHA-256 hash
        """
        return hashlib.sha256(xml_url.encode()).hexdigest()[:16]

    # =========================================================================
    # Advanced Query Building
    # =========================================================================

    def _build_sql_from_ast(self, node: Dict[str, Any], params: List[Any]) -> str:
        """
        Recursively build SQL WHERE clause from AST node.

        Args:
            node: AST node (BINARY_OP, UNARY_OP, or FIELD)
            params: List to accumulate query parameters

        Returns:
            SQL WHERE clause string (without 'WHERE' keyword)
        """
        node_type = node.get('type')

        if node_type == 'FIELD':
            # Leaf node: field:value
            field = node['field']
            value = node['value']
            search_type = node['searchType']

            if search_type == 'exact':
                # Exact match: simple WHERE clause
                params.append(value)
                return f"{field} = ?"
            else:
                # FTS field: use subquery
                if field == 'url':
                    # Search both xml_url and html_url
                    fts_query = f"(xml_url:{value} OR html_url:{value})"
                else:
                    fts_query = f"{field}:{value}"

                params.append(fts_query)
                return """rss_id IN (
                    SELECT rss_id FROM rss_search
                    WHERE rss_search MATCH ?
                )"""

        elif node_type == 'BINARY_OP':
            # Binary operator: AND or OR
            operator = node['operator']
            left_sql = self._build_sql_from_ast(node['left'], params)
            right_sql = self._build_sql_from_ast(node['right'], params)

            return f"({left_sql}) {operator} ({right_sql})"

        elif node_type == 'UNARY_OP':
            # Unary operator: NOT
            operator = node['operator']
            operand_sql = self._build_sql_from_ast(node['operand'], params)

            if operator == 'NOT':
                return f"NOT ({operand_sql})"
            else:
                raise ValueError(f"Unknown unary operator: {operator}")

        else:
            raise ValueError(f"Unknown node type: {node_type}")

    def _build_advanced_query(self, ast: Dict[str, Any]) -> Tuple[List[str], List[Any]]:
        """
        Build SQL query components from parsed AST.

        Args:
            ast: Parsed query AST from query_parser (tree structure)

        Returns:
            Tuple of (where_clauses, params)
        """
        params = []
        where_clause = self._build_sql_from_ast(ast, params)

        return [where_clause], params

    # =========================================================================
    # CRUD Operations
    # =========================================================================

    def get_all_subscriptions(self,
                             language: Optional[str] = None,
                             country: Optional[str] = None,
                             org_type: Optional[str] = None,
                             scope: Optional[str] = None,
                             search_query: Optional[str] = None,
                             page: int = 1,
                             per_page: int = 50) -> Dict[str, Any]:
        """
        Get all RSS subscriptions with optional filtering and pagination.

        Args:
            language: Filter by language code (e.g., 'en', 'fr')
            country: Filter by country code (e.g., 'USA', 'CAN')
            org_type: Filter by organization type
            scope: Filter by geographic scope
            search_query: Full-text search query
            page: Page number (1-indexed)
            per_page: Items per page (0 = all)

        Returns:
            dict: {
                'subscriptions': List of subscription dicts,
                'total': Total count,
                'page': Current page,
                'per_page': Items per page,
                'total_pages': Total pages
            }
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build query
            where_clauses = []
            params = []

            # Check if search_query uses advanced syntax
            if search_query and is_advanced_query(search_query):
                try:
                    # Parse advanced query
                    ast = parse_query(search_query)

                    # Build SQL from AST
                    adv_where, adv_params = self._build_advanced_query(ast)
                    where_clauses.extend(adv_where)
                    params.extend(adv_params)

                    logger.info(f"Advanced query parsed successfully")
                except QueryParseError as e:
                    logger.error(f"Query parse error: {e}")
                    # Return empty result with error message
                    return {
                        'subscriptions': [],
                        'total': 0,
                        'page': page,
                        'per_page': per_page,
                        'total_pages': 0,
                        'error': str(e)
                    }
            elif search_query:
                # Simple FTS5 search (backward compatibility)
                where_clauses.append("""
                    rss_id IN (
                        SELECT rss_id FROM rss_search
                        WHERE rss_search MATCH ?
                    )
                """)
                params.append(search_query)

            # Dropdown filters (only if not overridden by advanced query)
            # Note: Advanced query conditions take precedence
            if language:
                where_clauses.append("language = ?")
                params.append(language)
            if country:
                where_clauses.append("country = ?")
                params.append(country)
            if org_type:
                where_clauses.append("type = ?")
                params.append(org_type)
            if scope:
                where_clauses.append("scope = ?")
                params.append(scope)

            where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""

            # Get total count
            count_query = f"SELECT COUNT(*) as count FROM rss_subscriptions {where_sql}"
            cursor.execute(count_query, params)
            total = cursor.fetchone()['count']

            # Calculate pagination
            if per_page == 0:
                # Get all
                offset = 0
                limit_sql = ""
                total_pages = 1
            else:
                total_pages = (total + per_page - 1) // per_page
                offset = (page - 1) * per_page
                limit_sql = f"LIMIT {per_page} OFFSET {offset}"

            # Get subscriptions
            query = f"""
                SELECT * FROM rss_subscriptions
                {where_sql}
                ORDER BY title ASC
                {limit_sql}
            """
            cursor.execute(query, params)

            subscriptions = [dict(row) for row in cursor.fetchall()]

            return {
                'subscriptions': subscriptions,
                'total': total,
                'page': page,
                'per_page': per_page,
                'total_pages': total_pages
            }

        finally:
            conn.close()

    def get_subscription(self, rss_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a single subscription by ID.

        Args:
            rss_id: Subscription ID

        Returns:
            dict or None: Subscription data
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT * FROM rss_subscriptions WHERE rss_id = ?", (rss_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def create_subscription(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new RSS subscription.

        Args:
            data: Subscription data with keys:
                - xml_url (required)
                - html_url (required)
                - language (required)
                - title (required)
                - type (required)
                - scope (required)
                - country (required)
                - subdivision (optional, defaults to 'N/A')

        Returns:
            dict: {'success': bool, 'rss_id': str or None, 'error': str or None}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Validate required fields
            required = ['xml_url', 'html_url', 'language', 'title', 'type', 'scope', 'country']
            for field in required:
                if not data.get(field):
                    return {'success': False, 'rss_id': None, 'error': f'Missing required field: {field}'}

            # Validate type and scope
            if data['type'] not in self.ORGANIZATION_TYPES:
                return {'success': False, 'rss_id': None, 'error': f'Invalid organization type: {data["type"]}'}
            if data['scope'] not in self.SCOPES:
                return {'success': False, 'rss_id': None, 'error': f'Invalid scope: {data["scope"]}'}

            # Generate RSS ID
            rss_id = self._generate_rss_id(data['xml_url'])

            # Check for duplicates
            cursor.execute("SELECT rss_id FROM rss_subscriptions WHERE xml_url = ?", (data['xml_url'],))
            if cursor.fetchone():
                return {'success': False, 'rss_id': None, 'error': 'Subscription with this URL already exists'}

            # Insert subscription
            cursor.execute("""
                INSERT INTO rss_subscriptions (
                    rss_id, xml_url, html_url, language, title, type, scope, country, subdivision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                rss_id,
                data['xml_url'],
                data['html_url'],
                data['language'],
                data['title'],
                data['type'],
                data['scope'],
                data['country'],
                data.get('subdivision', 'N/A')
            ))

            conn.commit()
            logger.info(f"Created RSS subscription: {rss_id} - {data['title']}")

            return {'success': True, 'rss_id': rss_id, 'error': None}

        except sqlite3.IntegrityError as e:
            return {'success': False, 'rss_id': None, 'error': f'Database error: {str(e)}'}
        finally:
            conn.close()

    def update_subscription(self, rss_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update an existing subscription.

        Args:
            rss_id: Subscription ID
            data: Updated subscription data

        Returns:
            dict: {'success': bool, 'error': str or None}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Check if exists
            cursor.execute("SELECT rss_id FROM rss_subscriptions WHERE rss_id = ?", (rss_id,))
            if not cursor.fetchone():
                return {'success': False, 'error': 'Subscription not found'}

            # Validate if type/scope provided
            if 'type' in data and data['type'] not in self.ORGANIZATION_TYPES:
                return {'success': False, 'error': f'Invalid organization type: {data["type"]}'}
            if 'scope' in data and data['scope'] not in self.SCOPES:
                return {'success': False, 'error': f'Invalid scope: {data["scope"]}'}

            # Build update query
            update_fields = []
            params = []

            for field in ['xml_url', 'html_url', 'language', 'title', 'type', 'scope', 'country', 'subdivision']:
                if field in data:
                    update_fields.append(f"{field} = ?")
                    params.append(data[field])

            if not update_fields:
                return {'success': False, 'error': 'No fields to update'}

            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(rss_id)

            query = f"UPDATE rss_subscriptions SET {', '.join(update_fields)} WHERE rss_id = ?"
            cursor.execute(query, params)

            conn.commit()
            logger.info(f"Updated RSS subscription: {rss_id}")

            return {'success': True, 'error': None}

        except sqlite3.IntegrityError as e:
            return {'success': False, 'error': f'Database error: {str(e)}'}
        finally:
            conn.close()

    def delete_subscription(self, rss_id: str) -> Dict[str, Any]:
        """
        Delete a subscription (soft delete - backed up to deleted_subscriptions).

        Args:
            rss_id: Subscription ID

        Returns:
            dict: {'success': bool, 'error': str or None}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM rss_subscriptions WHERE rss_id = ?", (rss_id,))

            if cursor.rowcount == 0:
                return {'success': False, 'error': 'Subscription not found'}

            conn.commit()
            logger.info(f"Deleted RSS subscription: {rss_id}")

            return {'success': True, 'error': None}

        finally:
            conn.close()

    def bulk_delete(self, rss_ids: List[str]) -> Dict[str, Any]:
        """
        Delete multiple subscriptions.

        Args:
            rss_ids: List of subscription IDs

        Returns:
            dict: {'success': bool, 'deleted_count': int, 'error': str or None}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            placeholders = ','.join('?' * len(rss_ids))
            cursor.execute(f"DELETE FROM rss_subscriptions WHERE rss_id IN ({placeholders})", rss_ids)

            deleted_count = cursor.rowcount
            conn.commit()

            logger.info(f"Bulk deleted {deleted_count} RSS subscriptions")

            return {'success': True, 'deleted_count': deleted_count, 'error': None}

        finally:
            conn.close()

    # =========================================================================
    # Dashboard Statistics
    # =========================================================================

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """
        Get statistics for dashboard.

        Returns:
            dict: Statistics including total count, breakdowns by language and type
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Total count
            cursor.execute("SELECT COUNT(*) as count FROM rss_subscriptions")
            total = cursor.fetchone()['count']

            # By language
            cursor.execute("""
                SELECT language, COUNT(*) as count
                FROM rss_subscriptions
                GROUP BY language
                ORDER BY count DESC
                LIMIT 10
            """)
            by_language = [dict(row) for row in cursor.fetchall()]

            # By type
            cursor.execute("""
                SELECT type, COUNT(*) as count
                FROM rss_subscriptions
                GROUP BY type
                ORDER BY count DESC
            """)
            by_type = [dict(row) for row in cursor.fetchall()]

            # By country (top 10)
            cursor.execute("""
                SELECT country, COUNT(*) as count
                FROM rss_subscriptions
                GROUP BY country
                ORDER BY count DESC
                LIMIT 10
            """)
            by_country = [dict(row) for row in cursor.fetchall()]

            return {
                'total': total,
                'by_language': by_language,
                'by_type': by_type,
                'by_country': by_country
            }

        finally:
            conn.close()

    # =========================================================================
    # OPML Export
    # =========================================================================

    def export_to_opml(self,
                      rss_ids: Optional[List[str]] = None,
                      collection_name: str = "RSS Subscriptions",
                      filters: Optional[Dict[str, str]] = None) -> str:
        """
        Export subscriptions to OPML format.

        Args:
            rss_ids: Specific subscription IDs to export (None = all)
            collection_name: Name for the collection
            filters: Optional filters (language, country, type, scope)

        Returns:
            str: OPML XML string
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Build query
            if rss_ids:
                placeholders = ','.join('?' * len(rss_ids))
                query = f"SELECT * FROM rss_subscriptions WHERE rss_id IN ({placeholders}) ORDER BY language, title"
                cursor.execute(query, rss_ids)
            elif filters:
                where_clauses = []
                params = []

                if filters.get('language'):
                    where_clauses.append("language = ?")
                    params.append(filters['language'])
                if filters.get('country'):
                    where_clauses.append("country = ?")
                    params.append(filters['country'])
                if filters.get('type'):
                    where_clauses.append("type = ?")
                    params.append(filters['type'])
                if filters.get('scope'):
                    where_clauses.append("scope = ?")
                    params.append(filters['scope'])

                where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
                query = f"SELECT * FROM rss_subscriptions {where_sql} ORDER BY language, title"
                cursor.execute(query, params)
            else:
                cursor.execute("SELECT * FROM rss_subscriptions ORDER BY language, title")

            subscriptions = [dict(row) for row in cursor.fetchall()]

            # Generate OPML
            return self._generate_opml(subscriptions, collection_name)

        finally:
            conn.close()

    def _generate_opml(self, subscriptions: List[Dict[str, Any]], collection_name: str) -> str:
        """Generate OPML XML from subscriptions."""
        # Create root element
        opml = ET.Element('opml', version='2.0')

        # Head
        head = ET.SubElement(opml, 'head')
        ET.SubElement(head, 'title').text = collection_name
        ET.SubElement(head, 'dateCreated').text = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        ET.SubElement(head, 'docs').text = 'http://opml.org/spec2.opml'
        ET.SubElement(head, 'ownerName').text = 'OpsToolKit RSS Manager'

        # Body
        body = ET.SubElement(opml, 'body')

        # Group by language
        by_language = {}
        for sub in subscriptions:
            lang = sub['language']
            if lang not in by_language:
                by_language[lang] = []
            by_language[lang].append(sub)

        # Create language groups
        for lang in sorted(by_language.keys()):
            subs = by_language[lang]
            group_title = f"{lang.upper()} Subscriptions ({len(subs)})"
            lang_outline = ET.SubElement(body, 'outline', title=group_title)

            for sub in subs:
                # Generate prefix
                prefix_parts = [sub['language'], sub['country']]
                if sub['subdivision'] not in ('N/A', 'NAT'):
                    prefix_parts.append(sub['subdivision'])

                # Type abbreviation
                type_abbr = {
                    'Academic Institution': 'ACA',
                    'Government Agency': 'GOV',
                    'Media Outlet': 'MED',
                    'Non-Governmental Organization': 'NGO',
                    'Professional Association': 'PRO',
                    'Public Health Agency': 'PHA',
                    'Scientific Journal': 'SCI'
                }.get(sub['type'], 'OTH')

                prefix_parts.append(type_abbr)
                prefix = '-'.join(prefix_parts)

                title = f"{prefix}: {sub['title']}"

                ET.SubElement(lang_outline, 'outline',
                             title=title,
                             type='rss',
                             xmlUrl=sub['xml_url'],
                             htmlUrl=sub['html_url'] or '')

        # Convert to string with declaration
        xml_str = ET.tostring(opml, encoding='unicode')
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_str}'

    # =========================================================================
    # Backup & Restore
    # =========================================================================

    def get_deleted_subscriptions(self) -> List[Dict[str, Any]]:
        """
        Get all deleted subscriptions.

        Returns:
            list: List of deleted subscription dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                SELECT * FROM deleted_subscriptions
                ORDER BY deleted_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def restore_subscription(self, deleted_id: int) -> Dict[str, Any]:
        """
        Restore a deleted subscription.

        Args:
            deleted_id: ID from deleted_subscriptions table

        Returns:
            dict: {'success': bool, 'error': str or None}
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # Get deleted subscription
            cursor.execute("SELECT * FROM deleted_subscriptions WHERE id = ?", (deleted_id,))
            deleted = cursor.fetchone()

            if not deleted:
                return {'success': False, 'error': 'Deleted subscription not found'}

            deleted = dict(deleted)

            # Restore to main table
            cursor.execute("""
                INSERT INTO rss_subscriptions (
                    rss_id, xml_url, html_url, language, title, type, scope, country, subdivision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                deleted['rss_id'],
                deleted['xml_url'],
                deleted['html_url'],
                deleted['language'],
                deleted['title'],
                deleted['type'],
                deleted['scope'],
                deleted['country'],
                deleted['subdivision'],
                deleted['created_at'],
                deleted['updated_at']
            ))

            # Remove from deleted table
            cursor.execute("DELETE FROM deleted_subscriptions WHERE id = ?", (deleted_id,))

            conn.commit()
            logger.info(f"Restored RSS subscription: {deleted['rss_id']}")

            return {'success': True, 'error': None}

        except sqlite3.IntegrityError as e:
            return {'success': False, 'error': f'Cannot restore: {str(e)}'}
        finally:
            conn.close()


# Global service instance
_rss_service: Optional[RSSService] = None


def get_rss_service() -> RSSService:
    """
    Get the global RSS service instance.

    Returns:
        RSSService: The service instance
    """
    global _rss_service

    if _rss_service is None:
        _rss_service = RSSService()

    return _rss_service
