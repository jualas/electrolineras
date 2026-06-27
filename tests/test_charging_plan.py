from __future__ import annotations

from api.routing.charging_plan import (
    VehicleEnergyProfile,
    build_emergency_charging_plan,
    build_route_charging_plan,
    classify_soc_arrival,
    estimate_range_km,
    soc_at_distance_km,
)
from api.routing.corridor import CorridorMatch
from models.station import Connector, Station, StationLocation


def sample_station(station_id: str, lat: float, lon: float, kw: float = 150.0, price: float | None = None) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="ccs", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=station_id,
        dynamic_price_eur_kwh=price,
    )


def test_estimate_range_model3_sr() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=80,
        usable_capacity_kwh=57,
        consumption_wh_per_km=142,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    range_km = estimate_range_km(profile)
    assert 250 < range_km < 290


def test_soc_at_distance_sierra_factor() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=80,
        usable_capacity_kwh=57,
        consumption_wh_per_km=142,
        terrain_factor=1.25,
        reserve_soc_percent=10,
    )
    soc_100km = soc_at_distance_km(profile, 100)
    assert 45 < soc_100km < 52


def test_classify_soc_arrival_levels() -> None:
    assert classify_soc_arrival(20, within_range=True) == "safe"
    assert classify_soc_arrival(12, within_range=True) == "adjusted"
    assert classify_soc_arrival(5, within_range=True) == "critical"
    assert classify_soc_arrival(50, within_range=False) == "unreachable"


def test_build_route_charging_plan_ranks_by_classification() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=35,
        usable_capacity_kwh=57,
        consumption_wh_per_km=150,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    matches = [
        CorridorMatch(
            station=sample_station("near-critical", 40.0, 0.4, price=0.55),
            deviation_m=500,
            route_position_m=40_000,
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("safe-stop", 40.0, 0.2, price=0.45),
            deviation_m=800,
            route_position_m=20_000,
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    plan = build_route_charging_plan(
        matches,
        origin_position_km=0.0,
        destination_distance_km=120.0,
        profile=profile,
        limit=5,
    )
    assert plan.stops[0].classification == "safe"
    assert plan.strategies[0].station_id == plan.stops[0].station.id
    assert plan.soc_at_destination_pct is not None
    assert plan.reachable_without_stop is False


def test_build_emergency_charging_plan() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=25,
        usable_capacity_kwh=57,
        consumption_wh_per_km=160,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    stations = [
        (sample_station("close", 40.01, 0.01, price=0.39), 1.2),
        (sample_station("far", 40.05, 0.05, price=0.30), 80.0),
    ]
    plan = build_emergency_charging_plan(stations, profile=profile, limit=5)
    assert plan.stops
    assert plan.stops[0].station.id == "close"
    assert plan.strategies[0].station_id is not None
