"""
Hazard Matching Module for DR-Tracker.

Matches extracted hazards from HTML to canonical hazard list using
exact and fuzzy matching algorithms with support for hierarchical
hazards and variant terms.
"""

import json
import logging
from typing import Optional, List, Dict, Tuple
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


class HazardMatcher:
    """
    Matches extracted hazards to canonical hazard list.

    Supports hierarchical hazards with parent-child relationships
    and variant terms. Uses two-stage matching:
    1. Exact match (case-insensitive) against canonical names and variants
    2. Fuzzy match with 85% threshold against canonical names and variants

    Returns format:
    - Simple hazards: "Hazard Name"
    - Child hazards: "Parent::Child"
    """

    def __init__(self, hazards_json_path: str):
        """
        Initialize hazard matcher with hierarchical hazard list.

        Args:
            hazards_json_path: Path to idc_hazards_hierarchical.json file
        """
        self.raw_hazards = self._load_hazards(hazards_json_path)
        self.matchable_items = self._flatten_hierarchical_hazards(self.raw_hazards)

        # Build search index for efficient matching
        self._build_search_index()

        logger.info(f"Loaded {len(self.matchable_items)} matchable hazards from {len(self.raw_hazards)} entries")

    def _load_hazards(self, path: str) -> List[Dict]:
        """
        Load hierarchical hazards from JSON file.

        Args:
            path: Path to JSON file

        Returns:
            List of hazard dictionaries

        Raises:
            FileNotFoundError: If hazards file not found
            json.JSONDecodeError: If JSON is invalid
        """
        try:
            with open(path, 'r', encoding='utf-8') as f:
                hazards = json.load(f)
            logger.debug(f"Successfully loaded hazards from {path}")
            return hazards
        except FileNotFoundError:
            logger.error(f"Hazards file not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in hazards file: {e}")
            raise

    def _flatten_hierarchical_hazards(self, hazards: List[Dict]) -> List[Dict]:
        """
        Flatten hierarchical hazards into matchable items list.

        Rules:
        - If hazard has no children: add as-is
        - If hazard has children: add ONLY the children (not parent)
        - Children get display_name as "Parent::Child"

        Args:
            hazards: Raw hierarchical hazard list

        Returns:
            List of matchable hazard dictionaries with structure:
            {
                "canonical_hazard": str,
                "parent": Optional[str],
                "variants": List[str],
                "display_name": str,
                "all_match_terms": List[str]  # canonical + variants for matching
            }
        """
        matchable = []

        for hazard in hazards:
            canonical = hazard.get('canonical_hazard', '')
            children = hazard.get('child')
            variants = hazard.get('variant') or []

            # Ensure variants is a list
            if not isinstance(variants, list):
                variants = []

            if children and isinstance(children, list):
                # Has children - add only children
                for child in children:
                    child_canonical = child.get('canonical_hazard', '')
                    child_variants = child.get('variant') or []

                    # Ensure child variants is a list
                    if not isinstance(child_variants, list):
                        child_variants = []

                    # Create display name as Parent::Child
                    display_name = f"{canonical}::{child_canonical}"

                    # Combine all terms for matching (canonical + variants)
                    all_match_terms = [child_canonical] + child_variants

                    matchable.append({
                        'canonical_hazard': child_canonical,
                        'parent': canonical,
                        'variants': child_variants,
                        'display_name': display_name,
                        'all_match_terms': all_match_terms
                    })
            else:
                # No children - add as simple hazard
                display_name = canonical
                all_match_terms = [canonical] + variants

                matchable.append({
                    'canonical_hazard': canonical,
                    'parent': None,
                    'variants': variants,
                    'display_name': display_name,
                    'all_match_terms': all_match_terms
                })

        return matchable

    def _build_search_index(self):
        """
        Build search index for efficient matching.

        Creates:
        - display_names: List of display names for UI
        - term_to_hazard: Dict mapping each match term (lowercase) to hazard item
        - all_terms: List of all searchable terms for fuzzy matching
        """
        self.display_names = []
        self.term_to_hazard = {}  # lowercase term -> hazard item
        self.all_terms = []  # All searchable terms

        for item in self.matchable_items:
            display_name = item['display_name']
            self.display_names.append(display_name)

            # Map each match term to this hazard
            for term in item['all_match_terms']:
                term_lower = term.lower().strip()
                if term_lower:
                    # Store term -> hazard mapping
                    if term_lower not in self.term_to_hazard:
                        self.term_to_hazard[term_lower] = item
                    self.all_terms.append(term)

        logger.debug(f"Built search index with {len(self.term_to_hazard)} unique terms")

    def exact_match(self, extracted_hazard: str) -> Optional[str]:
        """
        Try exact case-insensitive match against canonical names and variants.

        Args:
            extracted_hazard: Hazard string extracted from HTML

        Returns:
            Display name (e.g., "Parent::Child" or "Hazard") if match found, None otherwise
        """
        extracted_lower = extracted_hazard.lower().strip()

        # Look up in term index
        if extracted_lower in self.term_to_hazard:
            matched_item = self.term_to_hazard[extracted_lower]
            display_name = matched_item['display_name']
            logger.debug(f"Exact match: '{extracted_hazard}' -> '{display_name}'")
            return display_name

        return None

    def fuzzy_match(self, extracted_hazard: str, threshold: int = 85) -> Optional[str]:
        """
        Try fuzzy match with threshold using rapidfuzz against all searchable terms.

        Uses fuzz.ratio scorer which compares full strings.

        Args:
            extracted_hazard: Hazard string extracted from HTML
            threshold: Minimum similarity score (0-100, default: 85)

        Returns:
            Display name if match found, None otherwise
        """
        extracted_stripped = extracted_hazard.strip()

        # Use rapidfuzz to find best match across all terms
        match = process.extractOne(
            extracted_stripped,
            self.all_terms,
            scorer=fuzz.ratio,
            score_cutoff=threshold
        )

        if match:
            matched_term, score, _ = match
            # Look up which hazard this term belongs to
            matched_term_lower = matched_term.lower().strip()
            if matched_term_lower in self.term_to_hazard:
                matched_item = self.term_to_hazard[matched_term_lower]
                display_name = matched_item['display_name']
                logger.debug(f"Fuzzy match: '{extracted_hazard}' -> '{display_name}' via term '{matched_term}' (score: {score:.1f})")
                return display_name

        return None

    def match_hazard(self, extracted_hazard: str) -> Optional[str]:
        """
        Match hazard using exact then fuzzy matching.

        This is the main entry point for hazard matching.

        Args:
            extracted_hazard: Hazard string extracted from HTML

        Returns:
            Display name (e.g., "Parent::Child" or "Hazard") if match found, None otherwise
        """
        if not extracted_hazard or not extracted_hazard.strip():
            logger.warning("Empty hazard string provided")
            return None

        # Try exact match first (faster)
        exact = self.exact_match(extracted_hazard)
        if exact:
            return exact

        # Try fuzzy match
        fuzzy = self.fuzzy_match(extracted_hazard)
        if fuzzy:
            return fuzzy

        logger.warning(f"No match found for hazard: '{extracted_hazard}'")
        return None

    def match_hazards(self, extracted_hazards: List[str]) -> List[str]:
        """
        Match multiple hazards at once.

        Args:
            extracted_hazards: List of hazard strings

        Returns:
            List of matched display names (empty strings filtered out)
        """
        matched = []

        for hazard in extracted_hazards:
            match = self.match_hazard(hazard)
            if match:
                matched.append(match)

        logger.info(f"Matched {len(matched)}/{len(extracted_hazards)} hazards")
        return matched

    def get_all_hazards(self) -> List[str]:
        """
        Get list of all display names.

        Useful for UI dropdowns.

        Returns:
            List of display names
        """
        return self.display_names.copy()

    def get_matchable_items(self) -> List[Dict]:
        """
        Get list of all matchable items with full metadata.

        Useful for UI rendering with variants and parent info.

        Returns:
            List of matchable item dictionaries
        """
        return self.matchable_items.copy()

    def search_hazards(self, query: str, limit: int = 10) -> List[str]:
        """
        Search for hazards matching a query string.

        Searches across canonical names and variants.

        Useful for autocomplete/search functionality in UI.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of matching display names
        """
        if not query or not query.strip():
            return []

        query_lower = query.lower().strip()

        # Get all items that match the query in any of their terms
        matches = []
        for item in self.matchable_items:
            # Check if query matches any term
            for term in item['all_match_terms']:
                if query_lower in term.lower():
                    matches.append(item['display_name'])
                    break  # Found match, move to next item

        # If we have enough matches, return those
        if len(matches) >= limit:
            return matches[:limit]

        # Otherwise, use fuzzy matching to fill remaining slots
        remaining = limit - len(matches)
        if remaining > 0:
            fuzzy_matches = process.extract(
                query.strip(),
                self.all_terms,
                scorer=fuzz.partial_ratio,
                limit=limit
            )

            # Add fuzzy matches that aren't already in matches
            for matched_term, score, _ in fuzzy_matches:
                matched_term_lower = matched_term.lower().strip()
                if matched_term_lower in self.term_to_hazard:
                    matched_item = self.term_to_hazard[matched_term_lower]
                    display_name = matched_item['display_name']
                    if display_name not in matches:
                        matches.append(display_name)
                        if len(matches) >= limit:
                            break

        return matches[:limit]


def create_hazard_matcher(hazards_json_path: str = 'app/data/dr_tracker/idc_hazards_hierarchical.json') -> HazardMatcher:
    """
    Factory function to create a HazardMatcher instance.

    Args:
        hazards_json_path: Path to hierarchical hazards JSON file

    Returns:
        HazardMatcher instance
    """
    return HazardMatcher(hazards_json_path)
