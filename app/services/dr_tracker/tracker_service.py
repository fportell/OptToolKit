"""
DR-Tracker Builder Service.

Main service for processing Daily Report HTML files and generating Excel tracker files.
Complete rebuild for health surveillance Daily Reports (replacing Discrepancy Reports).
"""

import logging
import time
import json
import re
from typing import Dict, Any, List, Optional
from datetime import datetime
from io import BytesIO
import pandas as pd
import xlsxwriter
from openai import OpenAI
from flask import current_app

from .html_processor import process_html_file
from .hazard_matcher import HazardMatcher
from .models import DREntry, ProcessingResult

logger = logging.getLogger(__name__)


class DRTrackerService:
    """
    DR-Tracker service for processing Daily Reports.

    Handles:
    - HTML sanitization
    - OpenAI extraction
    - Hazard matching
    - Excel export with VBA macros
    """

    def __init__(self):
        """Initialize the DR-Tracker service."""
        self.client: Optional[OpenAI] = None
        self.model: str = 'gpt-4.1'
        self.hazard_matcher: Optional[HazardMatcher] = None
        self.preprompt: Optional[str] = None

    def _ensure_initialized(self):
        """Lazy initialization of OpenAI client and resources."""
        if self.client is None:
            api_key = current_app.config.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")

            self.client = OpenAI(api_key=api_key)
            self.model = current_app.config.get('DR_TRACKER_MODEL', 'gpt-4.1')
            logger.info(f"Initialized OpenAI client with model: {self.model}")

        if self.hazard_matcher is None:
            hazards_path = 'app/data/dr_tracker/idc_hazards_hierarchical.json'
            self.hazard_matcher = HazardMatcher(hazards_path)
            logger.info("Initialized hazard matcher")

        if self.preprompt is None:
            self.preprompt = self._load_preprompt()
            logger.info(f"Loaded preprompt ({len(self.preprompt)} chars)")

    def _load_preprompt(self) -> str:
        """
        Load system preprompt from file.

        Returns:
            Preprompt content

        Raises:
            FileNotFoundError: If preprompt file not found
        """
        preprompt_path = 'app/data/dr_tracker/gpt4_dr2tracker_preprompt.txt'
        try:
            with open(preprompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            logger.error(f"Preprompt file not found: {preprompt_path}")
            raise

    def process_html_upload(self, file_bytes: bytes, timeout: int = 120) -> ProcessingResult:
        """
        Complete pipeline: HTML → OpenAI → Hazard Matching.

        Args:
            file_bytes: Raw bytes from uploaded HTML file
            timeout: OpenAI API timeout in seconds

        Returns:
            ProcessingResult with success status, entries, and metadata
        """
        start_time = time.time()

        try:
            # Ensure initialized
            self._ensure_initialized()

            logger.info("Starting HTML upload processing")

            # Step 1: Sanitize HTML
            logger.info("Step 1: Sanitizing HTML")
            cleaned_html = process_html_file(file_bytes)
            logger.info(f"HTML cleaned: {len(cleaned_html)} chars")

            # Step 2: Extract with OpenAI
            logger.info("Step 2: Calling OpenAI for extraction")
            openai_result = self._call_openai(cleaned_html, timeout)

            if not openai_result['success']:
                return ProcessingResult(
                    success=False,
                    error=openai_result['error'],
                    metadata={'processing_time': time.time() - start_time}
                )

            # Step 3: Parse JSON response
            logger.info("Step 3: Parsing OpenAI JSON response")
            entries = self._parse_json_response(openai_result['content'])
            logger.info(f"Parsed {len(entries)} entries")

            # Step 4: Match hazards to canonical list
            logger.info("Step 4: Matching hazards to canonical list")
            entries = self._match_hazards(entries)

            processing_time = time.time() - start_time

            logger.info(f"Processing complete in {processing_time:.2f}s: {len(entries)} entries")

            return ProcessingResult(
                success=True,
                entries=entries,
                metadata={
                    'model': self.model,
                    'processing_time': processing_time,
                    'entry_count': len(entries),
                    'openai_time': openai_result.get('processing_time', 0)
                }
            )

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"Error processing HTML upload: {e}", exc_info=True)
            return ProcessingResult(
                success=False,
                error=str(e),
                metadata={'processing_time': processing_time}
            )

    def _call_openai(self, html_content: str, timeout: int) -> Dict[str, Any]:
        """
        Call OpenAI API with gpt-4.1 model.

        Args:
            html_content: Cleaned HTML content
            timeout: API timeout in seconds

        Returns:
            Dictionary with success, content, processing_time, and optional error
        """
        start_time = time.time()

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.preprompt},
                    {"role": "user", "content": html_content}
                ],
                temperature=0.7,
                timeout=timeout
            )

            processing_time = time.time() - start_time
            content = response.choices[0].message.content.strip()

            logger.info(f"OpenAI call successful in {processing_time:.2f}s")

            return {
                'success': True,
                'content': content,
                'processing_time': processing_time
            }

        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"OpenAI API call failed: {e}")
            return {
                'success': False,
                'error': f"OpenAI API error: {str(e)}",
                'processing_time': processing_time
            }

    def _parse_json_response(self, content: str) -> List[DREntry]:
        """
        Parse OpenAI JSON response into DREntry objects.

        Args:
            content: JSON string from OpenAI

        Returns:
            List of DREntry objects

        Raises:
            ValueError: If JSON parsing fails
        """
        # Remove markdown code blocks if present
        if content.startswith('```'):
            content = content.split('```')[1]
            if content.startswith('json') or content.startswith('python'):
                content = content[4:] if content.startswith('json') else content[6:]
            content = content.strip()

        # Remove any remaining trailing code blocks
        if content.endswith('```'):
            content = content.rsplit('```', 1)[0].strip()

        # Convert Python literals to JSON literals
        # OpenAI sometimes returns Python syntax (True/False/None) instead of JSON (true/false/null)
        content = re.sub(r'\bTrue\b', 'true', content)
        content = re.sub(r'\bFalse\b', 'false', content)
        content = re.sub(r'\bNone\b', 'null', content)

        try:
            parsed_json = json.loads(content)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Content preview: {content[:500]}")
            raise ValueError(f"Invalid JSON response from OpenAI: {str(e)}")

        if not isinstance(parsed_json, list):
            raise ValueError("Expected JSON array of entries")

        # Convert to DREntry objects
        entries = []
        for idx, entry_data in enumerate(parsed_json):
            try:
                # Convert references from [[url, label], ...] to [(url, label), ...]
                if 'references' in entry_data:
                    entry_data['references'] = [tuple(ref) for ref in entry_data['references']]

                entry = DREntry.from_dict(entry_data)
                entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to parse entry {idx}: {e}")
                continue

        return entries

    def _match_hazards(self, entries: List[DREntry]) -> List[DREntry]:
        """
        Match all hazards in entries to canonical list.

        Args:
            entries: List of DREntry objects

        Returns:
            Updated list of DREntry objects with matched hazards
        """
        for entry in entries:
            if entry.hazard_list:
                matched_hazards = self.hazard_matcher.match_hazards(entry.hazard_list)
                entry.hazard_list = matched_hazards

        return entries

    def export_to_excel_with_macros(self, entries: List[DREntry]) -> bytes:
        """
        Generate .xlsm file with two sheets and VBA macros.

        Sheet 1: Flags_and_Tags (with hyperlink formulas)
        Sheet 2: DR_tracker_PBI (full data)

        Args:
            entries: List of DREntry objects

        Returns:
            Excel file content as bytes

        Raises:
            ValueError: If export fails
        """
        try:
            logger.info(f"Generating Excel file with {len(entries)} entries")

            # Convert entries to DataFrames
            df_full = self._entries_to_dataframe(entries)
            df_flags = self._transform_for_flags_and_tags(df_full)

            # Create Excel with macros
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True, 'macro_enabled': True})

            # Add VBA project
            vba_path = current_app.config.get('DR_TRACKER_VBA_PATH', 'app/data/dr_tracker/vbaProject.bin')
            try:
                workbook.add_vba_project(vba_path)
                logger.info("VBA macros embedded successfully")
            except Exception as e:
                logger.warning(f"Failed to embed VBA macros: {e}")

            # Write sheets
            self._write_sheet(workbook, 'Flags_and_Tags', df_flags, is_flags_sheet=True)
            self._write_sheet(workbook, 'DR_tracker_PBI', df_full, is_flags_sheet=False)

            workbook.close()
            excel_bytes = output.getvalue()
            output.close()

            logger.info(f"Excel file generated: {len(excel_bytes)} bytes")
            return excel_bytes

        except Exception as e:
            logger.error(f"Failed to generate Excel: {e}", exc_info=True)
            raise ValueError(f"Excel generation failed: {str(e)}")

    def _entries_to_dataframe(self, entries: List[DREntry]) -> pd.DataFrame:
        """
        Convert DREntry objects to pandas DataFrame for DR_tracker_PBI sheet.

        Columns: ENTRY_#, HAZARD, DATE, REPORTED_LOCATION, CITED_LOCATIONS,
                 SUMMARY, REFERENCE_01lab, REFERENCE_01url, REFERENCE_02lab,
                 REFERENCE_02url, REFERENCE_03lab, REFERENCE_03url,
                 SECTION, PROGRAM_AREAS

        Args:
            entries: List of DREntry objects

        Returns:
            pandas DataFrame
        """
        rows = []

        for entry in entries:
            # Prepare hazard (join list with commas)
            hazard = ", ".join(entry.hazard_list) if entry.hazard_list else ""

            # Prepare cited locations
            cited_locations = ", ".join(entry.cited_locations) if entry.cited_locations else ""

            # Prepare summary (with title or update prefix)
            summary = entry.get_formatted_summary()

            # Prepare references (up to 3)
            ref_labels = ["", "", ""]
            ref_urls = ["", "", ""]

            for i, (url, label) in enumerate(entry.references[:3]):
                ref_labels[i] = label
                ref_urls[i] = url

            # Prepare program areas
            program_areas = ", ".join(entry.program_areas) if entry.program_areas else ""

            row = {
                "ENTRY_#": entry.entry_number,
                "HAZARD": hazard,
                "DATE": entry.report_date,
                "REPORTED_LOCATION": entry.reported_location,
                "CITED_LOCATIONS": cited_locations,
                "SUMMARY": summary,
                "REFERENCE_01lab": ref_labels[0],
                "REFERENCE_01url": ref_urls[0],
                "REFERENCE_02lab": ref_labels[1],
                "REFERENCE_02url": ref_urls[1],
                "REFERENCE_03lab": ref_labels[2],
                "REFERENCE_03url": ref_urls[2],
                "SECTION": entry.report_section,
                "PROGRAM_AREAS": program_areas
            }
            rows.append(row)

        columns = [
            "ENTRY_#", "HAZARD", "DATE", "REPORTED_LOCATION", "CITED_LOCATIONS",
            "SUMMARY", "REFERENCE_01lab", "REFERENCE_01url", "REFERENCE_02lab",
            "REFERENCE_02url", "REFERENCE_03lab", "REFERENCE_03url",
            "SECTION", "PROGRAM_AREAS"
        ]

        return pd.DataFrame(rows, columns=columns)

    def _transform_for_flags_and_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Transform DataFrame for Flags_and_Tags sheet.

        Creates REFERENCE_XXhlk columns with Excel =HYPERLINK() formulas.
        Excludes CITED_LOCATIONS and SECTION columns.

        Args:
            df: Full DataFrame from _entries_to_dataframe

        Returns:
            Transformed DataFrame
        """
        transformed_df = df.copy()

        # Create Excel hyperlink formulas
        transformed_df["REFERENCE_01hlk"] = transformed_df.apply(
            lambda row: f'=HYPERLINK("{row["REFERENCE_01url"]}", "{row["REFERENCE_01lab"]}")'
            if row["REFERENCE_01lab"] and row["REFERENCE_01url"] else "", axis=1
        )

        transformed_df["REFERENCE_02hlk"] = transformed_df.apply(
            lambda row: f'=HYPERLINK("{row["REFERENCE_02url"]}", "{row["REFERENCE_02lab"]}")'
            if row["REFERENCE_02lab"] and row["REFERENCE_02url"] else "", axis=1
        )

        transformed_df["REFERENCE_03hlk"] = transformed_df.apply(
            lambda row: f'=HYPERLINK("{row["REFERENCE_03url"]}", "{row["REFERENCE_03lab"]}")'
            if row["REFERENCE_03lab"] and row["REFERENCE_03url"] else "", axis=1
        )

        # Select only required columns
        columns = [
            "ENTRY_#", "HAZARD", "DATE", "REPORTED_LOCATION",
            "SUMMARY", "REFERENCE_01hlk", "REFERENCE_02hlk",
            "REFERENCE_03hlk", "PROGRAM_AREAS"
        ]

        return transformed_df[columns]

    def _write_sheet(self, workbook: xlsxwriter.Workbook, sheet_name: str,
                     df: pd.DataFrame, is_flags_sheet: bool):
        """
        Write DataFrame to Excel worksheet with formatting.

        Args:
            workbook: xlsxwriter Workbook object
            sheet_name: Name of the sheet
            df: DataFrame to write
            is_flags_sheet: Whether this is the Flags_and_Tags sheet
        """
        worksheet = workbook.add_worksheet(sheet_name)

        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#0d6efd',
            'font_color': 'white',
            'border': 1,
            'align': 'center',
            'valign': 'vcenter'
        })

        cell_format = workbook.add_format({
            'border': 1,
            'valign': 'top',
            'text_wrap': True
        })

        # Set column widths
        column_widths = {
            'ENTRY_#': 10,
            'HAZARD': 25,
            'DATE': 12,
            'REPORTED_LOCATION': 20,
            'CITED_LOCATIONS': 30,
            'SUMMARY': 60,
            'REFERENCE_01lab': 15,
            'REFERENCE_01url': 40,
            'REFERENCE_02lab': 15,
            'REFERENCE_02url': 40,
            'REFERENCE_03lab': 15,
            'REFERENCE_03url': 40,
            'REFERENCE_01hlk': 15,
            'REFERENCE_02hlk': 15,
            'REFERENCE_03hlk': 15,
            'SECTION': 10,
            'PROGRAM_AREAS': 40
        }

        # Write headers
        for col_num, column in enumerate(df.columns):
            worksheet.write(0, col_num, column, header_format)
            width = column_widths.get(column, 15)
            worksheet.set_column(col_num, col_num, width)

        # Write data
        for row_num, row_data in enumerate(df.itertuples(index=False), start=1):
            for col_num, value in enumerate(row_data):
                worksheet.write(row_num, col_num, value, cell_format)

        # Add auto-filter
        worksheet.autofilter(0, 0, len(df), len(df.columns) - 1)

        # Freeze top row
        worksheet.freeze_panes(1, 0)

        logger.info(f"Wrote sheet '{sheet_name}' with {len(df)} rows")

    def load_hazards(self) -> List[Dict]:
        """
        Load matchable hazards for UI.

        Returns flattened list of matchable hazards with variants.
        Simple hazards and children only (no parents with children).

        Returns:
            List of hazard dictionaries with structure:
            {
                "canonical_hazard": str,
                "parent": Optional[str],
                "variants": List[str],
                "display_name": str  (e.g., "Hazard" or "Parent::Child")
            }
        """
        # Ensure hazard matcher is initialized
        self._ensure_initialized()

        # Return matchable items from hazard matcher
        return self.hazard_matcher.get_matchable_items()

    def load_program_areas(self) -> List[Dict]:
        """
        Load program areas for UI.

        Returns:
            List of program area dictionaries
        """
        with open('app/data/dr_tracker/program_areas.json', 'r', encoding='utf-8') as f:
            return json.load(f)


# Global service instance
_tracker_service: Optional[DRTrackerService] = None


def get_tracker_service() -> DRTrackerService:
    """
    Get the global DR-Tracker service instance (singleton).

    Returns:
        DRTrackerService instance
    """
    global _tracker_service

    if _tracker_service is None:
        _tracker_service = DRTrackerService()
        logger.info("Created new DR-Tracker service instance")

    return _tracker_service
