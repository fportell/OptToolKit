"""
DR-Tracker Builder Service Package.

Complete rebuild for Daily Report (health surveillance) processing.
"""

from .tracker_service import DRTrackerService, get_tracker_service
from .models import DREntry, ProcessingResult
from .hazard_matcher import HazardMatcher
from .html_processor import process_html_file

__all__ = [
    'DRTrackerService',
    'get_tracker_service',
    'DREntry',
    'ProcessingResult',
    'HazardMatcher',
    'process_html_file'
]

__version__ = '2.0.0'  # Version 2.0: Daily Report processing (replaced Discrepancy Reports)
