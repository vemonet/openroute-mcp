from typing import Literal, TypedDict

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

RangeType = Literal[
    "time",
    "distance",
]

# Map route types to Swiss Geo API layers
LAYER_MAPPING: dict[str, str | None] = {
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


# Types for location search response
class LocationResult(TypedDict):
    """Represents a single location search result."""

    rank: int
    name: str
    address: str
    longitude: float
    latitude: float
    confidence: float
    layer: str


class LocationResponse(TypedDict):
    """Represents a list of location search results."""

    results: list[LocationResult]


# Types for POIs response
class CategoryInfo(TypedDict):
    """Category information for a POI."""

    category_name: str
    category_group: str


class OsmTags(TypedDict, total=False):
    """OSM tags for a POI (all fields are optional)."""

    name: str
    website: str
    opening_hours: str
    phone: str
    healthcare_speciality: str
    wheelchair: str
    fee: str


class PoiProperties(TypedDict, total=False):
    """Properties of a Point of Interest."""

    osm_id: int
    osm_type: int
    distance: float
    category_ids: dict[str, CategoryInfo]
    osm_tags: OsmTags


class PoiGeometry(TypedDict):
    """Geometry of a POI."""

    type: str
    coordinates: list[float]


class PoiFeature(TypedDict):
    """A Point of Interest feature."""

    type: str
    geometry: PoiGeometry
    properties: PoiProperties


class QueryGeometry(TypedDict):
    """Geometry information in the query."""

    bbox: list[list[float]]
    geojson: dict[str, str | list[float]]
    buffer: int


class QueryInfo(TypedDict):
    """Query information in the POIs response."""

    request: str
    geometry: QueryGeometry
    limit: int


class InformationMetadata(TypedDict):
    """Metadata information in the POIs response."""

    attribution: str
    version: str
    timestamp: int
    query: QueryInfo


class PoisResponse(TypedDict):
    """Response from the OpenRouteService POIs endpoint."""

    type: str
    bbox: list[float]
    features: list[PoiFeature]
    information: InformationMetadata
