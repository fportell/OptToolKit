"""
Geolocation Service for OpsToolKit.

This service provides country/region lookup and standardized area attribution
for reporting purposes. Based on the original GPHIN geolocation tool.

Per original functionality:
- Load geolocation database with UN M49 region standards
- Determine area attribution based on selected countries
- Format affected locations for reporting
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
import pandas as pd


class GeolocationService:
    """
    Service for geographic area attribution and reporting.

    Provides functionality to:
    - Load geolocation database
    - Determine appropriate area attribution
    - Format lists of affected locations
    """

    def __init__(self, db_path: Path):
        """
        Initialize the geolocation service.

        Args:
            db_path: Path to the geolocations_db.tsv file
        """
        self.db_path = db_path
        self.db = self._load_database()

    def _load_database(self) -> pd.DataFrame:
        """
        Load the geolocation database from TSV file.

        The database contains country names from Canadian Government sources
        and regions/continents from UN M49 standards.

        Returns:
            pd.DataFrame: Cleaned geolocation database
        """
        db = pd.read_csv(str(self.db_path), sep="\t")

        # Remove Canadian province data
        db = db.drop(columns=['CAN_PROV'])

        # Remove duplicates (from Canadian provinces)
        db = db.drop_duplicates()

        return db

    def get_all_countries(self) -> List[str]:
        """
        Get list of all countries in the database.

        Returns:
            List[str]: Sorted list of country names
        """
        return sorted(self.db['COUNTRY'].tolist())

    def get_country_data(self, countries: List[str]) -> pd.DataFrame:
        """
        Get data for selected countries.

        Args:
            countries: List of country names

        Returns:
            pd.DataFrame: Filtered database with selected countries
        """
        return self.db[self.db['COUNTRY'].isin(countries)]

    def determine_area_attribution(self, countries: List[str]) -> str:
        """
        Determine the area attribution for reporting based on data standards rules.

        This function applies GPHIN area attribution logic:
        - Single country: Use country name
        - Same region: Use region name
        - Same continent: Use continent name
        - All continents: "Worldwide"
        - Otherwise: "Multiregional"

        Args:
            countries: List of selected country names

        Returns:
            str: Area attribution string for reporting purposes
        """
        if not countries:
            return ""

        if len(countries) == 1:
            return countries[0]

        filtered_df = self.get_country_data(countries)
        unique_regions = filtered_df['REGION'].dropna().unique()
        unique_continents = filtered_df['CONTINENT'].dropna().unique()

        # Determine area attribution
        if len(unique_regions) == 1:
            return unique_regions[0]
        elif len(unique_continents) == 1:
            return unique_continents[0]
        elif set(unique_continents) == {
            "Africa",
            "Asia",
            "Europe",
            "Oceania",
            "Americas"
        }:
            return "Worldwide"
        else:
            return "Multiregional"

    def format_affected_locations(self, countries: List[str]) -> str:
        """
        Format a list of countries into a human-readable string.

        This function creates properly formatted text for listing affected locations
        in reports, using proper English grammar for conjunctions.

        Args:
            countries: Alphabetically sorted list of country names

        Returns:
            str: Formatted string for affected locations

        Examples:
            - ["Canada"] → "Canada"
            - ["Canada", "USA"] → "Canada and USA"
            - ["Canada", "Mexico", "USA"] → "Canada, Mexico, and USA"
        """
        if not countries:
            return ""

        sorted_countries = sorted(countries)

        if len(sorted_countries) == 1:
            return sorted_countries[0]
        elif len(sorted_countries) == 2:
            return " and ".join(sorted_countries)
        else:
            return ", ".join(sorted_countries[:-1]) + \
                   ", and " + \
                   sorted_countries[-1]

    def process_selection(self, countries: List[str]) -> Dict[str, Any]:
        """
        Process a country selection and generate reporting data.

        Args:
            countries: List of selected country names

        Returns:
            Dict with keys:
                - countries: List of selected countries (sorted)
                - country_data: DataFrame with country details
                - area_attribution: String for area reporting
                - affected_locations: Formatted string of locations
        """
        sorted_countries = sorted(countries)
        country_data = self.get_country_data(sorted_countries)
        area_attribution = self.determine_area_attribution(sorted_countries)
        affected_locations = self.format_affected_locations(sorted_countries)

        return {
            'countries': sorted_countries,
            'country_data': country_data,
            'area_attribution': area_attribution,
            'affected_locations': affected_locations
        }
