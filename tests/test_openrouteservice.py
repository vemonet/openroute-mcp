"""Test OpenRouteService integration."""

import pytest

from openroute_mcp.server import create_route_from_to, search_location_coordinates


@pytest.mark.asyncio
async def test_search_location_coordinates():
    """Test geocoding a location."""
    res = await search_location_coordinates("Paris, France")
    # Check that we got reasonable coordinates for Paris, approximately at longitude 2.3522, latitude 48.8566
    # assert -5 < lon < 10, f"Longitude {lon} is not in expected range for Paris"
    # assert 45 < lat < 52, f"Latitude {lat} is not in expected range for Paris"
    print(res)
    assert "Address:" in res, "Result should contain address information"


@pytest.mark.asyncio
async def test_create_route_with_waypoints():
    """Test creating a route with waypoints."""
    # Test route creation with a waypoint
    gpx = await create_route_from_to(
        route_type="foot-hiking",
        from_coordinates=[6.911558, 46.43423],
        to_coordinates=[6.63141, 46.520381],
        waypoints=[[6.842412, 46.462626], [6.78249, 46.50093]],
        # to_location="Hamburg, Germany",
        # waypoints=["Potsdam, Germany"],
    )
    print(gpx)
    # Check that we got valid GPX content
    assert "<?xml" in gpx[0].text, "GPX should start with XML declaration"
    assert "<gpx" in gpx[0].text, "GPX should contain gpx element"
    assert "</gpx>" in gpx[0].text, "GPX should be well-formed"


# @pytest.mark.asyncio
# async def test_create_route_from_to():
#     """Test creating a complete route."""
#     # Test route creation between two well-known locations
#     gpx = await create_route_from_to(
#         route_type="foot-hiking",
#         from_location="Heidelberg, Germany",
#         to_location="Mannheim, Germany",
#         waypoints=[]
#     )

#     # Check that we got valid GPX content
#     assert "<?xml" in gpx, "GPX should start with XML declaration"
#     assert "<gpx" in gpx, "GPX should contain gpx element"
#     assert "</gpx>" in gpx, "GPX should be well-formed"
#     assert "<trk>" in gpx or "<rte>" in gpx, "GPX should contain track or route data"


# @pytest.mark.asyncio
# async def test_geocode_location_not_found():
#     """Test geocoding fails when location not found."""
#     with pytest.raises(ValueError, match="Could not geocode location"):
#         await geocode_location("ThisIsDefinitelyNotARealPlaceXYZ123456789")
