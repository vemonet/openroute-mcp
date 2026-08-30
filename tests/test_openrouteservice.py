"""Test OpenRouteService integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from openroute_mcp.server import create_route_from_to, search_location_coordinates, settings


class _FakeResponse:
    """Stand-in for httpx.Response, just enough for create_route_from_to to run."""

    text = "<gpx></gpx>"

    def raise_for_status(self) -> None:
        pass


class _FakeClient:
    """Stand-in for the httpx.AsyncClient returned by http_client(), records the last POST."""

    def __init__(self) -> None:
        self.last_json: dict[str, Any] | None = None
        self.last_url: str = ""

    async def post(
        self, url: str, headers: dict[str, str] | None = None, json: dict[str, Any] | None = None
    ) -> _FakeResponse:
        self.last_url = url
        self.last_json = json
        return _FakeResponse()


def _fake_ctx() -> MagicMock:
    """A Context mock with just the awaited session methods create_route_from_to calls."""
    ctx = MagicMock()
    ctx.session.send_resource_updated = AsyncMock()
    ctx.session.send_resource_list_changed = AsyncMock()
    return ctx


# async def test_mcp_client_call():
#     client = MCPClient("python server.py")
#     response = await client.call_tool("add_numbers", {"a": 5, "b": 7})
#     assert response == 12


@pytest.mark.asyncio
async def test_search_location_coordinates() -> None:
    """Test geocoding a location."""
    res = await search_location_coordinates("Paris, France")
    # print(res)

    # Check that we got results
    assert "results" in res, "Response should contain results field"
    assert len(res["results"]) > 0, "Should return at least one location result"
    # Check the first result structure
    first_result = res["results"][0]
    assert "longitude" in first_result, "Result should contain longitude"
    assert "latitude" in first_result, "Result should contain latitude"
    assert "address" in first_result, "Result should contain address"
    assert "name" in first_result, "Result should contain name"
    assert "rank" in first_result, "Result should contain rank"
    # Check that we got reasonable coordinates for Paris (approximately at lon 2.3522, lat 48.8566)
    lon = first_result["longitude"]
    lat = first_result["latitude"]
    assert -5 < lon < 10, f"Longitude {lon} is not in expected range for Paris"
    assert 45 < lat < 52, f"Latitude {lat} is not in expected range for Paris"


@pytest.mark.asyncio
async def test_create_route_hgv_restrictions_sent() -> None:
    """driving-hgv with vehicle dimensions must build the ORS options.profile_params.restrictions payload."""
    fake_client = _FakeClient()
    original_no_save = settings.no_save
    settings.no_save = True  # skip GPX/image/HTML file writes, we only care about the outgoing request
    try:
        with patch("openroute_mcp.server.http_client", return_value=fake_client):
            await create_route_from_to(
                ctx=_fake_ctx(),
                route_type="driving-hgv",
                from_coordinates=[13.405, 52.52],  # Berlin
                to_coordinates=[11.582, 48.135],  # Munich
                hgv_height=3.06,
                hgv_width=2.34,
                hgv_length=7.29,
                hgv_weight=4.1,
            )
    finally:
        settings.no_save = original_no_save

    assert fake_client.last_url.endswith("/v2/directions/driving-hgv/gpx")
    assert fake_client.last_json is not None
    options = fake_client.last_json.get("options")
    assert options is not None, "driving-hgv with restrictions set must send an 'options' key"
    assert options["vehicle_type"] == "hgv"
    assert options["profile_params"]["restrictions"] == {
        "height": 3.06,
        "width": 2.34,
        "length": 7.29,
        "weight": 4.1,
    }


@pytest.mark.asyncio
async def test_create_route_hgv_without_restrictions_omits_options() -> None:
    """driving-hgv without any vehicle dimensions must not send an empty/partial options key."""
    fake_client = _FakeClient()
    original_no_save = settings.no_save
    settings.no_save = True
    try:
        with patch("openroute_mcp.server.http_client", return_value=fake_client):
            await create_route_from_to(
                ctx=_fake_ctx(),
                route_type="driving-hgv",
                from_coordinates=[13.405, 52.52],
                to_coordinates=[11.582, 48.135],
            )
    finally:
        settings.no_save = original_no_save

    assert fake_client.last_json is not None
    assert "options" not in fake_client.last_json


@pytest.mark.asyncio
async def test_create_route_car_ignores_hgv_args() -> None:
    """A non-hgv route_type must never send restrictions, even if hgv_* args are (mistakenly) passed."""
    fake_client = _FakeClient()
    original_no_save = settings.no_save
    settings.no_save = True
    try:
        with patch("openroute_mcp.server.http_client", return_value=fake_client):
            await create_route_from_to(
                ctx=_fake_ctx(),
                route_type="driving-car",
                from_coordinates=[13.405, 52.52],
                to_coordinates=[11.582, 48.135],
                hgv_height=3.06,
                hgv_weight=4.1,
            )
    finally:
        settings.no_save = original_no_save

    assert fake_client.last_json is not None
    assert "options" not in fake_client.last_json


# @pytest.mark.asyncio
# async def test_create_route_with_waypoints() -> None:
#     """Test creating a route with waypoints."""
#     # Test route creation with a waypoint
#     gpx = await create_route_from_to(
#         ctx=Context(),
#         route_type="foot-hiking",
#         from_coordinates=[6.911558, 46.43423],
#         to_coordinates=[6.63141, 46.520381],
#         waypoints=[[6.842412, 46.462626], [6.78249, 46.50093]],
#         # to_location="Hamburg, Germany",
#         # waypoints=["Potsdam, Germany"],
#     )
#     print(gpx)
#     # Check that we got valid GPX content
#     assert "<?xml" in gpx[0].text, "GPX should start with XML declaration"
#     assert "<gpx" in gpx[0].text, "GPX should contain gpx element"
#     assert "</gpx>" in gpx[0].text, "GPX should be well-formed"
