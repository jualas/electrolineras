from __future__ import annotations

from unittest.mock import patch

from api.agent_narration import nearest_destination_chargers_from_ranked
from api.agent_trip_guide import build_trip_guide_context, build_trip_guide_response
from api.schemas import (
    ChargingPlanResponse,
    PlannedRouteStopResult,
    RouteEndpoint,
    VehicleEnergyInput,
)
from models.station import Connector, Station, StationLocation


def _sample_station(id: str, lat: float, lon: float, kw: float) -> Station:
    return Station(
        id=id,
        source="test",
        country="ES",
        site_name=f"Station {id}",
        operator="Op",
        location=StationLocation(lat=lat, lon=lon, address="Addr"),
        connectors=[Connector(connector_type="CCS", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=id,
    )


def test_nearest_destination_chargers_from_ranked() -> None:
    ranked = [
        (_sample_station("a", 40.0, -3.7, 150.0), 2.5),
        (_sample_station("b", 40.01, -3.71, 22.0), 5.0),
    ]
    options = nearest_destination_chargers_from_ranked(ranked, limit=2)
    assert len(options) == 2
    assert options[0].station_id == "a"
    assert options[0].power_band == "hpc"
    assert options[1].power_band == "ac_slow"


def test_build_trip_guide_response_deterministic() -> None:
    plan = ChargingPlanResponse(
        mode="route",
        vehicle=VehicleEnergyInput(
            soc_percent=70,
            usable_capacity_kwh=50,
            consumption_wh_per_km=150,
            terrain_factor=1.0,
            reserve_soc_percent=10,
        ),
        range_km=200,
        charging_reach_km=180,
        origin=RouteEndpoint(lat=40.0, lon=-3.7),
        destination=RouteEndpoint(lat=41.0, lon=2.0),
        route_distance_km=500,
        route_duration_minutes=300,
        soc_at_destination_pct=25,
        reachable_without_stop=False,
        stops=[],
        strategies=[],
        warnings=[],
        candidates_in_bbox=1,
    )
    with patch("api.agent_trip_guide.dify_trip_guide_configured", return_value=False):
        guide = build_trip_guide_response(plan, destination_label="Barcelona", cultural_poi_enabled=False)
    assert guide.guide_source == "deterministic"
    assert "Resumen del viaje" in guide.guide_text
    assert guide.context.destination_label == "Barcelona"


def test_plan_snapshot_marks_micro_stop() -> None:

    stop = PlannedRouteStopResult(
        order=1,
        station=_sample_station("totana", 37.77, -1.45, 250.0),
        deviation_km=1.0,
        route_distance_km=50.0,
        extra_minutes=2.0,
        wrong_side=True,
        distance_from_origin_km=50.0,
        leg_distance_km=50.0,
        soc_arrival_pct=56.0,
        soc_departure_pct=61.0,
        charge_minutes=5.0,
        classification="safe",
    )
    plan = ChargingPlanResponse(
        mode="route",
        vehicle=VehicleEnergyInput(
            soc_percent=80,
            usable_capacity_kwh=57,
            consumption_wh_per_km=160,
            terrain_factor=1.0,
            reserve_soc_percent=10,
        ),
        range_km=200,
        charging_reach_km=180,
        origin=RouteEndpoint(lat=37.6, lon=-0.96),
        destination=RouteEndpoint(lat=38.7, lon=-5.5),
        route_distance_km=520,
        route_duration_minutes=400,
        soc_at_destination_pct=10,
        reachable_without_stop=False,
        stops=[],
        planned_stops=[stop],
        strategies=[],
        warnings=[],
        candidates_in_bbox=1,
        destination_stay=None,
    )
    ctx = build_trip_guide_context(plan, destination_label="Puerto Urraco")
    snap = ctx.plan_snapshot["planned_stops"][0]
    assert snap["micro_stop"] is True
    assert snap["charge_worthwhile"] is False
    assert snap["wrong_side"] is True
    assert ctx.plan_snapshot["ev_expert"]["eta_note"] == "osrm_speed_adjusted_no_live_traffic"
    assert ctx.plan_snapshot["ev_expert"]["destination_rural"] is False
