"""
Data Processing Service for DR Knowledge Chatbot.

Handles Excel file loading, validation, event extraction, and chunking.
Per chatbot_revised.md: 512 tokens/chunk, 100 token overlap.
"""

import logging
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from pathlib import Path

import pandas as pd
import tiktoken

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

@dataclass
class Reference:
    """Reference source for an epidemiological event."""
    label: str  # Source name
    url: str    # Source URL


@dataclass
class Event:
    """Epidemiological event from the database."""
    entry_id: str          # ENTRY_# (e.g., "00001")
    date: datetime         # Event date
    hazard: str            # Disease/pathogen name
    reported_location: str # Primary location
    cited_location: str    # Additional locations
    summary: str           # Full event description
    section: str           # hod/dme/int/rgp
    program_areas: str     # Notified program areas
    references: List[Reference] = field(default_factory=list)

    # Generated fields
    keywords: List[str] = field(default_factory=list)
    normalized_hazard: str = ""

    def __post_init__(self):
        """Normalize hazard name and extract keywords."""
        if not self.normalized_hazard:
            self.normalized_hazard = self.hazard.lower().strip()

        if not self.keywords:
            self.keywords = self._extract_keywords()

    def _extract_keywords(self) -> List[str]:
        """Extract keywords from hazard, locations, and summary."""
        keywords = set()

        # Add hazard
        keywords.add(self.normalized_hazard)

        # Add locations
        for location in [self.reported_location, self.cited_location]:
            if location and location != "N/A":
                keywords.update(location.lower().split(','))

        # Extract epidemiological terms from summary
        epi_terms = [
            'outbreak', 'cases', 'deaths', 'confirmed', 'suspected',
            'probable', 'surveillance', 'alert', 'epidemic', 'pandemic',
            'cluster', 'transmission', 'infection', 'disease'
        ]

        summary_lower = self.summary.lower()
        for term in epi_terms:
            if term in summary_lower:
                keywords.add(term)

        # Limit to 15 keywords
        return sorted(list(keywords))[:15]

    def to_text(self) -> str:
        """Convert event to searchable text format."""
        try:
            text_parts = [
                f"# Event #{self.entry_id}: {self.hazard}",
                f"\n**Date:** {self.date.strftime('%Y-%m-%d')}",
                f"\n**Reported Location:** {self.reported_location}",
            ]
        except Exception as e:
            import logging
            logging.error(f"Error formatting event {self.entry_id}: {e}")
            raise

        if self.cited_location and self.cited_location != "N/A":
            text_parts.append(f"\n**Cited Location:** {self.cited_location}")

        text_parts.append(f"\n\n**Summary:**\n{self.summary}")

        text_parts.append(f"\n\n**Classification:**")
        text_parts.append(f"\n- Section: {self.section}")

        if self.program_areas and self.program_areas != "N/A":
            text_parts.append(f"\n- Program Areas: {self.program_areas}")

        if self.references:
            text_parts.append(f"\n\n**References:**")
            for i, ref in enumerate(self.references, 1):
                text_parts.append(f"\n{i}. **{ref.label}**: {ref.url}")

        text_parts.append(f"\n\n**Keywords:** {', '.join(self.keywords)}")

        return "".join(text_parts)


@dataclass
class Chunk:
    """Text chunk for embedding."""
    text: str
    event_id: str
    chunk_index: int  # 0 if single chunk, else position
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0

    def __post_init__(self):
        """Calculate token count if not provided."""
        if self.token_count == 0:
            encoding = tiktoken.get_encoding("cl100k_base")
            self.token_count = len(encoding.encode(self.text))


# ============================================================================
# Data Processor
# ============================================================================

class DataProcessor:
    """Process Excel database files into events and chunks."""

    def __init__(self):
        """Initialize data processor."""
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.chunk_size = 512  # tokens
        self.chunk_overlap = 100  # tokens

    def load_excel(self, filepath: str, sheet_name: str = "DR data") -> pd.DataFrame:
        """
        Load Excel file into DataFrame.

        Args:
            filepath: Path to Excel file
            sheet_name: Name of worksheet to read (default: "DR data")

        Returns:
            DataFrame with event data

        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid or sheet doesn't exist
        """
        try:
            path = Path(filepath)
            if not path.exists():
                raise FileNotFoundError(f"Excel file not found: {filepath}")

            logger.info(f"Loading Excel file: {filepath}, worksheet: '{sheet_name}'")

            # Read Excel with specific worksheet and date parsing
            df = pd.read_excel(
                filepath,
                sheet_name=sheet_name,
                engine='openpyxl'
            )

            logger.info(f"Loaded {len(df)} rows from worksheet '{sheet_name}'")

            return df

        except ValueError as e:
            if "Worksheet" in str(e):
                # List available sheets for debugging
                try:
                    import openpyxl
                    wb = openpyxl.load_workbook(filepath, read_only=True)
                    available_sheets = wb.sheetnames
                    logger.error(f"Worksheet '{sheet_name}' not found. Available sheets: {available_sheets}")
                    raise ValueError(f"Worksheet '{sheet_name}' not found. Available sheets: {available_sheets}")
                except:
                    raise ValueError(f"Worksheet '{sheet_name}' not found in Excel file")
            raise
        except Exception as e:
            logger.error(f"Error loading Excel file: {e}")
            raise ValueError(f"Failed to load Excel file: {e}")

    def validate_data(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Validate DataFrame structure and content.

        Args:
            df: DataFrame to validate

        Returns:
            Validation result with 'valid' boolean and 'errors' list
        """
        errors = []
        warnings = []

        # Check required columns
        required_columns = [
            'ENTRY_#', 'DATE', 'HAZARD', 'REPORTED_LOCATION',
            'SUMMARY', 'SECTION'
        ]

        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            errors.append(f"Missing required columns: {', '.join(missing_columns)}")

        # Check for empty DataFrame
        if len(df) == 0:
            errors.append("DataFrame is empty")

        # Check for rows with missing ENTRY_# (these will be filtered out, not errors)
        if 'ENTRY_#' in df.columns:
            empty_ids = df['ENTRY_#'].isna().sum()
            if empty_ids > 0:
                warnings.append(f"{empty_ids} rows have missing ENTRY_# (will be skipped)")
                logger.info(f"Found {empty_ids} rows without ENTRY_# - these will be filtered out")

        # Check date format
        if 'DATE' in df.columns:
            # Try to parse dates
            try:
                pd.to_datetime(df['DATE'], format='%Y/%m/%d', errors='coerce')
            except Exception as e:
                errors.append(f"Date format error: {e}")

        return {
            'valid': len(errors) == 0,
            'errors': errors,
            'warnings': warnings,
            'total_rows': len(df)
        }

    def extract_events(self, df: pd.DataFrame) -> List[Event]:
        """
        Extract Event objects from DataFrame.

        Args:
            df: Validated DataFrame

        Returns:
            List of Event objects
        """
        events = []

        # Filter out rows with missing ENTRY_# (header rows, blank rows, etc.)
        original_count = len(df)
        df = df[df['ENTRY_#'].notna()].copy()
        filtered_count = len(df)

        if original_count != filtered_count:
            logger.info(f"Filtered out {original_count - filtered_count} rows without ENTRY_# ({filtered_count} valid rows remaining)")

        # Debug: Log first row columns
        if len(df) > 0:
            logger.info(f"DataFrame columns: {list(df.columns)}")
            logger.info(f"First row sample: ENTRY_#={df.iloc[0].get('ENTRY_#')}, DATE={df.iloc[0].get('DATE')}, HAZARD={df.iloc[0].get('HAZARD')}")

        for idx, row in df.iterrows():
            try:
                # Parse date
                date_str = str(row['DATE'])
                try:
                    event_date = pd.to_datetime(date_str, format='%Y/%m/%d')
                except:
                    # Try alternate formats
                    try:
                        event_date = pd.to_datetime(date_str)
                    except Exception as date_error:
                        logger.warning(f"Could not parse date for entry {row.get('ENTRY_#')} at index {idx}: {date_str}, error: {date_error}")
                        continue

                # Extract references
                references = []
                for i in [1, 2, 3]:
                    label_col = f'REFERENCE_0{i}lab'
                    url_col = f'REFERENCE_0{i}url' if i < 3 else f'REFERENCE_0{i}ur'  # Note: typo in column name

                    if label_col in row and url_col in row:
                        label = str(row[label_col]) if pd.notna(row[label_col]) else ""
                        url = str(row[url_col]) if pd.notna(row[url_col]) else ""

                        if label and url and label != "nan" and url != "nan":
                            references.append(Reference(label=label, url=url))

                # Create event
                event = Event(
                    entry_id=str(row['ENTRY_#']).zfill(5),
                    date=event_date,
                    hazard=str(row['HAZARD']) if pd.notna(row['HAZARD']) else "Unknown",
                    reported_location=str(row['REPORTED_LOCATION']) if pd.notna(row['REPORTED_LOCATION']) else "N/A",
                    cited_location=str(row.get('CITED_LOCATION', 'N/A')) if pd.notna(row.get('CITED_LOCATION')) else "N/A",
                    summary=str(row['SUMMARY']) if pd.notna(row['SUMMARY']) else "",
                    section=str(row['SECTION']) if pd.notna(row['SECTION']) else "",
                    program_areas=str(row.get('PROGRAM_AREAS', 'N/A')) if pd.notna(row.get('PROGRAM_AREAS')) else "N/A",
                    references=references
                )

                events.append(event)

            except Exception as e:
                logger.error(f"Error extracting event at index {idx}, ENTRY_#={row.get('ENTRY_#', 'N/A')}: {e}", exc_info=True)
                # Log first 5 errors in detail
                if idx < 5:
                    logger.error(f"Row data: {dict(row)}")
                continue

        logger.info(f"Extracted {len(events)} events from {len(df)} rows")

        return events

    def chunk_events(self, events: List[Event]) -> List[Chunk]:
        """
        Convert events to chunks with metadata.

        Strategy: Keep events intact (don't split mid-event).
        If event > chunk_size, split into multiple chunks with overlap.

        Args:
            events: List of Event objects

        Returns:
            List of Chunk objects ready for embedding
        """
        import sys
        logger.info(f"chunk_events: Starting to chunk {len(events)} events...")
        sys.stdout.flush()

        chunks = []

        for i, event in enumerate(events):
            # Log every event after 50 to find the problematic one
            if i >= 50:
                logger.info(f"Processing event {i + 1}/{len(events)}: ID={event.entry_id}")
                sys.stdout.flush()
            elif (i + 1) % 20 == 0:
                logger.info(f"Chunking progress: {i + 1}/{len(events)} events")
                sys.stdout.flush()
            elif i == 0:
                logger.info(f"Processing first event (ID: {event.entry_id})...")
                sys.stdout.flush()

            try:
                event_text = event.to_text()

                if i >= 50:
                    logger.info(f"  Event {event.entry_id}: to_text() returned {len(event_text)} chars")
                    sys.stdout.flush()

                tokens = self.encoding.encode(event_text)

                if i >= 50:
                    logger.info(f"  Event {event.entry_id}: encoded to {len(tokens)} tokens")
                    sys.stdout.flush()
                elif i == 0:
                    logger.info(f"First event: {len(event_text)} chars, {len(tokens)} tokens")
                    sys.stdout.flush()

            except Exception as e:
                logger.error(f"Error encoding event {event.entry_id}: {e}")
                sys.stdout.flush()
                raise

            # If event fits in one chunk
            if len(tokens) <= self.chunk_size:
                metadata = self._generate_metadata(event, 0, 1)
                chunk = Chunk(
                    text=event_text,
                    event_id=event.entry_id,
                    chunk_index=0,
                    metadata=metadata,
                    token_count=len(tokens)
                )
                chunks.append(chunk)

            else:
                # Split into multiple chunks with overlap
                if i >= 50:
                    logger.info(f"  Event {event.entry_id}: Splitting into multiple chunks (>{self.chunk_size} tokens)")
                    sys.stdout.flush()

                num_chunks = 0
                start = 0

                while start < len(tokens):
                    end = min(start + self.chunk_size, len(tokens))
                    chunk_tokens = tokens[start:end]
                    chunk_text = self.encoding.decode(chunk_tokens)

                    if i >= 50:
                        logger.info(f"    Chunk {num_chunks}: tokens[{start}:{end}] ({len(chunk_tokens)} tokens)")
                        sys.stdout.flush()

                    metadata = self._generate_metadata(event, num_chunks, -1)  # Will update total later
                    chunk = Chunk(
                        text=chunk_text,
                        event_id=event.entry_id,
                        chunk_index=num_chunks,
                        metadata=metadata,
                        token_count=len(chunk_tokens)
                    )
                    chunks.append(chunk)

                    num_chunks += 1

                    # Break if we've processed all tokens (prevents infinite loop)
                    if end >= len(tokens):
                        break

                    start = end - self.chunk_overlap  # Overlap

                # Update total chunks in metadata
                for i in range(num_chunks):
                    chunks[-(num_chunks - i)].metadata['total_chunks'] = num_chunks

        logger.info(f"Created {len(chunks)} chunks from {len(events)} events")

        return chunks

    def _generate_metadata(self, event: Event, chunk_index: int, total_chunks: int) -> Dict[str, Any]:
        """Generate metadata for a chunk."""
        # Convert keywords list to comma-separated string (ChromaDB doesn't accept lists)
        keywords_str = ", ".join(event.keywords[:10]) if event.keywords else ""

        return {
            "event_id": event.entry_id,
            "date": event.date.strftime('%Y-%m-%d'),
            "date_unix": int(event.date.timestamp()),
            "hazard": event.hazard,
            "hazard_normalized": event.normalized_hazard,
            "location": event.reported_location,
            "section": event.section,
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "keywords": keywords_str  # Comma-separated string instead of list
        }

    def calculate_file_hash(self, filepath: str) -> str:
        """Calculate MD5 hash of file for change detection."""
        hash_md5 = hashlib.md5()
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
