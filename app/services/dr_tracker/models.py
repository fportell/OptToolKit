"""
Data Models for DR-Tracker.

Pydantic models for Daily Report entries and validation.
"""

from pydantic import BaseModel, Field, field_validator
from typing import List, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DREntry(BaseModel):
    """
    Model for a Daily Report entry.

    Represents a single health surveillance event extracted from
    a Daily Report HTML file.
    """

    entry_number: str = Field(
        ...,
        description="Entry number (e.g., '1', '3a', '3b')"
    )

    hazard_list: List[str] = Field(
        default_factory=list,
        description="Matched canonical hazards"
    )

    report_date: str = Field(
        ...,
        description="Report date in mm/dd/yyyy format"
    )

    reported_location: str = Field(
        ...,
        description="Primary location reported"
    )

    cited_locations: Optional[List[str]] = Field(
        None,
        description="Additional cited locations"
    )

    summary: str = Field(
        ...,
        description="Summary text"
    )

    summary_title: Optional[str] = Field(
        None,
        description="Optional summary title (for RPG section entries)"
    )

    is_update: bool = Field(
        False,
        description="Whether this is an update to a previous entry"
    )

    references: List[Tuple[str, str]] = Field(
        default_factory=list,
        description="List of (url, label) tuples - maximum 3"
    )

    report_section: str = Field(
        ...,
        description="Section code: hod, dme, int, rpg"
    )

    program_areas: List[str] = Field(
        default_factory=list,
        description="Assigned program areas (acronyms)"
    )

    @field_validator('report_section')
    @classmethod
    def validate_section(cls, v: str) -> str:
        """Validate section code is one of the allowed values."""
        valid_sections = ['hod', 'dme', 'int', 'rpg']
        if v not in valid_sections:
            raise ValueError(f"Section must be one of {valid_sections}, got '{v}'")
        return v

    @field_validator('report_date')
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        """Validate date is in mm/dd/yyyy format."""
        try:
            datetime.strptime(v, '%m/%d/%Y')
        except ValueError:
            raise ValueError(f"Date must be in mm/dd/yyyy format, got '{v}'")
        return v

    @field_validator('references')
    @classmethod
    def validate_references(cls, v: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Validate references list has maximum 3 items."""
        if len(v) > 3:
            logger.warning(f"Entry has {len(v)} references, only first 3 will be used")
            return v[:3]
        return v

    @field_validator('entry_number')
    @classmethod
    def validate_entry_number(cls, v: str) -> str:
        """Validate entry number is not empty."""
        if not v or not v.strip():
            raise ValueError("Entry number cannot be empty")
        return v.strip()

    def to_dict(self) -> dict:
        """
        Convert to dictionary for JSON serialization.

        Converts tuples to lists for JSON compatibility.

        Returns:
            Dictionary representation
        """
        data = self.model_dump()
        # Convert tuples to lists for JSON serialization
        data['references'] = [[url, label] for url, label in self.references]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'DREntry':
        """
        Create instance from dictionary.

        Handles conversion of reference lists back to tuples.

        Args:
            data: Dictionary with entry data

        Returns:
            DREntry instance
        """
        if 'references' in data and isinstance(data['references'], list):
            # Convert lists back to tuples
            data['references'] = [tuple(ref) if isinstance(ref, list) else ref
                                  for ref in data['references']]
        return cls(**data)

    def get_formatted_summary(self) -> str:
        """
        Get formatted summary with title or update prefix if applicable.

        Returns:
            Formatted summary string
        """
        if self.summary_title:
            return f"{self.summary_title}: {self.summary}"
        elif self.is_update:
            return f"(Update): {self.summary}"
        else:
            return self.summary

    def get_section_name(self) -> str:
        """
        Get full section name from code.

        Returns:
            Full section name
        """
        section_names = {
            'hod': 'Highlight of the Day',
            'dme': 'Domestic Events (Media & Officials)',
            'int': 'International Events (Media & Officials)',
            'rpg': 'Research, Policies and Guidelines (Media & Officials)'
        }
        return section_names.get(self.report_section, self.report_section)

    def __str__(self) -> str:
        """String representation of entry."""
        return f"DREntry({self.entry_number}: {self.reported_location} - {self.get_section_name()})"

    def __repr__(self) -> str:
        """Debug representation of entry."""
        return (
            f"DREntry(entry_number='{self.entry_number}', "
            f"reported_location='{self.reported_location}', "
            f"section='{self.report_section}', "
            f"hazards={len(self.hazard_list)})"
        )


class ProcessingResult(BaseModel):
    """
    Model for HTML processing result.

    Used to return results from the main processing pipeline.
    """

    success: bool = Field(
        ...,
        description="Whether processing was successful"
    )

    entries: List[DREntry] = Field(
        default_factory=list,
        description="Extracted DR entries"
    )

    metadata: dict = Field(
        default_factory=dict,
        description="Processing metadata (model, timing, etc.)"
    )

    error: Optional[str] = Field(
        None,
        description="Error message if processing failed"
    )

    def get_entry_count(self) -> int:
        """Get number of extracted entries."""
        return len(self.entries)

    def has_error(self) -> bool:
        """Check if processing resulted in an error."""
        return not self.success or self.error is not None

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        data = self.model_dump()
        # Convert DREntry objects to dicts
        data['entries'] = [entry.to_dict() for entry in self.entries]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'ProcessingResult':
        """Create instance from dictionary."""
        if 'entries' in data and isinstance(data['entries'], list):
            # Convert dicts back to DREntry objects
            data['entries'] = [DREntry.from_dict(entry) if isinstance(entry, dict) else entry
                              for entry in data['entries']]
        return cls(**data)


def validate_entry_data(data: dict) -> Tuple[bool, Optional[str]]:
    """
    Validate entry data before creating DREntry instance.

    Args:
        data: Dictionary with entry data

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        DREntry.from_dict(data)
        return True, None
    except Exception as e:
        return False, str(e)
