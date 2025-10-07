import argparse
import logging
import os
import uuid
from typing import Any, Literal

import httpx
from mcp.server.fastmcp import FastMCP
from mcp.types import EmbeddedResource, TextResourceContents
from pydantic import AnyUrl

# Create a hiking route between Montreux and Lausanne, Switzerland
# Create a hiking route between Montreux and Lausanne, Switzerland, stop by some interesting points of interest on the way
# Create a hiking route between Montreux and Lausanne, going through Vevey and Puidoux, Switzerland
# Create a route between Rochers de Naye and Col de Jaman, Switzerland
# I am looking for the coordinates of Rochers de Naye in Switzerland

# TODO: we could create URL to enable the user to visualize the GPX route
# https://gpx.studio/?url=https://raw.githubusercontent.com/modelcontextprotocol/openroute-mcp/main/examples/route.gpx
# https://gpx.studio/


logging.getLogger("httpx").setLevel(logging.WARNING)

# Get API key from environment variable
OPENROUTESERVICE_API_KEY = os.getenv("OPENROUTESERVICE_API_KEY", "")
if not OPENROUTESERVICE_API_KEY:
    raise ValueError("OPENROUTESERVICE_API_KEY environment variable not set")

OPENROUTE_API = "https://api.openrouteservice.org"
SEARCH_LOCATION_RESULTS_LIMIT = 10
GEN_ROUTES_FOLDER = "data/generated_routes"
os.makedirs(GEN_ROUTES_FOLDER, exist_ok=True)


# TODO: use official lib? https://github.com/GIScience/openrouteservice-py
def http_client() -> httpx.AsyncClient:
    """Get an HTTP client instance."""
    return httpx.AsyncClient(
        timeout=30.0,
        limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
    )


# Create MCP server https://github.com/modelcontextprotocol/python-sdk
mcp = FastMCP(
    name="OpenRoute MCP",
    dependencies=["mcp", "httpx"],
    instructions="Tools to help plan routes using https://openrouteservice.org, for activities such as hiking or mountain biking",
    website_url="https://github.com/vemonet/openroute-mcp",
    # lifespan=,
    debug=True,
)

RouteType = Literal[
    "driving-car",
    "driving-hgv",
    "cycling-regular",
    "cycling-road",
    "cycling-mountain",
    "cycling-electric",
    "foot-walking",
    "foot-hiking",
    "wheelchair",
]


@mcp.tool()
async def search_location_coordinates(location: str) -> str:
    """Search for possible coordinates of a location.

    Args:
        location: Location string (address or place name)

    Returns:
        String representation of possible coordinates (longitude, latitude), and description if available to help selection.
    """
    response = await http_client().get(
        f"{OPENROUTE_API}/geocode/search",
        params={
            "api_key": OPENROUTESERVICE_API_KEY,
            "text": location,
            "size": SEARCH_LOCATION_RESULTS_LIMIT,
        },
    )
    response.raise_for_status()
    data = response.json()
    if not data.get("features"):
        raise ValueError(f"Could not geocode location: {location}")

    results = []
    # Get the top RESULTS_LIMIT best matches `data["features"][:SEARCH_LOCATION_RESULTS_LIMIT]`
    for i, feature in enumerate(data["features"], 1):
        coords = feature["geometry"]["coordinates"]
        longitude, latitude = coords[0], coords[1]

        # Extract useful properties for description
        props = feature.get("properties", {})
        name = props.get("name", "Unknown")
        address = props.get("label", "")
        confidence = props.get("confidence", 0)
        layer = props.get("layer", "")
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

        # Format response to be presented to the LLM/user
        result_str = f"{i}. {name}"
        if address:
            result_str += f"\n   Address: {address}"
        result_str += f"\n   Coordinates: [{longitude}, {latitude}]"
        result_str += f"\n   Confidence: {confidence}, Type: {layer}"
        results.append(result_str)

    result_text = f"Found {len(results)} locations for '{location}':\n\n" + "\n\n".join(results)
    # await ctx.info(f"Found {len(results)} locations for '{location}'")
    return result_text


# API docs: https://openrouteservice.org/dev/#/api-docs/v2/directions/{profile}/post
@mcp.tool()
async def create_route_from_to(
    route_type: RouteType,
    from_coordinates: list[float],
    to_coordinates: list[float],
    waypoints: list[list[float]] | None = None,
) -> list[str | EmbeddedResource]:
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
        f"{OPENROUTE_API}/v2/directions/{route_type}/gpx",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
            "Authorization": OPENROUTESERVICE_API_KEY,
        },
        json={"coordinates": coordinates},
    )
    response.raise_for_status()
    route_filename = f"{route_type}-{uuid.uuid4()}.gpx"
    # NOTE: store the generated route file to enable downloading it via a resource link later
    # with open(os.path.join(GEN_ROUTES_FOLDER, route_filename), "wb") as f:
    #     f.write(response.content)

    # Return the whole GPX file to enable LLM to summarize the route, and resource link enable downloading the `.gpx` file
    # https://modelcontextprotocol.io/specification/2025-06-18/server/tools#resource-links
    return [
        response.text,
        EmbeddedResource(
            type="resource",
            resource=TextResourceContents(
                text=response.text, uri=AnyUrl(f"route:///{route_filename}"), mimeType="application/gpx+xml"
            ),
        ),
        # ResourceLink(
        #     type="resource_link",
        #     uri=AnyUrl(f"route://{route_filename}"),
        #     name=route_filename,
        #     mimeType="application/gpx+xml",
        # ),
    ]


# https://openrouteservice.org/dev/#/api-docs/pois/post
@mcp.tool()
async def search_pois(
    bounding_box_coordinates: list[list[float]],
    filters_name: list[str] | None = None,
) -> Any:
    """Search for points of interest (POIs) in an area.

    Args:
        bounding_box_coordinates: coordinates defining a bounding box as [[min_lon, min_lat], [max_lon, max_lat]]
        filters_name: optional list of names to filter POIs, e.g. ["Gas station", "Restaurant"]

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
        f"{OPENROUTE_API}/pois",
        headers={
            "Authorization": OPENROUTESERVICE_API_KEY,
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8",
        },
        json=request_body,
    )
    response.raise_for_status()
    return response.json()


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
    # TODO: currently only works for Switzerland using Swiss Geo API, need to find other services for other countries
    # Check if coordinates are in Switzerland before calling Swiss API
    if not is_in_switzerland(from_coordinates[0], from_coordinates[1]) or not is_in_switzerland(
        to_coordinates[0], to_coordinates[1]
    ):
        return "Known route search is currently only available for locations in Switzerland. The provided coordinates are outside Switzerland's boundaries."

    client = http_client()
    map_layer_swiss = layer_mapping.get(route_type)
    if not map_layer_swiss:
        return f"No known route data available for route type '{route_type}' in Switzerland. This search currently supports hiking trails and cycling routes."

    # Get trails near start and end coordinates
    start_trails = await search_public_swiss_api(from_coordinates[0], from_coordinates[1], map_layer_swiss, client)
    end_trails = await search_public_swiss_api(to_coordinates[0], to_coordinates[1], map_layer_swiss, client)

    # Returns a message with the expected path + a list of trails close to start/end points = this enables agent to suggest waypoints when calling the `create_route_from_to` tool
    trails_info = f"Found {len(start_trails.get('results', []))} trails near start and {len(end_trails.get('results', []))} trails near end.\n\n"
    trails_info += f"Start trails: {start_trails}\n\nEnd trails: {end_trails}"
    return f"Given the known trails close to the start and end coordinates:\n{trails_info}\n\nSuggest waypoints to go through known trails when creating a route."

    # NOTE: also adds the direct route for more accuracy, but this might be quite long for the LLM context
    # direct_route = await create_route_from_to(route_type, from_coordinates, to_coordinates)
    # direct_gpx = direct_route[0].text
    # return f"Given the direct route pregenerated: {direct_gpx}\n\nAnd the known routes close to the start and end coordinates:\n{trails_info}\n\nSuggest waypoints to go through known trails when creating a route."


# Map route types to Swiss Geo API layers
layer_mapping: dict[str, str | None] = {
    "foot-walking": "all:ch.swisstopo.swisstlm3d-wanderwege",
    "foot-hiking": "all:ch.swisstopo.swisstlm3d-wanderwege",
    "cycling-regular": "all:ch.astra.veloland",
    "cycling-road": "all:ch.astra.veloland",
    "cycling-mountain": "all:ch.astra.mountainbikeland",
    "cycling-electric": "all:ch.astra.veloland",
    "driving-car": None,
    "driving-hgv": None,
    "wheelchair": None,
}


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


# TODO: add tool to retrieve relevant known hiking/cycling routes close to a given location as GPX
# Which service can be used to get known hiking/cycling routes close to a given location?
# 🍴 Request to do: https://www.trailforks.com/about/api/
# Need to host postgresql + uvicorn app: https://github.com/waymarkedtrails/waymarkedtrails-api

# 🇨🇭 Public Swiss: Get hiking trails close to a given coordinate as GeoJSON:
# curl "https://api3.geo.admin.ch/rest/services/all/MapServer/identify?geometry=6.632,46.519&geometryFormat=geojson&geometryType=esriGeometryPoint&sr=4326&layers=all:ch.swisstopo.swisstlm3d-wanderwege&tolerance=500&mapExtent=6.63,46.51,6.64,46.52&imageDisplay=600,400,96"
# https://api3.geo.admin.ch/services/sdiservices.html#sparql-service

# 🏔️ AllTrails web scraping
# https://github.com/srinath1510/alltrails-mcp-server
# https://lobehub.com/mcp/srinath1510-alltrails_mcp_server

# POST https://www.alltrails.com/api/alltrails/explore/v1/suggestions
# {"query":"rochers de naye","limit":50}
# {"searchResults":[{"ID":53798,"indexed_at":1755446471,"created_at":1678296231,"popularity":65.6676,"type":"poi","location_type":"poi","_geoloc":{"lat":46.4318192,"lng":6.976051},"source":"osm","subtype":"peak","trails_count":36,"photos_count":2,"elevation_meters":1998.87,"collections":["views"],"associated_area_ids":[10169111],"trail_ids":[11144238,11126747,11136147,11161037,11136143,10929163,10496707,11166434,11192006,11166427,10496518,10575921,10496672,11192227,10974364,10895867,10780653,10496680,11210891,11281891,11292278,11293844,11294054,11314607,11370656,11370655,11370654,11412067,11412051,11412055,11412050,11412073,11412057,11412075,11412048,11412071],"boundary_path":"points_of_interest/boundaries/53798.json","slug":"poi/switzerland/vaud/rochers-de-naye","area_slug":"parks/switzerland/vaud/regional-park-gruyere-pays-denhaut","area_name":"Parc naturel régional Gruyère Pays-d'Enhaut","city_name":"Veytaux","state_name":"Vaud","country_name":"Suisse","name":"Rochers de Naye","type_label":"Pic","location_label":"Parc naturel régional Gruyère Pays-d'Enhaut, Suisse","objectID":"poi-53798","name_with_formatting":"<em>Rochers</em> <em>de</em> <em>Naye</em>"},{"ID":10496672,"indexed_at":1759716137,"created_at":1564072489,"popularity":98.0533,"type":"trail","_geoloc":{"lat":46.43428,"lng":6.94742},"_cluster_geoloc":{"lat":46.43424,"lng":6.94735},"length":13035.654,"elevation_gain":904.9512000000001,"elevation_meters":1159,"difficulty_rating":"5","route_type":"L","avg_rating":4.7,"verified_map_id":272058803,"features":["cave","dogs","forest","views","wildlife","paved"],"activities":["birding","hiking"],"collections":["trending","trees","views","dogs"],"collections_with_photos":["trees","views","dogs"],"num_reviews":469,"is_closed":false,"num_photos":1986,"area_type":"S","popularity_by_month":{"month_1":3,"month_2":1,"month_3":2,"month_4":11,"month_5":49,"month_6":61,"month_7":93,"month_8":91,"month_9":89,"month_10":34,"month_11":24,"month_12":4},"seasonal_popularity":168,"slug":"trail/switzerland/vaud/rochers-de-naye-via-haux-de-caux","area_id":10169111,"associated_area_ids":[10169111],"area_slug":"parks/switzerland/vaud/regional-park-gruyere-pays-denhaut","area_name":"Parc naturel régional Gruyère Pays-d'Enhaut","city_name":"Caux","city_url":"switzerland/vaud/caux","state_name":"Vaud","country_name":"Suisse",

# Weird commercial API: https://rapidapi.com/trailapi/api/trailapi

# NOTE: search for campgrounds: https://github.com/campertunity/mcp-server


@mcp.resource("route://{filename}")
def get_route(filename: str) -> bytes:
    """Get a generated route `.gpx` file by filename."""
    with open(f"{GEN_ROUTES_FOLDER}/{filename}", "rb") as f:
        data = f.read()
    return data


def cli() -> None:
    """Run the MCP server."""
    parser = argparse.ArgumentParser(
        description="A Model Context Protocol (MCP) server for building routes using OpenRouteService."
    )
    parser.add_argument("--http", action="store_true", help="Use Streamable HTTP transport")
    parser.add_argument("--port", type=int, default=8888, help="Port to run the server on")
    args = parser.parse_args()
    if args.http:
        mcp.settings.port = args.port
        mcp.settings.log_level = "INFO"
        mcp.run(transport="streamable-http")
    else:
        mcp.run()
