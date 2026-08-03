from __future__ import annotations

from unittest.mock import patch

from api.agent_narration import nearest_destination_chargers_from_ranked
from api.agent_trip_guide import build_trip_guide_response
from api.schemas import (
    ChargingPlanResponse,
    ConsumptionBinResult,
    ConsumptionProfileResponse,
    PlannedRouteStopResult,
    RouteEndpoint,
    RouteTripSummaryResult,
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


def test_trip_guide_context_includes_consumption_profile() -> None:
    station = _sample_station("s1", 40.5, -1.0, 150.0)
    plan = ChargingPlanResponse(
        mode="route",
        vehicle=VehicleEnergyInput(
            soc_percent=90,
            usable_capacity_kwh=75,
            consumption_wh_per_km=140.9,
            terrain_factor=1.0,
            reserve_soc_percent=10,
            consumption_kwh_per_100km=14.09,
        ),
        range_km=450,
        charging_reach_km=400,
        origin=RouteEndpoint(lat=37.6, lon=-0.98),
        destination=RouteEndpoint(lat=40.03, lon=-6.09),
        route_distance_km=650,
        route_duration_minutes=420,
        route_preference="fastest",
        soc_at_destination_pct=5,
        projected_soc_at_destination_with_plan=12,
        reachable_without_stop=False,
        stops=[],
        planned_stops=[
            PlannedRouteStopResult(
                order=1,
                station=station,
                deviation_km=1.2,
                route_distance_km=280,
                extra_minutes=4,
                wrong_side=False,
                distance_from_origin_km=280,
                leg_distance_km=280,
                leg_driving_minutes=160,
                soc_arrival_pct=18,
                soc_departure_pct=70,
                charge_minutes=28,
                classification="safe",
                leg_energy_kwh=39.5,
                recommended_charge_from_pct=18,
                recommended_charge_to_pct=70,
                effective_charge_power_kw=120,
                estimated_charge_cost_eur=12.5,
                operator="Ionity",
            )
        ],
        route_trip_summary=RouteTripSummaryResult(
            total_duration_minutes=448,
            driving_duration_minutes=420,
            total_charge_minutes=28,
            total_energy_kwh=91.5,
            estimated_charge_cost_eur=12.5,
            projected_destination_soc_pct=12,
            stop_count=1,
        ),
        strategies=[],
        warnings=[],
        candidates_in_bbox=3,
        consumption_source="historical",
        consumption_kwh_per_100km=14.09,
        consumption_confidence="medium",
        consumption_note="Histórico vía rápida 14.1 kWh/100 km · 12 viajes ≥20 km",
        consumption_bin="highway",
    )
    profile = ConsumptionProfileResponse(
        available=True,
        source="historical",
        lookback_days=0,
        min_distance_km=20,
        drive_count=166,
        car_id=1,
        bins={
            "highway": ConsumptionBinResult(
                bin="highway",
                wh_per_km=140.9,
                kwh_per_100km=14.09,
                sample_count=12,
                total_distance_km=2000,
            ),
            "mixed": ConsumptionBinResult(
                bin="mixed",
                wh_per_km=132.9,
                kwh_per_100km=13.29,
                sample_count=34,
                total_distance_km=1500,
            ),
            "conventional": ConsumptionBinResult(
                bin="conventional",
                wh_per_km=130.6,
                kwh_per_100km=13.06,
                sample_count=47,
                total_distance_km=1200,
            ),
            "mountain": ConsumptionBinResult(
                bin="mountain",
                wh_per_km=144.5,
                kwh_per_100km=14.45,
                sample_count=73,
                total_distance_km=3000,
            ),
        },
    )
    with patch("api.agent_trip_guide.dify_trip_guide_configured", return_value=False):
        guide = build_trip_guide_response(
            plan,
            destination_label="Plasencia",
            cultural_poi_enabled=False,
            consumption_profile=profile,
            consumption_source="historical",
            consumption_kwh_per_100km=14.09,
            consumption_confidence="medium",
            consumption_note=plan.consumption_note,
            consumption_bin="highway",
        )

    ctx = guide.context
    assert ctx.consumption_profile is not None
    assert ctx.consumption_profile.available is True
    assert ctx.consumption_profile.bins["highway"].sample_count == 12
    assert ctx.consumption_note and "Histórico" in ctx.consumption_note
    assert ctx.consumption_kwh_per_100km == 14.09
    assert ctx.plan_snapshot.get("route_trip_summary") is not None
    assert ctx.plan_snapshot["planned_stops"][0]["leg_energy_kwh"] == 39.5
    assert ctx.plan_snapshot["planned_stops"][0]["recommended_charge_from_pct"] == 18
    assert "Consumo del plan" in guide.guide_text
    assert "14.1" in guide.guide_text or "14.09" in guide.guide_text
    assert "Resumen REVE" in guide.guide_text
    assert "highway 14.1" in guide.guide_text
