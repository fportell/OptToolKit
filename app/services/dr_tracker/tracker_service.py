"""
DR-Tracker Builder Service.

Generates structured DR-Tracker reports from text prompts using OpenAI.
Per FR-008: Generate DR-Tracker reports with configurable output formats.
"""

import logging
import time
import json
import csv
import io
from typing import Dict, Any, Optional, List
from datetime import datetime
from openai import OpenAI
from flask import current_app
import xlsxwriter

logger = logging.getLogger(__name__)


class DRTrackerService:
    """
    DR-Tracker report generation service using OpenAI.

    Converts natural language prompts into structured DR-Tracker data
    and exports to multiple formats.
    """

    # DR-Tracker field schema
    FIELD_SCHEMA = {
        'id': {'type': 'string', 'description': 'Unique identifier (DR-XXX format)'},
        'title': {'type': 'string', 'description': 'Brief title of the DR'},
        'description': {'type': 'string', 'description': 'Detailed description'},
        'category': {'type': 'string', 'description': 'Category (e.g., Technical, Process, Safety)'},
        'priority': {'type': 'string', 'description': 'Priority level (High, Medium, Low)'},
        'status': {'type': 'string', 'description': 'Current status (Open, In Progress, Resolved, Closed)'},
        'assigned_to': {'type': 'string', 'description': 'Person or team assigned'},
        'created_date': {'type': 'string', 'description': 'Creation date (YYYY-MM-DD)'},
        'due_date': {'type': 'string', 'description': 'Due date (YYYY-MM-DD)'},
        'resolution': {'type': 'string', 'description': 'Resolution details (if resolved)'}
    }

    # System prompt for OpenAI
    SYSTEM_PROMPT = """You are a DR-Tracker report generator. Your task is to convert natural language descriptions into structured DR (Discrepancy Report) entries.

Each DR entry must have these fields:
- id: Unique identifier in format DR-XXX (where XXX is a number)
- title: Brief, descriptive title
- description: Detailed description of the issue or discrepancy
- category: One of [Technical, Process, Safety, Documentation, Quality, Other]
- priority: One of [High, Medium, Low]
- status: One of [Open, In Progress, Resolved, Closed]
- assigned_to: Person or team name (or "Unassigned")
- created_date: Today's date in YYYY-MM-DD format
- due_date: Appropriate due date in YYYY-MM-DD format
- resolution: Empty string if not resolved, otherwise resolution details

Generate a JSON array of DR entries based on the user's prompt. Each entry should be a complete DR record.

IMPORTANT: Return ONLY valid JSON, no explanations or additional text."""

    def __init__(self):
        """Initialize the DR-Tracker service."""
        self.client = None
        self.model = None

    def _ensure_client(self):
        """Ensure OpenAI client is initialized."""
        if self.client is None:
            api_key = current_app.config.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")

            self.client = OpenAI(api_key=api_key)
            self.model = current_app.config.get('DR_TRACKER_MODEL', 'gpt-4')

            logger.info(f"Initialized OpenAI client for DR-Tracker with model: {self.model}")

    def generate_from_prompt(self,
                            prompt: str,
                            timeout: int = 120) -> Dict[str, Any]:
        """
        Generate DR-Tracker entries from a text prompt.

        Args:
            prompt: Natural language description of DRs to create
            timeout: Maximum processing time in seconds (default: 120)

        Returns:
            dict: Generation results with keys:
                - success: bool
                - entries: list of DR dictionaries (if successful)
                - count: int (number of entries)
                - prompt: str (original prompt)
                - model: str
                - processing_time: float (seconds)
                - error: str (if failed)
        """
        start_time = time.time()

        result = {
            'success': False,
            'entries': [],
            'count': 0,
            'prompt': prompt,
            'model': None,
            'processing_time': 0,
            'error': None
        }

        try:
            # Initialize client
            self._ensure_client()
            result['model'] = self.model

            # Validate input
            if not prompt or not prompt.strip():
                result['error'] = 'Prompt is empty'
                return result

            if len(prompt) > 10000:
                result['error'] = 'Prompt is too long (maximum 10,000 characters)'
                return result

            # Add today's date to context
            today = datetime.utcnow().strftime('%Y-%m-%d')
            contextualized_prompt = f"Today's date is {today}.\n\n{prompt}"

            logger.info(f"Generating DR entries from prompt (length: {len(prompt)} chars)")

            # Make API call with timeout handling
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": contextualized_prompt}
                ],
                temperature=0.7,
                max_tokens=2000,
                timeout=timeout
            )

            # Check processing time
            elapsed = time.time() - start_time
            if elapsed > timeout:
                result['error'] = f'Processing exceeded timeout of {timeout} seconds'
                return result

            # Extract and parse JSON response
            content = response.choices[0].message.content.strip()

            # Remove markdown code blocks if present
            if content.startswith('```'):
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
                content = content.strip()

            try:
                entries = json.loads(content)
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse JSON response: {e}")
                logger.error(f"Response content: {content}")
                result['error'] = f'Failed to parse AI response as JSON: {str(e)}'
                return result

            # Validate entries
            if not isinstance(entries, list):
                result['error'] = 'AI response is not a list of entries'
                return result

            # Validate and clean entries
            validated_entries = []
            for idx, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    logger.warning(f"Entry {idx} is not a dictionary, skipping")
                    continue

                # Ensure all required fields exist
                cleaned_entry = {}
                for field, schema in self.FIELD_SCHEMA.items():
                    value = entry.get(field, '')
                    cleaned_entry[field] = str(value) if value else ''

                validated_entries.append(cleaned_entry)

            result['entries'] = validated_entries
            result['count'] = len(validated_entries)
            result['success'] = True

            logger.info(f"Generated {result['count']} DR entries in {elapsed:.2f}s")

        except Exception as e:
            logger.error(f"Error generating DR entries: {e}", exc_info=True)
            result['error'] = f'Generation failed: {str(e)}'

        finally:
            result['processing_time'] = time.time() - start_time

        return result

    def export_to_csv(self, entries: List[Dict[str, Any]]) -> str:
        """
        Export DR entries to CSV format.

        Args:
            entries: List of DR entry dictionaries

        Returns:
            str: CSV content as string
        """
        if not entries:
            return ''

        output = io.StringIO()

        # Get all field names from schema
        fieldnames = list(self.FIELD_SCHEMA.keys())

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for entry in entries:
            writer.writerow(entry)

        csv_content = output.getvalue()
        output.close()

        logger.info(f"Exported {len(entries)} entries to CSV")
        return csv_content

    def export_to_json(self, entries: List[Dict[str, Any]]) -> str:
        """
        Export DR entries to JSON format.

        Args:
            entries: List of DR entry dictionaries

        Returns:
            str: JSON content as string
        """
        json_content = json.dumps(entries, indent=2)
        logger.info(f"Exported {len(entries)} entries to JSON")
        return json_content

    def export_to_xlsx(self, entries: List[Dict[str, Any]]) -> bytes:
        """
        Export DR entries to XLSX format.

        Args:
            entries: List of DR entry dictionaries

        Returns:
            bytes: XLSX file content as bytes
        """
        if not entries:
            return b''

        output = io.BytesIO()

        # Create workbook
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('DR Tracker')

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0d6efd',
            'font_color': 'white',
            'border': 1
        })

        cell_format = workbook.add_format({
            'border': 1,
            'valign': 'top',
            'text_wrap': True
        })

        priority_formats = {
            'High': workbook.add_format({'bg_color': '#dc3545', 'font_color': 'white', 'border': 1}),
            'Medium': workbook.add_format({'bg_color': '#ffc107', 'border': 1}),
            'Low': workbook.add_format({'bg_color': '#28a745', 'font_color': 'white', 'border': 1})
        }

        status_formats = {
            'Open': workbook.add_format({'bg_color': '#6c757d', 'font_color': 'white', 'border': 1}),
            'In Progress': workbook.add_format({'bg_color': '#0dcaf0', 'border': 1}),
            'Resolved': workbook.add_format({'bg_color': '#28a745', 'font_color': 'white', 'border': 1}),
            'Closed': workbook.add_format({'bg_color': '#495057', 'font_color': 'white', 'border': 1})
        }

        # Set column widths
        column_widths = {
            'id': 12,
            'title': 30,
            'description': 50,
            'category': 15,
            'priority': 10,
            'status': 15,
            'assigned_to': 20,
            'created_date': 12,
            'due_date': 12,
            'resolution': 40
        }

        # Write headers
        fieldnames = list(self.FIELD_SCHEMA.keys())
        for col_num, field in enumerate(fieldnames):
            worksheet.write(0, col_num, field.replace('_', ' ').title(), header_format)
            worksheet.set_column(col_num, col_num, column_widths.get(field, 15))

        # Write data
        for row_num, entry in enumerate(entries, start=1):
            for col_num, field in enumerate(fieldnames):
                value = entry.get(field, '')

                # Apply special formatting for priority and status
                if field == 'priority' and value in priority_formats:
                    worksheet.write(row_num, col_num, value, priority_formats[value])
                elif field == 'status' and value in status_formats:
                    worksheet.write(row_num, col_num, value, status_formats[value])
                else:
                    worksheet.write(row_num, col_num, value, cell_format)

        # Add auto-filter
        worksheet.autofilter(0, 0, len(entries), len(fieldnames) - 1)

        # Freeze top row
        worksheet.freeze_panes(1, 0)

        workbook.close()
        xlsx_content = output.getvalue()
        output.close()

        logger.info(f"Exported {len(entries)} entries to XLSX")
        return xlsx_content

    def validate_entries(self, entries: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate DR entries and return validation report.

        Args:
            entries: List of DR entry dictionaries

        Returns:
            dict: Validation report with keys:
                - valid: bool (all entries valid)
                - total: int (total entries)
                - errors: list of error messages
                - warnings: list of warning messages
        """
        report = {
            'valid': True,
            'total': len(entries),
            'errors': [],
            'warnings': []
        }

        if not entries:
            report['warnings'].append('No entries to validate')
            return report

        for idx, entry in enumerate(entries):
            entry_num = idx + 1

            # Check required fields
            for field in self.FIELD_SCHEMA.keys():
                if field not in entry or not entry[field]:
                    if field in ['id', 'title', 'description']:
                        report['errors'].append(f"Entry {entry_num}: Required field '{field}' is missing or empty")
                        report['valid'] = False
                    else:
                        report['warnings'].append(f"Entry {entry_num}: Field '{field}' is empty")

            # Validate specific fields
            if 'id' in entry:
                if not entry['id'].startswith('DR-'):
                    report['warnings'].append(f"Entry {entry_num}: ID should start with 'DR-'")

            if 'priority' in entry and entry['priority']:
                if entry['priority'] not in ['High', 'Medium', 'Low']:
                    report['warnings'].append(f"Entry {entry_num}: Invalid priority '{entry['priority']}'")

            if 'status' in entry and entry['status']:
                if entry['status'] not in ['Open', 'In Progress', 'Resolved', 'Closed']:
                    report['warnings'].append(f"Entry {entry_num}: Invalid status '{entry['status']}'")

        logger.info(f"Validation complete: {report['total']} entries, {len(report['errors'])} errors, {len(report['warnings'])} warnings")
        return report


# Global service instance
_tracker_service: Optional[DRTrackerService] = None


def get_tracker_service() -> DRTrackerService:
    """
    Get the global DR-Tracker service instance.

    Returns:
        DRTrackerService: The service instance
    """
    global _tracker_service

    if _tracker_service is None:
        _tracker_service = DRTrackerService()

    return _tracker_service
