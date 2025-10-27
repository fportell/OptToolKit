# DR-Tracker Builder - Complete Rebuild Implementation Plan

**Date Created**: 2025-10-24
**Status**: Planning
**Objective**: Replace Discrepancy Report functionality with Daily Report (health surveillance) processing system

---

## Table of Contents

1. [Overview](#overview)
2. [Requirements Summary](#requirements-summary)
3. [Architecture Decisions](#architecture-decisions)
4. [Implementation Checklist](#implementation-checklist)
5. [Detailed Implementation Phases](#detailed-implementation-phases)
6. [File Structure](#file-structure)
7. [Technical Specifications](#technical-specifications)
8. [Testing Strategy](#testing-strategy)
9. [Dependencies](#dependencies)

---

## Overview

### What We're Building

A Flask-based web tool that processes Daily Reports (health surveillance reports in HTML format) and generates structured Excel tracker files with VBA macros.

### Pipeline Flow

```
HTML Upload → Sanitization → OpenAI Extraction → Hazard Matching →
Editable Table → Excel Export (.xlsm)
```

### Key Features

- HTML file upload and preprocessing
- OpenAI-powered data extraction (gpt-4.1 model)
- Fuzzy hazard matching to canonical list
- Interactive editable table with searchable multi-select dropdowns
- Excel export with VBA macros (two sheets)
- Session-based data management

---

## Requirements Summary

### User Answers to Key Questions

1. **VBA Project File**: ✅ Copy from `legacy_code/ops_toolkit/src/data/daily_report/vbaProject.bin`
2. **Section Codes**: ✅ Keep using codes (hod, dme, int, rpg)
3. **Error Handling**: ✅ Re-upload only (no manual entry creation)
4. **Entry Numbering**: ✅ Allow manual editing (support "1", "3a", "3b" formats)
5. **Backward Compatibility**: ✅ Complete replacement (delete old Discrepancy Report functionality)

### Technical Decisions

- **Hazard Matching**: Exact match first, then fuzzy match (85% threshold using rapidfuzz)
- **Multi-select UI**: Geolocation-style searchable checkboxes with filtering
- **Session Storage**: Flask server-side session with 2-hour expiry
- **VBA Macros**: Use xlsxwriter's `add_vba_project()` method
- **OpenAI Model**: gpt-4.1
- **File Size Limit**: 5MB for HTML uploads
- **Processing Timeout**: 120 seconds for OpenAI calls

---

## Architecture Decisions

### Data Flow

```
User uploads HTML → Backend processes → Session cache stores data →
User edits in browser → Updates cached data → Download generates Excel
```

### Session Management

```python
_session_cache = {
    "session_id": {
        "entries": [DREntry.dict(), ...],
        "metadata": {
            "model": "gpt-4.1",
            "processing_time": 45.2
        },
        "timestamp": datetime
    }
}
```

### Excel Structure

**Sheet 1: Flags_and_Tags**
- Columns: ENTRY_#, HAZARD, DATE, REPORTED_LOCATION, SUMMARY, REFERENCE_01hlk, REFERENCE_02hlk, REFERENCE_03hlk, PROGRAM_AREAS
- References as Excel hyperlink formulas: `=HYPERLINK("url", "label")`

**Sheet 2: DR_tracker_PBI**
- Columns: ENTRY_#, HAZARD, DATE, REPORTED_LOCATION, CITED_LOCATIONS, SUMMARY, REFERENCE_01lab, REFERENCE_01url, REFERENCE_02lab, REFERENCE_02url, REFERENCE_03lab, REFERENCE_03url, SECTION, PROGRAM_AREAS
- Full data with separate URL and label columns

---

## Implementation Checklist

### Phase 1: Setup & File Migration

- [ ] 1.1 Create directory structure
  - [ ] Create `app/data/dr_tracker/`
  - [ ] Create `app/services/dr_tracker/`
  - [ ] Create `app/templates/tools/dr_tracker/` (if needed for modals)

- [ ] 1.2 Copy VBA project file
  - [ ] Copy `legacy_code/ops_toolkit/src/data/daily_report/vbaProject.bin` to `app/data/dr_tracker/`

- [ ] 1.3 Copy preprompt file
  - [ ] Copy `legacy_code/ops_toolkit/src/data/daily_report/gpt4_dr2tracker_preprompt.txt` to `app/data/dr_tracker/`

- [ ] 1.4 Convert reference data to JSON
  - [ ] Create conversion script: `scripts/convert_dr_data.py`
  - [ ] Convert `idc_hazards.py` → `app/data/dr_tracker/idc_hazards.json`
  - [ ] Convert `program_areas.py` → `app/data/dr_tracker/program_areas.json`
  - [ ] Verify JSON structure and encoding

- [ ] 1.5 Update dependencies
  - [ ] Add `chardet>=5.2.0` to `requirements.txt`
  - [ ] Add `rapidfuzz>=3.6.0` to `requirements.txt`
  - [ ] Run `pip install -r requirements.txt`

### Phase 2: Backend Service Implementation

- [ ] 2.1 Create `app/services/dr_tracker/html_processor.py`
  - [ ] Implement `detect_file_encoding(file_bytes)`
  - [ ] Implement `parse_html(file_bytes, encoding)`
  - [ ] Implement `remove_unnecessary_html_attributes(soup)`
  - [ ] Implement `replace_safe_links(html_content)` (with text fragment removal)
  - [ ] Implement `sanitize_html_text(html_text)` (typographic character replacement)
  - [ ] Implement `extract_html_body(soup)`
  - [ ] Implement `remove_non_content_tags(html_text)`
  - [ ] Implement `remove_empty_lines(html_text)`
  - [ ] Implement `discard_disclaimer(html_text)`
  - [ ] Implement `discard_content_before_DR(html_text)`
  - [ ] Implement `remove_gphin(text)`
  - [ ] Create main function: `process_html_file(file_bytes) -> str`
  - [ ] Add unit tests for each function

- [ ] 2.2 Create `app/services/dr_tracker/hazard_matcher.py`
  - [ ] Implement `HazardMatcher` class
  - [ ] Implement `load_canonical_hazards()` method
  - [ ] Implement `exact_match(extracted_hazard)` method (case-insensitive)
  - [ ] Implement `fuzzy_match(extracted_hazard)` method (85% threshold)
  - [ ] Implement `match_hazard(extracted_hazard) -> Optional[str]` (combines exact + fuzzy)
  - [ ] Add unit tests with various hazard examples

- [ ] 2.3 Create `app/services/dr_tracker/models.py`
  - [ ] Define `DREntry` Pydantic model with all fields
  - [ ] Add field validators (date format, section codes, etc.)
  - [ ] Add `to_dataframe_row()` method for Excel export
  - [ ] Add `from_dict()` and `to_dict()` methods
  - [ ] Test model serialization/deserialization

- [ ] 2.4 Rebuild `app/services/dr_tracker/tracker_service.py`
  - [ ] Remove all old Discrepancy Report code
  - [ ] Implement `DRTrackerService` class initialization
  - [ ] Implement `_load_preprompt()` method
  - [ ] Implement `process_html_upload(file_bytes, timeout)` main pipeline
  - [ ] Implement `_call_openai(html_content, timeout)` with gpt-4.1
  - [ ] Implement `_parse_json_response(content)` to extract entries
  - [ ] Implement `_match_hazards(entries)` using HazardMatcher
  - [ ] Implement `_entries_to_dataframe(entries)` for full data sheet
  - [ ] Implement `_transform_for_flags_and_tags(df)` for sheet 1
  - [ ] Implement `_write_sheet(workbook, sheet_name, df)` helper
  - [ ] Implement `export_to_excel_with_macros(entries) -> bytes`
  - [ ] Implement `load_hazards() -> List[Dict]` for UI
  - [ ] Implement `load_program_areas() -> List[Dict]` for UI
  - [ ] Add error handling and logging throughout
  - [ ] Update `get_tracker_service()` singleton function

- [ ] 2.5 Update `app/services/dr_tracker/__init__.py`
  - [ ] Export new service and models
  - [ ] Add version information

### Phase 3: Routes Rebuild

- [ ] 3.1 Completely replace `app/routes/tools/dr_tracker.py`
  - [ ] Remove all old Discrepancy Report routes
  - [ ] Implement `index()` - Upload HTML file page (GET)
  - [ ] Implement `process()` - Process uploaded HTML file (POST)
    - [ ] Validate file type (.html, .htm)
    - [ ] Validate file size (5MB max)
    - [ ] Call `service.process_html_upload()`
    - [ ] Generate session_id
    - [ ] Store results in `_session_cache`
    - [ ] Return JSON response
  - [ ] Implement `edit(session_id)` - Display editable table (GET)
    - [ ] Load data from cache
    - [ ] Load hazards and program areas
    - [ ] Render editor template
  - [ ] Implement `update_entry(session_id)` - Update single entry (POST)
    - [ ] Validate session exists
    - [ ] Update entry in cache
    - [ ] Return success/error JSON
  - [ ] Implement `download(session_id)` - Download Excel file (GET)
    - [ ] Load entries from cache
    - [ ] Call `service.export_to_excel_with_macros()`
    - [ ] Return .xlsm file response
  - [ ] Add session cleanup mechanism (2-hour expiry)
  - [ ] Add comprehensive error handling
  - [ ] Add logging for all operations

- [ ] 3.2 Update blueprint registration
  - [ ] Verify blueprint is registered in `app/__init__.py`
  - [ ] Update URL prefix if needed

### Phase 4: Frontend Templates

- [ ] 4.1 Rebuild `app/templates/tools/dr_tracker.html`
  - [ ] Remove old text prompt interface
  - [ ] Add file upload form
    - [ ] File input with `.html, .htm` accept filter
    - [ ] File size validation (client-side)
    - [ ] Drag-and-drop support (optional enhancement)
  - [ ] Add processing status display
    - [ ] Loading spinner
    - [ ] Progress messages ("Sanitizing HTML...", "Extracting data...", "Matching hazards...")
  - [ ] Add information section
    - [ ] Daily Report format explanation
    - [ ] Sample HTML structure reference
    - [ ] Instructions for use
  - [ ] Implement JavaScript for upload handling
    - [ ] FormData submission
    - [ ] Status updates during processing
    - [ ] Redirect to editor on success
    - [ ] Error message display
  - [ ] Add page styling consistent with OpsToolKit theme

- [ ] 4.2 Create `app/templates/tools/dr_tracker_editor.html`
  - [ ] Create editable table structure
    - [ ] Headers: ENTRY_#, HAZARD, DATE, REPORTED_LOCATION, CITED_LOCATIONS, SUMMARY, REFERENCES, SECTION, PROGRAM_AREAS, Actions
    - [ ] Render all entries from session
    - [ ] Make ENTRY_# inline editable (text input)
    - [ ] Display HAZARD with badge + edit button
    - [ ] Display PROGRAM_AREAS with badge + edit button
    - [ ] Display references as clickable links
    - [ ] Add "Edit Full" button per row
  - [ ] Create HAZARD selection modal (Geolocation-style)
    - [ ] Search input field
    - [ ] Match count display
    - [ ] Selection count display
    - [ ] "Select All Visible" button
    - [ ] "Clear All" button
    - [ ] Scrollable checkbox list (400px height)
    - [ ] Save and Cancel buttons
  - [ ] Create PROGRAM_AREAS selection modal (similar to HAZARD)
    - [ ] Search input field
    - [ ] Match count display with acronym + name
    - [ ] Selection count display
    - [ ] "Select All Visible" button
    - [ ] "Clear All" button
    - [ ] Scrollable checkbox list
    - [ ] Save and Cancel buttons
  - [ ] Create full entry edit modal (optional)
    - [ ] All fields editable
    - [ ] Date picker for report_date
    - [ ] Text inputs for locations
    - [ ] Textarea for summary
    - [ ] Reference fields (url + label pairs)
  - [ ] Add action buttons
    - [ ] "Download Excel (.xlsm)" button (prominent)
    - [ ] "Reset All Changes" button (warning style)
    - [ ] "Back to Upload" button
  - [ ] Implement JavaScript functionality
    - [ ] Searchable dropdown filtering (like Geolocation)
    - [ ] Real-time search with debouncing
    - [ ] Select All Visible logic
    - [ ] Clear All logic
    - [ ] Selection count updates
    - [ ] Modal show/hide handlers
    - [ ] Save hazard/program area selections
    - [ ] AJAX calls to update backend
    - [ ] Inline editing for entry numbers
    - [ ] Download button handler
  - [ ] Add responsive design
    - [ ] Table scrolls horizontally on mobile
    - [ ] Modals are mobile-friendly
    - [ ] Touch-friendly buttons and inputs

- [ ] 4.3 Update/remove `app/templates/tools/dr_tracker_results.html`
  - [ ] Determine if needed (may merge into editor)
  - [ ] If keeping, update to show processing results
  - [ ] If removing, delete file

### Phase 5: Data Conversion

- [ ] 5.1 Create `scripts/convert_dr_data.py`
  - [ ] Import legacy data files
  - [ ] Parse `idc_hazards.py` structure
  - [ ] Convert to JSON format
  - [ ] Parse `program_areas.py` structure
  - [ ] Convert to JSON format
  - [ ] Write to `app/data/dr_tracker/` directory
  - [ ] Validate JSON output
  - [ ] Run conversion script
  - [ ] Verify generated JSON files

### Phase 6: Configuration Updates

- [ ] 6.1 Update `app/config.py`
  - [ ] Add `DR_TRACKER_MODEL = 'gpt-4.1'`
  - [ ] Add `DR_TRACKER_TIMEOUT = 120`
  - [ ] Add `DR_TRACKER_MAX_FILE_SIZE = 5 * 1024 * 1024`
  - [ ] Add `DR_TRACKER_VBA_PATH = 'app/data/dr_tracker/vbaProject.bin'`
  - [ ] Add `DR_TRACKER_SESSION_TIMEOUT = 7200` (2 hours)

- [ ] 6.2 Update environment configuration
  - [ ] Verify `OPENAI_API_KEY` is set
  - [ ] Add any new environment variables if needed

### Phase 7: Testing

- [ ] 7.1 Unit Tests
  - [ ] Test `html_processor.py` functions
    - [ ] Test encoding detection
    - [ ] Test Safe Links decoding
    - [ ] Test HTML sanitization
    - [ ] Test text replacement
  - [ ] Test `hazard_matcher.py`
    - [ ] Test exact matching (various cases)
    - [ ] Test fuzzy matching (threshold validation)
    - [ ] Test no-match scenarios
  - [ ] Test `models.py`
    - [ ] Test DREntry validation
    - [ ] Test serialization/deserialization
    - [ ] Test dataframe conversion
  - [ ] Test `tracker_service.py`
    - [ ] Mock OpenAI calls
    - [ ] Test JSON parsing
    - [ ] Test Excel generation
    - [ ] Test error handling

- [ ] 7.2 Integration Tests
  - [ ] Test complete upload → process → edit → download flow
  - [ ] Test session management and expiry
  - [ ] Test with real sample HTML files
  - [ ] Test with malformed HTML
  - [ ] Test with large files (near 5MB limit)
  - [ ] Test concurrent user sessions
  - [ ] Test error scenarios (OpenAI timeout, invalid JSON, missing fields)

- [ ] 7.3 Manual Testing
  - [ ] Upload valid Daily Report HTML
  - [ ] Verify entries are extracted correctly
  - [ ] Verify hazards are matched to canonical list
  - [ ] Test editing entries in the UI
  - [ ] Test searchable dropdowns for HAZARD and PROGRAM_AREAS
  - [ ] Test "Select All Visible" and "Clear All" buttons
  - [ ] Test entry number editing
  - [ ] Download Excel file
  - [ ] Verify Excel has two sheets with correct data
  - [ ] Verify VBA macros are embedded
  - [ ] Test Excel file in Microsoft Excel
  - [ ] Test session expiry behavior
  - [ ] Test error messages and user feedback

- [ ] 7.4 Edge Cases
  - [ ] Empty sections (e.g., "Highlight of the Day" with Nil)
  - [ ] Multiple events per location (3a, 3b numbering)
  - [ ] Special characters in summaries
  - [ ] Very long summaries
  - [ ] Missing references
  - [ ] Multiple hazards per entry
  - [ ] Unicode and international characters

### Phase 8: Documentation

- [ ] 8.1 Update user documentation
  - [ ] Create user guide for DR-Tracker Builder
  - [ ] Document HTML upload requirements
  - [ ] Document editing interface
  - [ ] Document Excel output format
  - [ ] Add screenshots/GIFs of workflow

- [ ] 8.2 Update developer documentation
  - [ ] Document service architecture
  - [ ] Document data models
  - [ ] Document API endpoints
  - [ ] Document session management
  - [ ] Add code examples

- [ ] 8.3 Update landing page
  - [ ] Update tool description on landing page
  - [ ] Update tool icon/badge if needed
  - [ ] Update tool category if needed

### Phase 9: Deployment

- [ ] 9.1 Code cleanup
  - [ ] Remove all commented-out old code
  - [ ] Remove unused imports
  - [ ] Format code with Black/autopep8
  - [ ] Run linter (ruff)
  - [ ] Fix any linting errors

- [ ] 9.2 Version control
  - [ ] Create backup branch for old implementation
  - [ ] Tag old version: `dr-tracker-v1-discrepancy-reports`
  - [ ] Commit new implementation with descriptive messages
  - [ ] Create feature branch: `feature/dr-tracker-daily-reports`

- [ ] 9.3 Pre-deployment checks
  - [ ] All tests passing
  - [ ] No console errors in browser
  - [ ] Mobile responsiveness verified
  - [ ] Cross-browser compatibility checked (Chrome, Firefox, Safari)
  - [ ] Performance profiling (large files)
  - [ ] Security review (file upload validation, session security)

- [ ] 9.4 Deployment
  - [ ] Merge to main branch
  - [ ] Deploy to staging environment
  - [ ] Run smoke tests on staging
  - [ ] Deploy to production
  - [ ] Monitor logs for errors
  - [ ] Verify tool is accessible

- [ ] 9.5 Post-deployment
  - [ ] Monitor user feedback
  - [ ] Monitor error logs
  - [ ] Track performance metrics
  - [ ] Document any issues found

---

## Detailed Implementation Phases

### Phase 1: Setup & File Migration (30 minutes)

#### Tasks

1. **Create Directory Structure**
   ```bash
   mkdir -p app/data/dr_tracker
   mkdir -p scripts
   ```

2. **Copy VBA Project File**
   ```bash
   cp legacy_code/ops_toolkit/src/data/daily_report/vbaProject.bin app/data/dr_tracker/
   ```

3. **Copy Preprompt File**
   ```bash
   cp legacy_code/ops_toolkit/src/data/daily_report/gpt4_dr2tracker_preprompt.txt app/data/dr_tracker/
   ```

4. **Create Conversion Script**
   ```python
   # scripts/convert_dr_data.py
   import json
   from pathlib import Path

   # Load legacy data
   # Convert to JSON format
   # Write to app/data/dr_tracker/
   ```

5. **Update Dependencies**
   ```bash
   echo "chardet>=5.2.0" >> requirements.txt
   echo "rapidfuzz>=3.6.0" >> requirements.txt
   pip install -r requirements.txt
   ```

#### Success Criteria

- [ ] All directories created
- [ ] VBA file copied and accessible
- [ ] Preprompt file copied and readable
- [ ] JSON conversion script working
- [ ] Dependencies installed

---

### Phase 2: Backend Service Implementation (4-5 hours)

#### 2.1 HTML Processor Module

**File**: `app/services/dr_tracker/html_processor.py`

**Functions to implement** (from legacy code):

```python
def detect_file_encoding(file_bytes: bytes) -> Tuple[str, float]:
    """Detect encoding using chardet."""
    result = chardet.detect(file_bytes)
    return result['encoding'], result['confidence']

def parse_html(file_bytes: bytes, encoding: str) -> BeautifulSoup:
    """Parse HTML with BeautifulSoup and lxml."""
    try:
        html_content = file_bytes.decode(encoding, errors="replace")
    except (UnicodeDecodeError, LookupError, TypeError):
        html_content = file_bytes.decode("utf-8", errors="replace")
    return BeautifulSoup(html_content, "lxml")

def remove_unnecessary_html_attributes(soup: BeautifulSoup) -> BeautifulSoup:
    """Remove all attributes except href in <a> tags."""
    # Implementation from legacy code lines 42-56

def replace_safe_links(html_content: str) -> str:
    """Replace Microsoft Safe Links and remove text fragments."""
    # Implementation from legacy code lines 102-127

def sanitize_html_text(html_text: str) -> str:
    """Replace typographic characters with ASCII equivalents."""
    # Implementation from legacy code lines 193-209

def extract_html_body(soup: BeautifulSoup) -> BeautifulSoup:
    """Extract <body> part of HTML."""
    # Implementation from legacy code lines 130-135

def remove_non_content_tags(html_text: str) -> str:
    """Discard tags without content."""
    # Implementation from legacy code lines 138-149

def remove_empty_lines(html_text: str) -> str:
    """Remove empty lines from HTML text."""
    # Implementation from legacy code lines 152-158

def discard_disclaimer(html_text: str) -> str:
    """Discard 'disclaimer' section and everything after."""
    # Implementation from legacy code lines 161-169

def discard_content_before_DR(html_text: str) -> str:
    """Discard content before 'review and risk assessment.'"""
    # Implementation from legacy code lines 172-181

def remove_gphin(text: str) -> str:
    """Remove 'GPHIN' text."""
    # Implementation from legacy code lines 184-188

def process_html_file(file_bytes: bytes) -> str:
    """Main pipeline: run all HTML processing steps."""
    encoding, confidence = detect_file_encoding(file_bytes)
    soup = parse_html(file_bytes, encoding)
    soup = remove_unnecessary_html_attributes(soup)
    body = extract_html_body(soup)
    body_html = str(body)
    body_html = replace_safe_links(body_html)
    body_html = sanitize_html_text(body_html)
    body_html = remove_non_content_tags(body_html)
    body_html = remove_empty_lines(body_html)
    body_html = discard_disclaimer(body_html)
    body_html = discard_content_before_DR(body_html)
    body_html = remove_gphin(body_html)
    return body_html
```

#### 2.2 Hazard Matcher Module

**File**: `app/services/dr_tracker/hazard_matcher.py`

```python
import json
from typing import Optional, List, Dict
from rapidfuzz import fuzz, process

class HazardMatcher:
    def __init__(self, hazards_json_path: str):
        self.canonical_hazards = self._load_hazards(hazards_json_path)
        self.hazard_names = [h['canonical_hazard'] for h in self.canonical_hazards]

    def _load_hazards(self, path: str) -> List[Dict]:
        with open(path, 'r') as f:
            return json.load(f)

    def exact_match(self, extracted_hazard: str) -> Optional[str]:
        """Try exact case-insensitive match."""
        for canonical in self.hazard_names:
            if extracted_hazard.lower() == canonical.lower():
                return canonical
        return None

    def fuzzy_match(self, extracted_hazard: str, threshold: int = 85) -> Optional[str]:
        """Try fuzzy match with threshold."""
        match = process.extractOne(
            extracted_hazard,
            self.hazard_names,
            scorer=fuzz.ratio,
            score_cutoff=threshold
        )
        return match[0] if match else None

    def match_hazard(self, extracted_hazard: str) -> Optional[str]:
        """Match hazard using exact then fuzzy matching."""
        # Try exact first
        exact = self.exact_match(extracted_hazard)
        if exact:
            return exact

        # Try fuzzy
        fuzzy = self.fuzzy_match(extracted_hazard)
        return fuzzy
```

#### 2.3 Data Models

**File**: `app/services/dr_tracker/models.py`

```python
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Tuple
from datetime import datetime

class DREntry(BaseModel):
    entry_number: str = Field(..., description="Entry number (e.g., '1', '3a', '3b')")
    hazard_list: List[str] = Field(default_factory=list, description="Matched canonical hazards")
    report_date: str = Field(..., description="Report date in mm/dd/yyyy format")
    reported_location: str = Field(..., description="Primary location reported")
    cited_locations: Optional[List[str]] = Field(None, description="Additional cited locations")
    summary: str = Field(..., description="Summary text")
    summary_title: Optional[str] = Field(None, description="Optional summary title")
    is_update: bool = Field(False, description="Whether this is an update")
    references: List[Tuple[str, str]] = Field(default_factory=list, description="[(url, label), ...]")
    report_section: str = Field(..., description="Section code: hod, dme, int, rpg")
    program_areas: List[str] = Field(default_factory=list, description="Assigned program areas")

    @validator('report_section')
    def validate_section(cls, v):
        valid_sections = ['hod', 'dme', 'int', 'rpg']
        if v not in valid_sections:
            raise ValueError(f"Section must be one of {valid_sections}")
        return v

    @validator('report_date')
    def validate_date_format(cls, v):
        try:
            datetime.strptime(v, '%m/%d/%Y')
        except ValueError:
            raise ValueError("Date must be in mm/dd/yyyy format")
        return v

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = self.dict()
        # Convert tuples to lists for JSON serialization
        data['references'] = [[url, label] for url, label in self.references]
        return data

    @classmethod
    def from_dict(cls, data: dict) -> 'DREntry':
        """Create instance from dictionary."""
        if 'references' in data:
            data['references'] = [tuple(ref) for ref in data['references']]
        return cls(**data)
```

#### 2.4 Tracker Service Rebuild

**File**: `app/services/dr_tracker/tracker_service.py`

```python
import logging
import time
import json
from typing import Dict, Any, List
from datetime import datetime
from io import BytesIO
import pandas as pd
import xlsxwriter
from openai import OpenAI
from flask import current_app

from .html_processor import process_html_file
from .hazard_matcher import HazardMatcher
from .models import DREntry

logger = logging.getLogger(__name__)

class DRTrackerService:
    def __init__(self):
        self.client = None
        self.model = 'gpt-4.1'
        self.hazard_matcher = None
        self.preprompt = None

    def _ensure_initialized(self):
        """Lazy initialization of OpenAI client and resources."""
        if self.client is None:
            api_key = current_app.config.get('OPENAI_API_KEY')
            if not api_key:
                raise ValueError("OPENAI_API_KEY not configured")
            self.client = OpenAI(api_key=api_key)
            self.model = current_app.config.get('DR_TRACKER_MODEL', 'gpt-4.1')

        if self.hazard_matcher is None:
            hazards_path = 'app/data/dr_tracker/idc_hazards.json'
            self.hazard_matcher = HazardMatcher(hazards_path)

        if self.preprompt is None:
            self.preprompt = self._load_preprompt()

    def _load_preprompt(self) -> str:
        """Load system preprompt from file."""
        with open('app/data/dr_tracker/gpt4_dr2tracker_preprompt.txt', 'r') as f:
            return f.read()

    def process_html_upload(self, file_bytes: bytes, timeout: int = 120) -> Dict[str, Any]:
        """
        Complete pipeline: HTML → OpenAI → Hazard Matching

        Returns:
            {
                'success': bool,
                'entries': List[DREntry],
                'metadata': {...},
                'error': str (if failed)
            }
        """
        # Implementation details...
        pass

    def export_to_excel_with_macros(self, entries: List[DREntry]) -> bytes:
        """Generate .xlsm file with two sheets and VBA macros."""
        # Implementation details...
        pass

    def load_hazards(self) -> List[Dict]:
        """Load canonical hazards for UI."""
        with open('app/data/dr_tracker/idc_hazards.json', 'r') as f:
            return json.load(f)

    def load_program_areas(self) -> List[Dict]:
        """Load program areas for UI."""
        with open('app/data/dr_tracker/program_areas.json', 'r') as f:
            return json.load(f)
```

---

### Phase 3: Routes Rebuild (2 hours)

**File**: `app/routes/tools/dr_tracker.py`

Complete replacement of existing file with new implementation handling:
- HTML file uploads
- Session-based data storage
- Entry editing
- Excel export with macros

---

### Phase 4: Frontend Templates (4-5 hours)

#### Template Structure

1. **Upload Page** (`dr_tracker.html`)
   - File upload form
   - Processing status display
   - Instructions and information

2. **Editor Page** (`dr_tracker_editor.html`)
   - Editable table with all entries
   - Searchable multi-select modals for HAZARD and PROGRAM_AREAS
   - Download button

---

### Phase 5: Testing (2-3 hours)

#### Test Coverage

- Unit tests for all service modules
- Integration tests for complete workflow
- Manual testing with real HTML files
- Edge case testing

---

## File Structure

```
OpsToolKit/
├── app/
│   ├── data/
│   │   └── dr_tracker/
│   │       ├── gpt4_dr2tracker_preprompt.txt
│   │       ├── idc_hazards.json
│   │       ├── program_areas.json
│   │       └── vbaProject.bin
│   ├── routes/
│   │   └── tools/
│   │       └── dr_tracker.py (REBUILT)
│   ├── services/
│   │   └── dr_tracker/
│   │       ├── __init__.py
│   │       ├── tracker_service.py (REBUILT)
│   │       ├── html_processor.py (NEW)
│   │       ├── hazard_matcher.py (NEW)
│   │       └── models.py (NEW)
│   └── templates/
│       └── tools/
│           ├── dr_tracker.html (REBUILT)
│           └── dr_tracker_editor.html (NEW)
├── scripts/
│   └── convert_dr_data.py (NEW)
├── docs/
│   └── dr_tracker_builder_new_implementation.md (THIS FILE)
└── legacy_code/
    └── ops_toolkit/
        └── src/
            ├── daily_report/
            │   └── daily_report.py (REFERENCE ONLY)
            └── data/
                └── daily_report/
                    ├── gpt4_dr2tracker_preprompt.txt
                    ├── idc_hazards.py
                    ├── program_areas.py
                    └── vbaProject.bin
```

---

## Technical Specifications

### OpenAI Integration

**Model**: gpt-4.1
**Timeout**: 120 seconds
**System Prompt**: Loaded from `gpt4_dr2tracker_preprompt.txt`
**Response Format**: JSON array of entry dictionaries

### Hazard Matching Algorithm

1. **Exact Match** (case-insensitive)
   - Direct string comparison
   - Return immediately if found

2. **Fuzzy Match** (if exact fails)
   - Use rapidfuzz library
   - Scoring method: `fuzz.ratio`
   - Threshold: 85%
   - Return best match or None

### Session Management

- **Storage**: In-memory dictionary `_session_cache`
- **Timeout**: 2 hours (7200 seconds)
- **Cleanup**: Background task or on-access check
- **Session ID**: UUID v4

### Excel Export Specifications

**File Format**: `.xlsm` (Macro-enabled workbook)
**Library**: xlsxwriter
**VBA Macros**: Embedded from `vbaProject.bin`

**Sheet 1: Flags_and_Tags**
```
Columns (9):
- ENTRY_#
- HAZARD
- DATE
- REPORTED_LOCATION
- SUMMARY
- REFERENCE_01hlk (=HYPERLINK formula)
- REFERENCE_02hlk (=HYPERLINK formula)
- REFERENCE_03hlk (=HYPERLINK formula)
- PROGRAM_AREAS
```

**Sheet 2: DR_tracker_PBI**
```
Columns (14):
- ENTRY_#
- HAZARD
- DATE
- REPORTED_LOCATION
- CITED_LOCATIONS
- SUMMARY
- REFERENCE_01lab
- REFERENCE_01url
- REFERENCE_02lab
- REFERENCE_02url
- REFERENCE_03lab
- REFERENCE_03url
- SECTION
- PROGRAM_AREAS
```

### Data Validation Rules

- **File Type**: `.html` or `.htm` only
- **File Size**: Maximum 5MB
- **Entry Number**: Any string format (e.g., "1", "3a", "3b")
- **Report Date**: Must be `mm/dd/yyyy` format
- **Section Code**: Must be one of: `hod`, `dme`, `int`, `rpg`
- **References**: Maximum 3 per entry
- **Hazards**: Multiple allowed (list)
- **Program Areas**: Multiple allowed (list)

---

## Testing Strategy

### Unit Tests

**Module**: `test_html_processor.py`
- Test encoding detection with various files
- Test Safe Links decoding
- Test HTML sanitization
- Test special character replacement

**Module**: `test_hazard_matcher.py`
- Test exact matching (case variations)
- Test fuzzy matching (threshold validation)
- Test no-match scenarios
- Test performance with large hazard list

**Module**: `test_models.py`
- Test DREntry validation
- Test date format validation
- Test section code validation
- Test serialization/deserialization

**Module**: `test_tracker_service.py`
- Mock OpenAI API calls
- Test JSON parsing (valid and invalid)
- Test hazard matching integration
- Test Excel generation
- Test error handling

### Integration Tests

**Scenario**: Complete workflow
```python
def test_complete_workflow():
    # 1. Upload HTML file
    # 2. Verify processing succeeds
    # 3. Verify entries extracted
    # 4. Verify hazards matched
    # 5. Edit entry
    # 6. Download Excel
    # 7. Verify Excel contents
```

**Scenario**: Session management
```python
def test_session_expiry():
    # 1. Create session
    # 2. Wait for expiry
    # 3. Verify session cleaned up
```

**Scenario**: Error handling
```python
def test_openai_timeout():
    # Simulate OpenAI timeout
    # Verify error message
    # Verify graceful degradation
```

### Manual Testing Checklist

- [ ] Upload valid HTML file
- [ ] Upload invalid file (non-HTML)
- [ ] Upload oversized file (>5MB)
- [ ] Verify entries display correctly
- [ ] Edit entry number
- [ ] Edit hazards using searchable dropdown
- [ ] Edit program areas using searchable dropdown
- [ ] Test search functionality (filter hazards)
- [ ] Test "Select All Visible"
- [ ] Test "Clear All"
- [ ] Download Excel
- [ ] Open Excel in Microsoft Excel
- [ ] Verify Sheet 1 has hyperlink formulas
- [ ] Verify Sheet 2 has full data
- [ ] Verify VBA macros work
- [ ] Test on mobile device
- [ ] Test in different browsers

---

## Dependencies

### Python Packages

```txt
# Existing
Flask>=3.0.0
openai>=1.12.0
pandas>=2.0.0
xlsxwriter>=3.1.0
beautifulsoup4>=4.12.0
lxml>=4.9.0
pydantic>=2.0.0

# New
chardet>=5.2.0       # HTML encoding detection
rapidfuzz>=3.6.0     # Fuzzy string matching
```

### JavaScript Libraries

- **Bootstrap 5** (already included)
- **Bootstrap Icons** (already included)
- No additional JS libraries needed (using vanilla JS for Geolocation-style search)

### External Services

- **OpenAI API** (gpt-4.1 model access required)

---

## Estimated Timeline

| Phase | Task | Estimated Time |
|-------|------|----------------|
| 1 | Setup & File Migration | 30 minutes |
| 2 | Backend Service Implementation | 4-5 hours |
| 3 | Routes Rebuild | 2 hours |
| 4 | Frontend Templates | 4-5 hours |
| 5 | Data Conversion | 30 minutes |
| 6 | Configuration Updates | 15 minutes |
| 7 | Testing | 2-3 hours |
| 8 | Documentation | 1-2 hours |
| 9 | Deployment | 1 hour |
| **Total** | **15-19 hours** |

---

## Notes and Considerations

### Performance

- **HTML Processing**: Should complete in <1 second for typical files
- **OpenAI Extraction**: 30-60 seconds depending on file complexity
- **Hazard Matching**: <1 second for all entries
- **Excel Generation**: <2 seconds for typical reports (50-100 entries)

### Security

- **File Upload**: Validate file type and size before processing
- **Session Management**: Use secure random UUIDs
- **OpenAI API**: Sanitize HTML before sending (no PII if possible)
- **Error Messages**: Don't expose sensitive information

### Scalability

- **Session Storage**: Consider Redis for multi-server deployments
- **File Size**: 5MB limit prevents memory issues
- **Concurrent Users**: Session cache is thread-safe
- **OpenAI Rate Limits**: Consider implementing queue system

### Maintenance

- **Hazard List Updates**: JSON files can be easily updated
- **Program Areas Updates**: JSON files can be easily updated
- **VBA Macros**: Requires Excel to generate new `vbaProject.bin`
- **Preprompt Updates**: Text file can be edited without code changes

---

## Success Criteria

This implementation will be considered successful when:

- [ ] All checklist items are completed
- [ ] All tests pass (unit, integration, manual)
- [ ] Users can upload HTML and get structured Excel output
- [ ] Hazard matching achieves >90% accuracy
- [ ] Processing completes within timeout
- [ ] Excel files open correctly with working macros
- [ ] UI is intuitive and responsive
- [ ] No critical bugs or errors
- [ ] Documentation is complete and accurate
- [ ] Tool is deployed and accessible to users

---

## Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2025-10-24 | 1.0 | Initial implementation plan created |

---

**Document Status**: Ready for Implementation
**Next Steps**: Begin Phase 1 - Setup & File Migration
