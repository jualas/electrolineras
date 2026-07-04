from __future__ import annotations

from api.agent_narration import build_agent_narration
from api.agent_trip_guide import build_trip_guide_context, format_deterministic_guide
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


def _planned_stop(order: int, station_id: str, route_km: float, leg_km: float) -> PlannedRouteStopResult:
    return PlannedRouteStopResult(
        order=order,
        station=_sample_station(station_id, 40.0 + order * 0.1, -3.7 + order * 0.1, 150.0),
        deviation_km=1.2,
        route_distance_km=route_km,
        extra_minutes=4.0,
        wrong_side=False,
        distance_from_origin_km=route_km,
        leg_distance_km=leg_km,
        soc_arrival_pct=18.0,
        soc_departure_pct=72.0,
        charge_minutes=22.0,
        classification="safe",
    )


def test_build_agent_narration_includes_planned_stops() -> None:
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
        geodesic_distance_km=303.0,
        route_distance_km=344.0,
        route_shortest_distance_km=344.0,
        route_fastest_distance_km=357.0,
        route_conventional_distance_km=407.0,
        route_variants_approximate=False,
        route_preference="shortest",
        soc_at_destination_pct=-5.0,
        projected_soc_at_destination_with_plan=32.0,
        reachable_without_stop=False,
        stops=[],
        planned_stops=[
            _planned_stop(1, "mid", 170.0, 170.0),
            _planned_stop(2, "far", 320.0, 150.0),
        ],
        strategies=[],
        warnings=[],
        candidates_in_bbox=2,
    )

    summary, bullets = build_agent_narration(plan)

    assert "Plan multi-parada: 2 parada(s)" in " ".join(bullets)
    assert any("Parada 1:" in bullet for bullet in bullets)
    assert any("Parada 2:" in bullet for bullet in bullets)
    assert any("~32 %" in bullet for bullet in bullets)
    assert any("más directa" in bullet for bullet in bullets)
    assert summary


def test_trip_guide_context_includes_planned_stops_snapshot() -> None:
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
        route_preference="fastest",
        soc_at_destination_pct=25,
        projected_soc_at_destination_with_plan=31.0,
        reachable_without_stop=False,
        stops=[],
        planned_stops=[_planned_stop(1, "only", 250.0, 250.0)],
        strategies=[],
        warnings=[],
        candidates_in_bbox=1,
    )

    context = build_trip_guide_context(plan, destination_label="Valencia")
    snapshot = context.plan_snapshot

    assert snapshot["route_preference"] == "fastest"
    assert len(snapshot["planned_stops"]) == 1
    assert snapshot["planned_stops"][0]["order"] == 1
    assert snapshot["projected_soc_at_destination_with_plan"] == 31.0

    guide = format_deterministic_guide("Resumen", ["bullet"], context)
    assert "### Paradas planificadas" in guide
    assert "SOC estimado en destino con plan" in guide
    assert "### Comparativa de rutas" in guide
