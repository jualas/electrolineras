from __future__ import annotations

from api.routing.corridor import RoutePolyline, rank_stations_along_route_for_planning
from models.station import Connector, Station, StationLocation


def _station(station_id: str, lat: float, lon: float) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="ccs", power_kw=150.0)],
        max_power_kw=150.0,
        raw_ref=station_id,
    )


def test_planning_corridor_covers_route_length() -> None:
    """Los candidatos de planificación deben repartirse a lo largo de la ruta, no solo al inicio."""
    route = RoutePolyline(
        [
            (0.0, 37.0),
            (0.5, 37.5),
            (1.0, 38.0),
            (2.0, 39.0),
            (3.0, 40.0),
        ],
    )
    stations: list[Station] = []
    for index in range(40):
        km_fraction = index / 39
        lon = km_fraction * 3.0
        lat = 37.0 + km_fraction * 3.0
        stations.append(_station(f"s-{index}", lat, lon))

    matches = rank_stations_along_route_for_planning(
        route,
        stations,
        origin_lat=37.0,
        origin_lon=0.0,
        corridor_m=15_000,
        behind_margin_m=2000,
        wrong_side_penalty_m=5000,
        average_speed_mps=25.0,
        route_distance_km=route.length_m / 1000.0,
        segment_km=30.0,
        per_segment=5,
    )
    assert len(matches) >= 10
    positions_km = [match.route_position_m / 1000.0 for match in matches]
    assert max(positions_km) > route.length_m / 1000.0 * 0.55
    assert min(positions_km) < route.length_m / 1000.0 * 0.2
