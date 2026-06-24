from __future__ import annotations

from api.routing.corridor import RoutePolyline, rank_stations_along_route
from models.station import Connector, Station, StationLocation


def _station(id: str, lat: float, lon: float, kw: float = 150.0) -> Station:
    return Station(
        id=id,
        source="es-nap-dgt",
        country="ES",
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="ccs", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=id,
    )


def test_excludes_station_behind_origin() -> None:
    # Ruta horizontal hacia el este
    polyline = RoutePolyline([(0.0, 40.0), (1.0, 40.0)])
    behind = _station("behind", 40.0, -0.2)
    ahead = _station("ahead", 40.0, 0.5)

    matches = rank_stations_along_route(
        polyline,
        [behind, ahead],
        origin_lat=40.0,
        origin_lon=0.1,
        corridor_m=50_000,
        behind_margin_m=2_000,
        wrong_side_penalty_m=5_000,
        average_speed_mps=25.0,
        limit=10,
    )

    ids = [match.station.id for match in matches]
    assert "ahead" in ids
    assert "behind" not in ids


def test_excludes_station_outside_corridor() -> None:
    polyline = RoutePolyline([(0.0, 40.0), (1.0, 40.0)])
    far = _station("far", 41.5, 0.5)

    matches = rank_stations_along_route(
        polyline,
        [far],
        origin_lat=40.0,
        origin_lon=0.0,
        corridor_m=5_000,
        behind_margin_m=2_000,
        wrong_side_penalty_m=5_000,
        average_speed_mps=25.0,
        limit=10,
    )

    assert matches == []


def test_orders_by_deviation_then_power() -> None:
    polyline = RoutePolyline([(0.0, 40.0), (1.0, 40.0)])
    close_low = _station("close-low", 40.01, 0.5, kw=100.0)
    close_high = _station("close-high", 40.01, 0.5, kw=350.0)
    farther = _station("farther", 40.05, 0.5, kw=400.0)

    matches = rank_stations_along_route(
        polyline,
        [farther, close_low, close_high],
        origin_lat=40.0,
        origin_lon=0.0,
        corridor_m=20_000,
        behind_margin_m=2_000,
        wrong_side_penalty_m=5_000,
        average_speed_mps=25.0,
        limit=10,
    )

    assert [match.station.id for match in matches[:2]] == ["close-high", "close-low"]
    assert matches[2].station.id == "farther"
