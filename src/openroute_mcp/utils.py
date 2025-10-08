import logging
from typing import Any

import folium
import gpxpy
import httpx
from staticmap import CircleMarker, Line, StaticMap

from openroute_mcp.types import LocationResult

logging.getLogger("httpx").setLevel(logging.WARNING)


# TODO: use official lib? https://github.com/GIScience/openrouteservice-py
def http_client() -> httpx.AsyncClient:
    """Get an HTTP client instance."""
    return httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )


def process_location_result(result: dict[str, Any], rank: int) -> LocationResult:
    """Process a single location result from the API response into a LocationResult object."""
    props = result.get("properties", {})
    address = props.get("label", "")
    if not address:
        # Build full address components from available parts
        address_parts = []
        if props.get("housenumber"):
            address_parts.append(props["housenumber"])
        if props.get("street"):
            address_parts.append(props["street"])
        if props.get("locality"):
            address_parts.append(props["locality"])
        if props.get("region"):
            address_parts.append(props["region"])
        if props.get("country"):
            address_parts.append(props["country"])
        if address_parts:
            address = ", ".join(address_parts)
    return LocationResult(
        rank=rank,
        name=props.get("name", "Unknown"),
        address=address,
        longitude=result["geometry"]["coordinates"][0],
        latitude=result["geometry"]["coordinates"][1],
        confidence=props.get("confidence", 0),
        layer=props.get("layer", ""),
    )


def gpx_to_img(gpx_str: str, output_file: str) -> str:
    """Convert a GPX string to a PNG image of the route using `staticmap`."""
    gpx = gpxpy.parse(gpx_str)
    coords = []
    # Collect all route <rte> / track <trk> elements
    for track in gpx.tracks:
        for segment in track.segments:
            for point in segment.points:
                coords.append((point.longitude, point.latitude))
    for route in gpx.routes:
        for point in route.points:  # type: ignore
            coords.append((point.longitude, point.latitude))
    if not coords:
        print("WARNING: No coordinates found in GPX data, skipping image generation")
        return ""

    # Create map, add route line, and optionally add start/end markers
    m = StaticMap(800, 600, url_template="http://a.tile.openstreetmap.org/{z}/{x}/{y}.png")
    m.add_line(Line(coords, "blue", 3))
    if coords:
        m.add_marker(CircleMarker(coords[0], "green", 10))  # Start
        m.add_marker(CircleMarker(coords[-1], "red", 10))  # End

    # Render image and save to file
    img = m.render()
    output_path = f"data/generated_routes/{output_file}"
    img.save(output_path)
    return output_path


def gpx_to_html(gpx_str: str, output_file: str) -> str:
    """Plot a GPX route using `folium` and save as an HTML file."""
    gpx = gpxpy.parse(gpx_str)
    # Collect all route <rte> / track <trk> elements
    route_points = []
    for track in gpx.tracks:
        for seg in track.segments:
            for pt in seg.points:
                route_points.append((pt.latitude, pt.longitude))
    for route in gpx.routes:
        for pt in route.points:  # type: ignore
            route_points.append((pt.latitude, pt.longitude))

    if not route_points:
        print("WARNING: No coordinates found in GPX data, skipping HTMLI generation")
        return ""

    # Center map roughly at midpoint
    avg_lat = sum(lat for lat, _lon in route_points) / len(route_points)
    avg_lon = sum(lon for _lat, lon in route_points) / len(route_points)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=13, tiles="OpenStreetMap")
    folium.PolyLine(route_points, color="blue", weight=5, opacity=0.8).add_to(m)  # type: ignore
    folium.Marker(route_points[0], tooltip="Start").add_to(m)
    folium.Marker(route_points[-1], tooltip="End").add_to(m)
    output_path = f"data/generated_routes/{output_file}"
    m.save(output_path)
    return output_path
