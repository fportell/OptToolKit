"""
Query Processing Service for DR Knowledge Chatbot.

Handles query parsing, filter extraction, and query enhancement.
"""

import logging
import re
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ParsedQuery:
    """Parsed query with extracted filters."""
    original: str
    enhanced: str
    filters: Dict[str, Any]


class QueryProcessor:
    """Process and enhance user queries."""

    def __init__(self):
        """Initialize query processor."""
        self.disease_aliases = {
            'covid': 'covid-19',
            'coronavirus': 'covid-19',
            'sars-cov-2': 'covid-19',
            'monkeypox': 'mpox',
        }

    def parse_query(self, query: str) -> ParsedQuery:
        """
        Parse user query and extract filters.

        Args:
            query: User query string

        Returns:
            ParsedQuery with enhanced query and filters
        """
        filters = self.extract_filters(query)
        enhanced = self._enhance_query(query)

        return ParsedQuery(
            original=query,
            enhanced=enhanced,
            filters=filters
        )

    def extract_filters(self, query: str) -> Dict[str, Any]:
        """
        Extract metadata filters from query.

        Examples:
        - "measles in 2025" → {"date_from": "2025-01-01", "date_to": "2025-12-31"}
        - "recent ebola" → {"date_from": "2024-01-01"}
        - "mpox in USA" → {"location_contains": "united states"}

        Args:
            query: User query

        Returns:
            Filter dictionary
        """
        filters = {}
        query_lower = query.lower()

        # Extract time-based filters
        filters.update(self._extract_time_filters(query_lower))

        # Extract location filters
        location = self._extract_location(query_lower)
        if location:
            filters['location_contains'] = location

        # Extract disease/hazard
        hazard = self._extract_hazard(query_lower)
        if hazard:
            filters['hazard_normalized'] = hazard

        return filters

    def _extract_time_filters(self, query: str) -> Dict[str, str]:
        """Extract temporal filters from query."""
        filters = {}
        today = datetime.now()

        # Recent (last 2 years)
        if any(word in query for word in ['recent', 'latest', 'current']):
            filters['date_from'] = (today - timedelta(days=730)).strftime('%Y-%m-%d')
            return filters

        # This year
        if 'this year' in query or str(today.year) in query:
            filters['date_from'] = f"{today.year}-01-01"
            filters['date_to'] = f"{today.year}-12-31"
            return filters

        # Last year
        if 'last year' in query or str(today.year - 1) in query:
            year = today.year - 1
            filters['date_from'] = f"{year}-01-01"
            filters['date_to'] = f"{year}-12-31"
            return filters

        # Specific year (YYYY pattern) - check this BEFORE month patterns
        year_match = re.search(r'\b(20\d{2})\b', query)
        if year_match:
            year = year_match.group(1)
            filters['date_from'] = f"{year}-01-01"
            filters['date_to'] = f"{year}-12-31"
            return filters

        # Month name without explicit year - assume CURRENT year
        month_names = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4,
            'may': 5, 'june': 6, 'july': 7, 'august': 8,
            'september': 9, 'october': 10, 'november': 11, 'december': 12
        }

        for month_name, month_num in month_names.items():
            if month_name in query:
                # Found month without year - use current year
                year = today.year
                # Get first and last day of that month
                if month_num == 12:
                    next_month_year = year + 1
                    next_month = 1
                else:
                    next_month_year = year
                    next_month = month_num + 1

                filters['date_from'] = f"{year}-{month_num:02d}-01"
                # Last day of month = first day of next month - 1 day
                last_day = (datetime(next_month_year, next_month, 1) - timedelta(days=1)).day
                filters['date_to'] = f"{year}-{month_num:02d}-{last_day:02d}"

                logger.info(f"Detected month '{month_name}' without year - using {year}: {filters['date_from']} to {filters['date_to']}")
                return filters

        # Last N months
        months_match = re.search(r'last (\d+) months?', query)
        if months_match:
            months = int(months_match.group(1))
            filters['date_from'] = (today - timedelta(days=months*30)).strftime('%Y-%m-%d')
            return filters

        return filters

    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query."""
        # Common location patterns
        location_patterns = [
            r'in (\w+(?:\s+\w+)*?)(?:\s|$|,)',
            r'from (\w+(?:\s+\w+)*?)(?:\s|$|,)',
        ]

        for pattern in location_patterns:
            match = re.search(pattern, query)
            if match:
                location = match.group(1).strip()
                # Filter out common non-location words
                if location not in ['the', 'a', 'an', 'this', 'that', 'these', 'those']:
                    return location

        return None

    def _extract_hazard(self, query: str) -> Optional[str]:
        """Extract disease/hazard from query."""
        # Check for aliases
        for alias, canonical in self.disease_aliases.items():
            if alias in query:
                return canonical

        # Common disease patterns
        diseases = [
            'measles', 'mpox', 'monkeypox', 'cholera', 'ebola', 'dengue',
            'pertussis', 'covid-19', 'influenza', 'malaria', 'tuberculosis',
            'chikungunya', 'zika', 'yellow fever', 'polio'
        ]

        for disease in diseases:
            if disease in query:
                return disease

        return None

    def _enhance_query(self, query: str) -> str:
        """Enhance query with synonyms and expansions."""
        enhanced = query.lower()

        # Expand abbreviations
        enhancements = {
            'covid': 'covid-19 coronavirus sars-cov-2',
            'mpox': 'mpox monkeypox',
            'usa': 'united states america',
            'uk': 'united kingdom britain',
        }

        for term, expansion in enhancements.items():
            if term in enhanced:
                enhanced += f" {expansion}"

        return enhanced
