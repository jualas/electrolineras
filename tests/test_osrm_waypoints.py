from api.routing.osrm import geodesic_path_km, osrm_coordinates_path


def test_osrm_coordinates_path_with_waypoints() -> None:
    path = osrm_coordinates_path(
        37.625,
        -0.996,
        37.625,
        -0.996,
        waypoints=[(37.992, -1.131)],
    )
    assert path == "-0.996,37.625;-1.131,37.992;-0.996,37.625"


def test_geodesic_path_round_trip_not_zero() -> None:
    home = (37.625, -0.996)
    murcia = (37.9922, -1.1307)
    assert geodesic_path_km(*home, *home) == 0.0
    loop_km = geodesic_path_km(*home, *home, waypoints=[murcia])
    assert loop_km > 80
