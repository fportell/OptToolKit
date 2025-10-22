"""
EXIF Data Extraction for Geolocation Tool.

Extracts GPS coordinates and metadata from image EXIF data.
Per FR-006: Extract GPS data from JPEG/PNG images for map visualization.
"""

import logging
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from datetime import datetime

logger = logging.getLogger(__name__)


class ExifExtractor:
    """
    Extract and process EXIF data from images.

    Supports JPEG and PNG formats with EXIF metadata.
    """

    @staticmethod
    def _get_decimal_coordinates(gps_info: Dict) -> Optional[Tuple[float, float]]:
        """
        Convert GPS coordinates from EXIF format to decimal degrees.

        Args:
            gps_info: Dictionary of GPS tags from EXIF

        Returns:
            tuple: (latitude, longitude) in decimal degrees, or None if invalid
        """
        try:
            # Get latitude
            lat_ref = gps_info.get('GPSLatitudeRef')
            lat = gps_info.get('GPSLatitude')

            # Get longitude
            lon_ref = gps_info.get('GPSLongitudeRef')
            lon = gps_info.get('GPSLongitude')

            if not all([lat_ref, lat, lon_ref, lon]):
                return None

            # Convert to decimal degrees
            def convert_to_degrees(value):
                """Convert GPS coordinate tuple to decimal degrees."""
                d = float(value[0])
                m = float(value[1])
                s = float(value[2])
                return d + (m / 60.0) + (s / 3600.0)

            latitude = convert_to_degrees(lat)
            if lat_ref == 'S':
                latitude = -latitude

            longitude = convert_to_degrees(lon)
            if lon_ref == 'W':
                longitude = -longitude

            return (latitude, longitude)

        except (KeyError, ValueError, TypeError, ZeroDivisionError) as e:
            logger.error(f"Error converting GPS coordinates: {e}")
            return None

    @staticmethod
    def _get_gps_info(exif_data: Dict) -> Dict[str, Any]:
        """
        Extract GPS information from EXIF data.

        Args:
            exif_data: Raw EXIF data dictionary

        Returns:
            dict: Processed GPS information
        """
        gps_info = {}

        # Find GPSInfo tag
        gps_tag_id = None
        for tag, value in exif_data.items():
            tag_name = TAGS.get(tag, tag)
            if tag_name == 'GPSInfo':
                gps_tag_id = tag
                break

        if gps_tag_id is None:
            return gps_info

        # Decode GPS tags
        gps_data = exif_data[gps_tag_id]
        for key in gps_data.keys():
            tag_name = GPSTAGS.get(key, key)
            gps_info[tag_name] = gps_data[key]

        return gps_info

    @staticmethod
    def _get_datetime(exif_data: Dict) -> Optional[str]:
        """
        Extract datetime from EXIF data.

        Args:
            exif_data: Raw EXIF data dictionary

        Returns:
            str: ISO format datetime string, or None
        """
        try:
            # Try DateTimeOriginal first, fall back to DateTime
            for tag_name in ['DateTimeOriginal', 'DateTime']:
                for tag, value in exif_data.items():
                    if TAGS.get(tag, tag) == tag_name:
                        # Parse EXIF datetime format: "YYYY:MM:DD HH:MM:SS"
                        dt = datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                        return dt.isoformat()

            return None

        except (ValueError, TypeError) as e:
            logger.error(f"Error parsing datetime: {e}")
            return None

    @classmethod
    def extract_exif(cls, image_path: Path) -> Dict[str, Any]:
        """
        Extract EXIF data from image file.

        Args:
            image_path: Path to image file

        Returns:
            dict: Dictionary containing EXIF metadata with keys:
                - has_exif: bool - Whether EXIF data was found
                - has_gps: bool - Whether GPS coordinates were found
                - latitude: float - Latitude in decimal degrees (if available)
                - longitude: float - Longitude in decimal degrees (if available)
                - altitude: float - Altitude in meters (if available)
                - datetime: str - ISO format datetime (if available)
                - camera_make: str - Camera manufacturer (if available)
                - camera_model: str - Camera model (if available)
                - error: str - Error message (if extraction failed)
        """
        result = {
            'has_exif': False,
            'has_gps': False,
            'latitude': None,
            'longitude': None,
            'altitude': None,
            'datetime': None,
            'camera_make': None,
            'camera_model': None,
            'image_width': None,
            'image_height': None,
            'error': None
        }

        try:
            # Open image
            with Image.open(image_path) as img:
                # Get image dimensions
                result['image_width'], result['image_height'] = img.size

                # Get EXIF data
                exif_data = img._getexif()

                if not exif_data:
                    result['error'] = 'No EXIF data found in image'
                    logger.info(f"No EXIF data in {image_path.name}")
                    return result

                result['has_exif'] = True

                # Extract GPS information
                gps_info = cls._get_gps_info(exif_data)

                if gps_info:
                    # Get coordinates
                    coords = cls._get_decimal_coordinates(gps_info)
                    if coords:
                        result['has_gps'] = True
                        result['latitude'], result['longitude'] = coords

                        # Get altitude if available
                        altitude = gps_info.get('GPSAltitude')
                        if altitude:
                            result['altitude'] = float(altitude)

                        logger.info(
                            f"GPS data extracted from {image_path.name}: "
                            f"({result['latitude']:.6f}, {result['longitude']:.6f})"
                        )

                # Extract other metadata
                for tag, value in exif_data.items():
                    tag_name = TAGS.get(tag, tag)

                    if tag_name == 'Make':
                        result['camera_make'] = str(value).strip()
                    elif tag_name == 'Model':
                        result['camera_model'] = str(value).strip()

                # Extract datetime
                result['datetime'] = cls._get_datetime(exif_data)

                if not result['has_gps']:
                    result['error'] = 'Image has EXIF data but no GPS coordinates'
                    logger.info(f"No GPS data in {image_path.name}")

                return result

        except FileNotFoundError:
            result['error'] = 'Image file not found'
            logger.error(f"File not found: {image_path}")
        except Image.UnidentifiedImageError:
            result['error'] = 'Invalid or unsupported image format'
            logger.error(f"Invalid image format: {image_path}")
        except Exception as e:
            result['error'] = f'Error extracting EXIF data: {str(e)}'
            logger.error(f"Error extracting EXIF from {image_path}: {e}")

        return result

    @classmethod
    def extract_from_multiple(cls, image_paths: list[Path]) -> list[Dict[str, Any]]:
        """
        Extract EXIF data from multiple images.

        Args:
            image_paths: List of paths to image files

        Returns:
            list: List of EXIF data dictionaries (one per image)
        """
        results = []

        for image_path in image_paths:
            result = cls.extract_exif(image_path)
            result['filename'] = image_path.name
            results.append(result)

        return results

    @staticmethod
    def format_coordinates(lat: float, lon: float) -> Dict[str, str]:
        """
        Format coordinates in multiple representations.

        Args:
            lat: Latitude in decimal degrees
            lon: Longitude in decimal degrees

        Returns:
            dict: Formatted coordinates with keys:
                - decimal: "lat, lon" format
                - dms: Degrees, Minutes, Seconds format
                - google_maps: URL for Google Maps
        """
        def decimal_to_dms(decimal: float, is_latitude: bool) -> str:
            """Convert decimal degrees to DMS format."""
            direction = ''
            if is_latitude:
                direction = 'N' if decimal >= 0 else 'S'
            else:
                direction = 'E' if decimal >= 0 else 'W'

            decimal = abs(decimal)
            degrees = int(decimal)
            minutes_decimal = (decimal - degrees) * 60
            minutes = int(minutes_decimal)
            seconds = (minutes_decimal - minutes) * 60

            return f"{degrees}°{minutes}'{seconds:.2f}\"{direction}"

        lat_dms = decimal_to_dms(lat, True)
        lon_dms = decimal_to_dms(lon, False)

        return {
            'decimal': f"{lat:.6f}, {lon:.6f}",
            'dms': f"{lat_dms}, {lon_dms}",
            'google_maps': f"https://www.google.com/maps?q={lat},{lon}"
        }
