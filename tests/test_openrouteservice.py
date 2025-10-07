"""Test OpenRouteService integration."""

import pytest

from openroute_mcp.server import search_location_coordinates

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
