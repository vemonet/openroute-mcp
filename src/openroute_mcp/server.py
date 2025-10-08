import argparse
import base64
import json
import os
import uuid
from dataclasses import dataclass
from typing import Any
from xml.dom.minidom import parseString

import httpx
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.session import ServerSession
from mcp.types import BlobResourceContents, EmbeddedResource, TextResourceContents
from pydantic import AnyUrl

from openroute_mcp.types import LAYER_MAPPING, LocationResponse, LocationResult, PoisResponse, RangeType, RouteType
from openroute_mcp.utils import gpx_to_html, gpx_to_img, http_client, process_location_result

# TODO: we could create URL to enable the user to visualize the GPX route
# https://gpx.studio/?url=https://raw.githubusercontent.com/modelcontextprotocol/openroute-mcp/main/examples/route.gpx
# https://gpx.studio/

# Create MCP server https://github.com/modelcontextprotocol/python-sdk
mcp = FastMCP(
    name="OpenRoute MCP",
    dependencies=["mcp", "httpx"],
    instructions="Tools to help plan routes using https://openrouteservice.org, for activities such as hiking or mountain biking",
    website_url="https://github.com/vemonet/openroute-mcp",
    # lifespan=app_lifespan,
)


@mcp.tool()
async def search_location_coordinates(location: str) -> LocationResponse:
    """Search for possible coordinates of a location.

    Args:
        location: Location string (address or place name)

    Returns:
        List of location results with coordinates, address, and metadata.
    """
    response = await http_client().get(
        f"{settings.openroute_api}/geocode/search",
        params={
            "api_key": settings.openroute_api_key,
            "text": location,
            "size": settings.search_results_limit,
        },
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("features"):
        raise ValueError(f"Could not geocode location: {location}")

    results: list[LocationResult] = []
    # Get the top RESULTS_LIMIT best matches `data["features"][:SEARCH_LOCATION_RESULTS_LIMIT]`
    for i, feature in enumerate(data["features"], 1):
        results.append(process_location_result(feature, i))
    return LocationResponse(results=results)


@mcp.tool()
async def get_coordinates_object(lon: float, lat: float) -> LocationResponse:
    """Returns the next enclosing objects with an address tag which surrounds the given coordinate.

    Args:
        lon: Longitude of the location
        lat: Latitude of the location

    Returns:
        List of objects results close to the given coordinates
    """
    response = await http_client().get(
        f"{settings.openroute_api}/geocode/reverse",
        params={
            "api_key": settings.openroute_api_key,
            "point.lon": lon,
            "point.lat": lat,
        },
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("features"):
        raise ValueError(f"Could not reverse geocode location: [{lon}, {lat}]")

    results: list[LocationResult] = []
    for i, feature in enumerate(data["features"], 1):
        results.append(process_location_result(feature, i))
    return LocationResponse(results=results)


# API docs: https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/post
@mcp.tool()
async def create_route_from_to(
    ctx: Context[ServerSession, Any],
    route_type: RouteType,
    from_coordinates: list[float],
    to_coordinates: list[float],
    waypoints: list[list[float]] | None = None,
) -> list[EmbeddedResource | str]:
    """Create a route from a starting location coordinates to a destination, optionally with waypoints.

    Args:
        route_type: Type of route, e.g. "driving-car", "cycling-mountain", "cycling-regular", "foot-hiking"
        from_coordinates: Starting location as [longitude, latitude]
        to_coordinates: Destination location as [longitude, latitude]
        waypoints: optional list of waypoints coordinates as [[lon, lat], ...]

    Returns:
        GPX representation of the route
    """
    coordinates = [from_coordinates]
    if waypoints:
        coordinates.extend(waypoints)
    coordinates.append(to_coordinates)

    response = await http_client().post(
        f"{settings.openroute_api}/v2/directions/{route_type}/gpx",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
            "Authorization": settings.openroute_api_key,
        },
        json={"coordinates": coordinates},
    )
    response.raise_for_status()

    # Pretty-format the GPX XML
    try:
        pretty_xml = parseString(response.text).toprettyxml(indent="  ")  # noqa: S318
    except Exception:
        pretty_xml = response.text

    route_filename = f"{route_type}-{uuid.uuid4()}"
    gpx_filename = f"{route_filename}.gpx"
    gpx_uri = AnyUrl(f"route:///{gpx_filename}")

    # Notify client of resource update https://github.com/modelcontextprotocol/python-sdk/#session-properties-and-methods
    await ctx.session.send_resource_updated(gpx_uri)
    tool_resp: list[EmbeddedResource | str] = [
        "The generated route is provided as a GPX file, please us it to summarize the route to the user and provide details, e.g. by which remarkable places does it go through. ",
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(text=pretty_xml, uri=gpx_uri, mimeType="application/gpx+xml"),
        ),
    ]

    if not settings.no_save:
        # NOTE: store the generated route file to enable downloading it via a resource link later
        with open(os.path.join(settings.data_folder, gpx_filename), "w", encoding="utf-8") as f:
            f.write(pretty_xml)
        # Generate image and HTML for the route
        img_filename = f"{route_filename}.png"
        html_filename = f"{route_filename}.html"
        img_filepath = gpx_to_img(response.text, img_filename)
        html_filepath = gpx_to_html(response.text, html_filename)

        # Add PNG image if generated
        if not settings.no_img and img_filepath:
            img_uri = AnyUrl(f"route:///{img_filename}")
            await ctx.session.send_resource_updated(img_uri)
            with open(img_filepath, "rb") as f:
                img_binary = base64.b64encode(f.read()).decode("utf-8")
            tool_resp[0] += " An image preview of the route is also provided."  # type: ignore
            tool_resp.append(
                EmbeddedResource(
                    type="resource",
                    resource=BlobResourceContents(blob=img_binary, uri=img_uri, mimeType="image/png"),
                ),
            )
        # Add HTML interactive map if generated
        if settings.add_html and html_filepath:
            html_uri = AnyUrl(f"route:///{html_filename}")
            await ctx.session.send_resource_updated(html_uri)
            with open(html_filepath) as f:
                html_str = f.read()
            tool_resp[0] += (
                " An interactive HTML map of the route is also provided (no need to read it, it contains the same info as the GPX)."  # type: ignore
            )
            tool_resp.append(
                EmbeddedResource(
                    type="resource",
                    resource=TextResourceContents(text=html_str, uri=html_uri, mimeType="text/html"),
                ),
            )
            # # https://modelcontextprotocol.io/specification/2025-06-18/server/tools#resource-links
            # tool_resp.append(
            #     ResourceLink(
            #         type="resource_link",
            #         uri=html_uri,
            #         name=html_filename,
            #         mimeType="text/html",
            #     ),
            # )
    await ctx.session.send_resource_list_changed()
    return tool_resp


# https://openrouteservice.org/dev/#/api-docs/pois/post
@mcp.tool()
async def search_pois(
    bounding_box_coordinates: list[list[float]],
    filters_name: list[str] | None = None,
) -> PoisResponse:
    """Search for points of interest (POIs) in an area.

    Args:
        bounding_box_coordinates: coordinates defining a bounding box as [[min_lon, min_lat], [max_lon, max_lat]]
        filters_name: optional explictly mentioned list of names to filter POIs, e.g. ["Gas station", "Restaurant"]

    Returns:
        Found POIs information
    """
    request_body = {
        "request": "pois",
        "geometry": {
            "bbox": bounding_box_coordinates,
            "geojson": {"type": "Point", "coordinates": bounding_box_coordinates[0]},
            "buffer": 200,
        },
        "limit": 100,
    }
    if filters_name:
        request_body["filters"] = {"name": filters_name}
    response = await http_client().post(
        f"{settings.openroute_api}/pois",
        headers={
            "Authorization": settings.openroute_api_key,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
        },
        json=request_body,
    )
    response.raise_for_status()
    result: PoisResponse = response.json()
    return result


@mcp.tool()
async def search_known_routes(route_type: RouteType, from_coordinates: list[float], to_coordinates: list[float]) -> str:
    """Search for known hiking/cycling routes close to a given start and end coordinates,
    this enables to suggest waypoints to go through known trails when creating a route.

    Currently only works for Switzerland using Swiss Geo API.

    Args:
        route_type: Type of route, e.g. "driving-car", "cycling-mountain", "cycling-regular", "foot-hiking"
        from_coordinates: Starting location as [longitude, latitude]
        to_coordinates: Destination location as [longitude, latitude]

    Returns:
        Description of known routes close to the given coordinates
    """
    # NOTE: currently only works for Switzerland using Swiss Geo API, need to find other services for other countries
    # Check if coordinates are in Switzerland before calling Swiss API
    if not is_in_switzerland(from_coordinates[0], from_coordinates[1]) or not is_in_switzerland(
        to_coordinates[0], to_coordinates[1]
    ):
        return "Known route search is currently only available for locations in Switzerland. The provided coordinates are outside Switzerland's boundaries."

    client = http_client()
    map_layer_swiss = LAYER_MAPPING.get(route_type)
    if not map_layer_swiss:
        return f"No known route data available for route type '{route_type}' in Switzerland. This search currently supports hiking trails and cycling routes."

    # Get trails near start and end coordinates
    start_trails = await search_public_swiss_api(from_coordinates[0], from_coordinates[1], map_layer_swiss, client)
    end_trails = await search_public_swiss_api(to_coordinates[0], to_coordinates[1], map_layer_swiss, client)

    # Returns a message with the expected path + a list of trails close to start/end points = this enables agent to suggest waypoints when calling the `create_route_from_to` tool
    trails_info = f"Found {len(start_trails.get('results', []))} trails near start and {len(end_trails.get('results', []))} trails near end.\n\n"
    trails_info += f"Start trails: \n\n```json\n{json.dumps(start_trails, indent=2)}\n```\n\nEnd trails: \n\n```json\n{json.dumps(end_trails, indent=2)}\n```"
    return f"Given the known trails close to the start and end coordinates:\n\n{trails_info}\n\nSuggest waypoints to go through known trails when creating a route."

    # NOTE: also adds the direct route for more accuracy, but this might be quite long for the LLM context
    # direct_route = await create_route_from_to(route_type, from_coordinates, to_coordinates)
    # direct_gpx = direct_route[0].text
    # return f"Given the direct route pregenerated: {direct_gpx}\n\nAnd the known routes close to the start and end coordinates:\n{trails_info}\n\nSuggest waypoints to go through known trails when creating a route."


def is_in_switzerland(lon: float, lat: float) -> bool:
    """Check if coordinates are approximately within Switzerland's boundaries.

    Switzerland boundaries (approximate):
    - Longitude: 5.96° to 10.49° East
    - Latitude: 45.82° to 47.81° North
    """
    return 5.96 <= lon <= 10.49 and 45.82 <= lat <= 47.81


async def search_public_swiss_api(lon: float, lat: float, swiss_layer: str, client: httpx.AsyncClient) -> Any:
    """Search for known trails near a coordinate using Swiss Geo API."""
    # Calculate map extent by adding/subtracting a small delta from the coordinates
    extent_delta = 0.02  # Approximately 2km
    response = await client.get(
        "https://api3.geo.admin.ch/rest/services/all/MapServer/identify",
        params={
            "geometry": f"{lon},{lat}",
            "geometryFormat": "geojson",
            "geometryType": "esriGeometryPoint",
            "sr": "4326",
            "layers": swiss_layer,
            "tolerance": "500",
            "mapExtent": f"{lon - extent_delta},{lat - extent_delta},{lon + extent_delta},{lat + extent_delta}",
            "imageDisplay": "600,400,96",
        },
    )
    response.raise_for_status()
    return response.json()


# TODO: find services that can be used to get known hiking/cycling routes close to a given location?

# 🍴 Trailforks: request to do https://www.trailforks.com/about/api/

# 🇨🇭 Public Swiss API: Get hiking trails close to a given coordinate as GeoJSON:
# curl "https://api3.geo.admin.ch/rest/services/all/MapServer/identify?geometry=6.632,46.519&geometryFormat=geojson&geometryType=esriGeometryPoint&sr=4326&layers=all:ch.swisstopo.swisstlm3d-wanderwege&tolerance=500&mapExtent=6.63,46.51,6.64,46.52&imageDisplay=600,400,96"
# https://api3.geo.admin.ch/services/sdiservices.html#sparql-service

# 🏔️ AllTrails web scraping
# https://github.com/srinath1510/alltrails-mcp-server
# https://lobehub.com/mcp/srinath1510-alltrails_mcp_server

# 🌍 WikiLoc: no API, scraping possible
# https://en.wikiloc.com/wikiloc/map.do?sw=46.3810438458062%2C6.469573974609375&ne=46.7248003746672%2C6.92962646484375&page=1

# 🧗 https://www.outdooractive.com/
# API: https://developers.outdooractive.com/API-Reference/Data-API.html

# 🌌 Waymarked Trails: Need to host postgresql + uvicorn app: https://github.com/waymarkedtrails/waymarkedtrails-api
# https://github.com/waymarkedtrails/waymarkedtrails-backend

# POST https://www.alltrails.com/api/alltrails/explore/v1/suggestions
# {"query":"rochers de naye","limit":50}
# {"searchResults":[{"ID":53798,"indexed_at":1755446471,"created_at":1678296231,"popularity":65.6676,"type":"poi","location_type":"poi","_geoloc":{"lat":46.4318192,"lng":6.976051},"source":"osm","subtype":"peak","trails_count":36,"photos_count":2,"elevation_meters":1998.87,"collections":["views"],"associated_area_ids":[10169111],"trail_ids":[11144238,11126747,11136147,11161037,11136143,10929163,10496707,11166434,11192006,11166427,10496518,10575921,10496672,11192227,10974364,10895867,10780653,10496680,11210891,11281891,11292278,11293844,11294054,11314607,11370656,11370655,11370654,11412067,11412051,11412055,11412050,11412073,11412057,11412075,11412048,11412071],"boundary_path":"points_of_interest/boundaries/53798.json","slug":"poi/switzerland/vaud/rochers-de-naye","area_slug":"parks/switzerland/vaud/regional-park-gruyere-pays-denhaut","area_name":"Parc naturel régional Gruyère Pays-d'Enhaut","city_name":"Veytaux","state_name":"Vaud","country_name":"Suisse","name":"Rochers de Naye","type_label":"Pic","location_label":"Parc naturel régional Gruyère Pays-d'Enhaut, Suisse","objectID":"poi-53798","name_with_formatting":"<em>Rochers</em> <em>de</em> <em>Naye</em>"},{"ID":10496672,"indexed_at":1759716137,"created_at":1564072489,"popularity":98.0533,"type":"trail","_geoloc":{"lat":46.43428,"lng":6.94742},"_cluster_geoloc":{"lat":46.43424,"lng":6.94735},"length":13035.654,"elevation_gain":904.9512000000001,"elevation_meters":1159,"difficulty_rating":"5","route_type":"L","avg_rating":4.7,"verified_map_id":272058803,"features":["cave","dogs","forest","views","wildlife","paved"],"activities":["birding","hiking"],"collections":["trending","trees","views","dogs"],"collections_with_photos":["trees","views","dogs"],"num_reviews":469,"is_closed":false,"num_photos":1986,"area_type":"S","popularity_by_month":{"month_1":3,"month_2":1,"month_3":2,"month_4":11,"month_5":49,"month_6":61,"month_7":93,"month_8":91,"month_9":89,"month_10":34,"month_11":24,"month_12":4},"seasonal_popularity":168,"slug":"trail/switzerland/vaud/rochers-de-naye-via-haux-de-caux","area_id":10169111,"associated_area_ids":[10169111],"area_slug":"parks/switzerland/vaud/regional-park-gruyere-pays-denhaut","area_name":"Parc naturel régional Gruyère Pays-d'Enhaut","city_name":"Caux","city_url":"switzerland/vaud/caux","state_name":"Vaud","country_name":"Suisse",

# Weird commercial API: https://rapidapi.com/trailapi/api/trailapi

# NOTE: search for campgrounds commercial MCP server: https://github.com/campertunity/mcp-server


@mcp.tool()
async def get_reachable_area(
    coordinates_list: list[list[float]],
    route_type: RouteType,
    range_type: RangeType,
    area_range: list[int] = [300, 200],  # noqa: B006
) -> PoisResponse:
    """Computes the area that can be reached within a given time or distance from one or more starting points.

    Args:
        coordinates_list: 1 or more coordinates to compute reachable area from as [[lon, lat], ...]
        route_type: Type of route, e.g. "cycling-mountain", "cycling-regular", "foot-hiking", "driving-car"
        range_type: Type of range, either `time` (in seconds) or `distance` (in metres)
        area_range: maximum range value of the analysis in seconds for time and metres for distance.
            Or a comma separated list of specific range values

    Returns:
        Reachable area information in GeoJSON format
    """
    request_body = {
        "locations": coordinates_list,
        "range": area_range,
        "range_type": range_type,
    }
    response = await http_client().post(
        f"{settings.openroute_api}/v2/isochrones/{route_type}",
        headers={
            "Authorization": settings.openroute_api_key,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
        },
        json=request_body,
    )
    response.raise_for_status()
    # TODO: fix the type
    result: PoisResponse = response.json()
    return result


# TODO: tool to help find trails around one specific location


@mcp.resource("route://{filename}")
def get_route(filename: str) -> bytes:
    """Get a generated route `.gpx`, `.png` or `.html` file by filename."""
    with open(f"{settings.data_folder}/{filename}", "rb") as f:
        data = f.read()
    return data


@mcp.prompt(title="Scenic hiking route")
def scenic_hiking_route(from_location: str, to_location: str) -> str:
    """Prompt to create a scenic hiking route."""
    return f"Create a hiking route from {from_location} to {to_location}, try to go through known pleasant trails, and pass by interesting points of interest on the way"


@mcp.prompt(title="Mountain biking route")
def scenic_biking_route(from_location: str, to_location: str) -> str:
    """Prompt to create a scenic mountain biking route."""
    return f"Create a mountain biking route from {from_location} to {to_location}, try to go through known pleasant trails, and pass by interesting points of interest on the way"


@dataclass
class AppSettings:
    openroute_api: str = "https://api.openrouteservice.org"
    openroute_api_key: str = os.getenv("OPENROUTESERVICE_API_KEY", "")
    data_folder: str = "data/generated_routes"
    search_results_limit: int = 10
    no_save: bool = False
    no_img: bool = False
    add_html: bool = False


settings = AppSettings()


def cli() -> None:
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="A Model Context Protocol (MCP) server for building routes using OpenRouteService."
    )
    parser.add_argument("--http", action="store_true", help="Use Streamable HTTP transport")
    parser.add_argument("--host", type=str, default="localhost", help="Host to run the server on")
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    parser.add_argument(
        "--openroute-api",
        type=str,
        default="https://api.openrouteservice.org",
        help="OpenRouteService API URL (default: https://api.openrouteservice.org)",
    )
    parser.add_argument(
        "--openroute-api-key",
        type=str,
        default="",
        help="OpenRouteService API key (default: taken from env var OPENROUTESERVICE_API_KEY)",
    )
    parser.add_argument(
        "--data-folder", type=str, default="data/generated_routes", help="Folder to save generated routes"
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save generated routes to disk (also disable image and HTML generation)",
    )
    parser.add_argument(
        "--no-img",
        action="store_true",
        help="Do not add PNG image visualization of the routes to the response (image not supported by all LLMs)",
    )
    parser.add_argument(
        "--add-html",
        action="store_true",
        help="Add HTML interactive map for routes to the response (larger context used)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug mode (more logs)",
    )
    args = parser.parse_args()
    settings.openroute_api = args.openroute_api
    settings.data_folder = args.data_folder
    settings.no_save = args.no_save
    settings.no_img = args.no_img
    settings.add_html = args.add_html
    if args.openroute_api_key:
        settings.openroute_api_key = args.openroute_api_key
    if not settings.openroute_api_key:
        raise ValueError("OPENROUTESERVICE_API_KEY environment variable not set and --openroute-api-key not provided")
    os.makedirs(settings.data_folder, exist_ok=True)

    if args.http:
        mcp.settings.host = args.host
        mcp.settings.port = args.port
        mcp.settings.log_level = "DEBUG" if args.debug else "INFO"
        mcp.settings.debug = args.debug
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


# from contextlib import asynccontextmanager
# @asynccontextmanager
# async def app_lifespan(app: FastMCP): # type: ignore
#     print("Server starting up...")
#     yield
#     print("Server shutting down...")

# Create a direct hiking route between Montreux and Lausanne, Switzerland
# I am searching for POIs around Chauderon, Lausanne
# Create a hiking route between Montreux and Lausanne, Switzerland, stop by some interesting points of interest on the way
# Create a hiking route between Montreux and Lausanne, going through Vevey and Puidoux, Switzerland
# Create a route between Rochers de Naye and Col de Jaman, Switzerland
# I am looking for the coordinates of Rochers de Naye in Switzerland
