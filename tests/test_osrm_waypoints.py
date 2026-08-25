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


def test_user_itinerary_ship_to_cantos_to_cuenca_to_cartagena_path() -> None:
    """Repro Asistente: origen≈destino Cartagena con vías Madrid/Cuenca."""
    origin = (37.625, -0.996)
    tres_cantos = (40.6008, -3.7081)
    villaconejos = (40.4167, -2.3167)
    dest = (37.625, -1.01)
    path = osrm_coordinates_path(
        *origin,
        *dest,
        waypoints=[tres_cantos, villaconejos],
    )
    assert path.count(";") == 3
    loop_km = geodesic_path_km(*origin, *dest, waypoints=[tres_cantos, villaconejos])
    assert loop_km > 500
