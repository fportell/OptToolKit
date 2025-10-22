"""
Interactive Map Generation for Geolocation Tool.

Creates interactive maps using Folium with markers for GPS coordinates.
Per FR-006: Visualize extracted GPS data on interactive maps.
"""

import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
import folium
from folium import plugins
import base64

logger = logging.getLogger(__name__)


class MapGenerator:
    """
    Generate interactive maps with GPS markers.

    Uses Folium library to create Leaflet.js maps.
    """

    # Default map settings
    DEFAULT_ZOOM = 13
    DEFAULT_TILE = 'OpenStreetMap'

    # Available tile layers
    TILE_LAYERS = {
        'OpenStreetMap': 'OpenStreetMap',
        'Satellite': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        'Terrain': 'https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}',
        'CartoDB': 'CartoDB positron'
    }

    @staticmethod
    def _create_popup_html(data: Dict[str, Any]) -> str:
        """
        Create HTML content for map marker popup.

        Args:
            data: Dictionary with location data

        Returns:
            str: HTML content for popup
        """
        html_parts = [
            f"<div style='font-family: sans-serif; min-width: 200px;'>",
            f"<h6 style='margin: 0 0 10px 0; color: #0d6efd;'><b>{data.get('filename', 'Unknown')}</b></h6>"
        ]

        # Coordinates
        if data.get('latitude') and data.get('longitude'):
            html_parts.append(
                f"<p style='margin: 5px 0;'>"
                f"<b>Coordinates:</b><br>"
                f"<small>{data['latitude']:.6f}, {data['longitude']:.6f}</small>"
                f"</p>"
            )

        # Altitude
        if data.get('altitude'):
            html_parts.append(
                f"<p style='margin: 5px 0;'>"
                f"<b>Altitude:</b> {data['altitude']:.1f} m"
                f"</p>"
            )

        # Datetime
        if data.get('datetime'):
            # Format datetime nicely
            from datetime import datetime
            try:
                dt = datetime.fromisoformat(data['datetime'])
                formatted_dt = dt.strftime('%Y-%m-%d %H:%M:%S')
                html_parts.append(
                    f"<p style='margin: 5px 0;'>"
                    f"<b>Taken:</b> {formatted_dt}"
                    f"</p>"
                )
            except:
                pass

        # Camera info
        camera_parts = []
        if data.get('camera_make'):
            camera_parts.append(data['camera_make'])
        if data.get('camera_model'):
            camera_parts.append(data['camera_model'])

        if camera_parts:
            html_parts.append(
                f"<p style='margin: 5px 0;'>"
                f"<b>Camera:</b> {' '.join(camera_parts)}"
                f"</p>"
            )

        # Image dimensions
        if data.get('image_width') and data.get('image_height'):
            html_parts.append(
                f"<p style='margin: 5px 0;'>"
                f"<b>Size:</b> {data['image_width']} × {data['image_height']} px"
                f"</p>"
            )

        # Google Maps link
        if data.get('latitude') and data.get('longitude'):
            google_url = f"https://www.google.com/maps?q={data['latitude']},{data['longitude']}"
            html_parts.append(
                f"<p style='margin: 10px 0 0 0;'>"
                f"<a href='{google_url}' target='_blank' style='color: #0d6efd;'>"
                f"<small>View in Google Maps ↗</small>"
                f"</a>"
                f"</p>"
            )

        html_parts.append("</div>")

        return ''.join(html_parts)

    @staticmethod
    def _get_marker_color(index: int, total: int) -> str:
        """
        Get marker color based on index.

        Args:
            index: Marker index (0-based)
            total: Total number of markers

        Returns:
            str: Color name for folium marker
        """
        colors = ['red', 'blue', 'green', 'purple', 'orange', 'darkred',
                  'lightred', 'beige', 'darkblue', 'darkgreen', 'cadetblue',
                  'darkpurple', 'pink', 'lightblue', 'lightgreen', 'gray']

        if total == 1:
            return 'red'

        return colors[index % len(colors)]

    @classmethod
    def create_map(cls,
                   locations: List[Dict[str, Any]],
                   tile_layer: str = DEFAULT_TILE,
                   cluster_markers: bool = False) -> Optional[str]:
        """
        Create an interactive map with markers for GPS locations.

        Args:
            locations: List of location dictionaries with GPS data
            tile_layer: Map tile layer to use
            cluster_markers: Whether to cluster nearby markers

        Returns:
            str: HTML string of the map, or None if no valid locations
        """
        # Filter locations with valid GPS coordinates
        valid_locations = [
            loc for loc in locations
            if loc.get('has_gps') and loc.get('latitude') and loc.get('longitude')
        ]

        if not valid_locations:
            logger.warning("No valid GPS locations to map")
            return None

        logger.info(f"Creating map with {len(valid_locations)} location(s)")

        # Calculate map center (average of all coordinates)
        avg_lat = sum(loc['latitude'] for loc in valid_locations) / len(valid_locations)
        avg_lon = sum(loc['longitude'] for loc in valid_locations) / len(valid_locations)

        # Determine zoom level based on number of points and spread
        if len(valid_locations) == 1:
            zoom_start = cls.DEFAULT_ZOOM
        else:
            # Calculate bounding box
            lats = [loc['latitude'] for loc in valid_locations]
            lons = [loc['longitude'] for loc in valid_locations]

            lat_range = max(lats) - min(lats)
            lon_range = max(lons) - min(lons)
            max_range = max(lat_range, lon_range)

            # Adjust zoom based on coordinate spread
            if max_range > 1:
                zoom_start = 8
            elif max_range > 0.1:
                zoom_start = 11
            else:
                zoom_start = 13

        # Create base map
        tile_url = cls.TILE_LAYERS.get(tile_layer, cls.TILE_LAYERS[cls.DEFAULT_TILE])

        m = folium.Map(
            location=[avg_lat, avg_lon],
            zoom_start=zoom_start,
            tiles=tile_url if tile_url in ['OpenStreetMap', 'CartoDB positron'] else None,
            attr='OpsToolKit Geolocation'
        )

        # Add custom tile layer if needed
        if tile_url not in ['OpenStreetMap', 'CartoDB positron']:
            folium.TileLayer(
                tiles=tile_url,
                attr='Map tiles',
                name=tile_layer
            ).add_to(m)

        # Add markers
        if cluster_markers and len(valid_locations) > 5:
            # Use marker clustering for many points
            marker_cluster = plugins.MarkerCluster().add_to(m)

            for idx, location in enumerate(valid_locations):
                popup_html = cls._create_popup_html(location)

                folium.Marker(
                    location=[location['latitude'], location['longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=location.get('filename', f'Location {idx + 1}'),
                    icon=folium.Icon(
                        color=cls._get_marker_color(idx, len(valid_locations)),
                        icon='camera',
                        prefix='fa'
                    )
                ).add_to(marker_cluster)
        else:
            # Add individual markers
            for idx, location in enumerate(valid_locations):
                popup_html = cls._create_popup_html(location)

                folium.Marker(
                    location=[location['latitude'], location['longitude']],
                    popup=folium.Popup(popup_html, max_width=300),
                    tooltip=location.get('filename', f'Location {idx + 1}'),
                    icon=folium.Icon(
                        color=cls._get_marker_color(idx, len(valid_locations)),
                        icon='camera',
                        prefix='fa'
                    )
                ).add_to(m)

        # Add layer control if multiple tile layers
        folium.LayerControl().add_to(m)

        # Add fullscreen button
        plugins.Fullscreen(
            position='topright',
            title='Fullscreen',
            title_cancel='Exit fullscreen',
            force_separate_button=True
        ).add_to(m)

        # Add scale bar
        plugins.MeasureControl(
            position='bottomleft',
            primary_length_unit='kilometers',
            secondary_length_unit='miles',
            primary_area_unit='sqkilometers',
            secondary_area_unit='acres'
        ).add_to(m)

        # Generate HTML
        map_html = m._repr_html_()

        logger.info("Map generated successfully")
        return map_html

    @classmethod
    def create_map_with_path(cls,
                             locations: List[Dict[str, Any]],
                             tile_layer: str = DEFAULT_TILE) -> Optional[str]:
        """
        Create a map with markers connected by a path (for sequential photos).

        Args:
            locations: List of location dictionaries with GPS data (should be ordered)
            tile_layer: Map tile layer to use

        Returns:
            str: HTML string of the map, or None if insufficient locations
        """
        # Filter valid locations
        valid_locations = [
            loc for loc in locations
            if loc.get('has_gps') and loc.get('latitude') and loc.get('longitude')
        ]

        if len(valid_locations) < 2:
            logger.warning("Need at least 2 locations for path map")
            return cls.create_map(locations, tile_layer)

        # Create base map (same as regular map)
        map_html = cls.create_map(locations, tile_layer, cluster_markers=False)

        if not map_html:
            return None

        # Parse the HTML and add a polyline
        # For simplicity, we'll create a new map with the path
        avg_lat = sum(loc['latitude'] for loc in valid_locations) / len(valid_locations)
        avg_lon = sum(loc['longitude'] for loc in valid_locations) / len(valid_locations)

        m = folium.Map(
            location=[avg_lat, avg_lon],
            zoom_start=12,
            tiles=cls.TILE_LAYERS.get(tile_layer, cls.DEFAULT_TILE)
        )

        # Add polyline connecting locations
        coordinates = [[loc['latitude'], loc['longitude']] for loc in valid_locations]
        folium.PolyLine(
            coordinates,
            color='blue',
            weight=3,
            opacity=0.7,
            tooltip='Photo path'
        ).add_to(m)

        # Add numbered markers
        for idx, location in enumerate(valid_locations):
            popup_html = cls._create_popup_html(location)

            folium.Marker(
                location=[location['latitude'], location['longitude']],
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=f"{idx + 1}. {location.get('filename', 'Unknown')}",
                icon=folium.Icon(
                    color=cls._get_marker_color(idx, len(valid_locations)),
                    icon='info-sign',
                    prefix='glyphicon'
                )
            ).add_to(m)

        # Add plugins
        plugins.Fullscreen().add_to(m)
        plugins.MeasureControl().add_to(m)

        return m._repr_html_()
