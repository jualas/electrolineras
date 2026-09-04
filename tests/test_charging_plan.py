from __future__ import annotations

import pytest

from api.routing.charging_plan import (
    VehicleEnergyProfile,
    build_emergency_charging_plan,
    build_route_charging_plan,
    classify_soc_arrival,
    estimate_charging_reach_km,
    estimate_charging_stops_needed,
    estimate_range_km,
    soc_at_distance_km,
)
from api.routing.corridor import CorridorMatch
from models.station import Connector, Station, StationLocation


def sample_station(
    station_id: str,
    lat: float,
    lon: float,
    kw: float = 150.0,
    price: float | None = None,
    operator: str | None = None,
) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="ccs", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=station_id,
        dynamic_price_eur_kwh=price,
        operator=operator,
    )


def test_estimate_range_model3_sr() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=80,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    range_km = estimate_range_km(profile)
    assert 290 < range_km < 300


def test_estimate_charging_stops_needed() -> None:
    assert estimate_charging_stops_needed(741, 188) == 3
    assert estimate_charging_stops_needed(100, 188) == 0


def test_clamp_display_soc_pct() -> None:
    from api.routing.charging_plan import clamp_display_soc_pct

    assert clamp_display_soc_pct(-175) == 0.0
    assert clamp_display_soc_pct(55) == 55.0


def test_soc_at_distance_sierra_factor() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=80,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
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
    assert any(strategy.id == "charge_now" for strategy in plan.strategies)
    assert plan.soc_at_destination_pct is not None
    assert plan.reachable_without_stop is False


def test_build_route_charging_plan_with_origin_stops() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=15,
        usable_capacity_kwh=57,
        consumption_wh_per_km=150,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    corridor_matches = [
        CorridorMatch(
            station=sample_station("far-on-route", 40.0, 0.8, price=0.45),
            deviation_m=500,
            route_position_m=80_000,
            extra_minutes=5.0,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    origin_near = build_emergency_charging_plan(
        [(sample_station("near-home", 40.001, 0.001, price=0.42), 2.0)],
        profile=profile,
        limit=5,
    )
    plan = build_route_charging_plan(
        corridor_matches,
        origin_position_km=0.0,
        destination_distance_km=120.0,
        profile=profile,
        origin_stops=origin_near.stops,
        limit=5,
    )
    assert plan.origin_stops
    assert plan.origin_stops[0].station.id == "near-home"
    assert plan.stops[0].classification == "unreachable"
    assert any(strategy.id == "charge_at_origin" for strategy in plan.strategies)


def test_charging_reach_low_soc_vs_planning_range() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=15,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        terrain_factor=1.0,
        reserve_soc_percent=10,
    )
    plan_range = estimate_range_km(profile)
    charge_reach = estimate_charging_reach_km(profile)
    assert plan_range < 25
    assert 35 < charge_reach < 48
    assert classify_soc_arrival(5.0, within_range=True) == "critical"


def test_build_planned_route_stops_multi_hop_cartagena_style() -> None:
    """Viaje ~741 km con autonomía ~188 km → paradas planificadas con tramos ~2 h."""
    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    range_km = estimate_range_km(profile)
    assert 370 < range_km < 385

    destination_km = 741.0
    route_duration_minutes = 420.0  # ~106 km/h media
    positions_km = [250.0, 480.0, 700.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"stop-{idx}", 40.0, 0.1 * idx, kw=150.0, price=0.40 + idx * 0.01),
            deviation_m=400,
            route_position_m=int(km * 1000),
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions_km, start=1)
    ]

    from api.routing.charging_plan import build_planned_route_stops

    planned, warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=destination_km,
        profile=profile,
        route_distance_km=destination_km,
        route_duration_minutes=route_duration_minutes,
    )
    assert len(planned) >= 2
    assert [stop.order for stop in planned] == list(range(1, len(planned) + 1))
    assert planned[0].route_distance_km < planned[-1].route_distance_km
    assert all(stop.soc_departure_pct > stop.soc_arrival_pct for stop in planned)
    assert all(stop.charge_minutes >= 0 for stop in planned)
    assert all(stop.leg_driving_minutes <= 185 for stop in planned)
    assert projected is not None
    assert projected >= 0


def test_planned_stops_monotonic_and_short_charge_strategy() -> None:
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=60,
        consumption_wh_per_km=170,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
        max_charge_power_kw=100,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    # Tras target 135 min / min progress 0.85: 2.ª parada debe quedar dentro de alcance (~≤460 km)
    positions_km = [250.0, 440.0, 630.0, 780.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"stop-{idx}", 40.0, 0.1 * idx, kw=200.0),
            deviation_m=400,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions_km, start=1)
    ]
    planned, _, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=812.0,
        profile=profile,
        route_distance_km=812.0,
        route_duration_minutes=560.0,
    )
    assert len(planned) >= 2
    kms = [s.distance_from_origin_km for s in planned]
    assert all(kms[i] < kms[i + 1] for i in range(len(kms) - 1))
    for stop in planned[:-1]:
        assert stop.soc_departure_pct <= 72.0
        assert stop.charge_minutes <= 35.0
    assert projected is not None


def test_origin_exclusion_disabled_battery_only() -> None:
    from api.routing.charging_plan import estimate_charging_reach_km, origin_exclusion_radius_km

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=361,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    reach = estimate_charging_reach_km(profile)
    exclusion = origin_exclusion_radius_km(176.0, 100.0, charging_reach_km=reach)
    assert reach == pytest.approx(150.0, abs=1.0)
    assert exclusion == 0.0



def test_telemetry_capacity_model_3_50() -> None:
    from api.integrations.telemetry_energy import resolve_telemetry_capacity_kwh
    from api.integrations.teslamate import VehicleTelemetry

    telemetry = VehicleTelemetry(
        car_id=1,
        display_name="The Ship",
        state="online",
        lat=37.6,
        lon=-1.0,
        battery_level_pct=39.0,
        usable_battery_level_pct=39.0,
        est_battery_range_km=483.0,
        rated_battery_range_km=158.0,
        model="3",
        trim_badging="50",
        car_model_label="Model 3 50",
    )
    assert resolve_telemetry_capacity_kwh(telemetry=telemetry) == 57.5


def test_no_planned_stops_near_origin_when_soc_100() -> None:
    """Con SOC alto, preferir parada cerca del final del alcance (no micro-parada al inicio)."""
    from api.routing.charging_plan import build_planned_route_stops, estimate_charging_reach_km

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    route_km = 808.0
    route_duration = 480.0
    reach = estimate_charging_reach_km(profile)
    far_in_reach_km = max(80.0, reach * 0.88)

    matches = [
        CorridorMatch(
            station=sample_station("near-1", 40.0, 0.01, kw=150.0),
            deviation_m=300,
            route_position_m=1_000,
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("near-5", 40.0, 0.02, kw=150.0),
            deviation_m=300,
            route_position_m=5_000,
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("near-end-reach", 40.5, 0.5, kw=200.0),
            deviation_m=400,
            route_position_m=int(far_in_reach_km * 1000),
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("mid", 41.0, 0.8, kw=200.0),
            deviation_m=400,
            route_position_m=450_000,
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("late", 41.5, 1.1, kw=200.0),
            deviation_m=400,
            route_position_m=650_000,
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    planned, _, _ = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=route_km,
        profile=profile,
        route_distance_km=route_km,
        route_duration_minutes=route_duration,
    )
    assert planned
    assert planned[0].station.id == "near-end-reach"
    assert planned[0].route_distance_km >= 50


def test_faster_charger_preferred_for_similar_position() -> None:
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    matches = [
        CorridorMatch(
            station=sample_station("slow", 40.0, 0.1, kw=50.0, price=0.35),
            deviation_m=400,
            route_position_m=250_000,
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("fast", 40.0, 0.2, kw=250.0, price=0.45),
            deviation_m=400,
            route_position_m=250_000,
            extra_minutes=3.0,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    planned, _, _ = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=741.0,
        profile=profile,
        route_distance_km=741.0,
        route_duration_minutes=420.0,
    )
    assert planned
    assert planned[0].station.id == "fast"


def test_build_route_charging_plan_includes_planned_stops() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    matches = [
        CorridorMatch(
            station=sample_station("mid-stop", 40.0, 0.5, kw=150.0, price=0.42),
            deviation_m=500,
            route_position_m=250_000,
            extra_minutes=4.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("far-stop", 40.0, 0.8, kw=150.0, price=0.38),
            deviation_m=600,
            route_position_m=480_000,
            extra_minutes=5.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("last-stop", 40.0, 0.9, kw=150.0, price=0.36),
            deviation_m=600,
            route_position_m=700_000,
            extra_minutes=5.0,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    plan = build_route_charging_plan(
        matches,
        origin_position_km=0.0,
        destination_distance_km=741.0,
        profile=profile,
        limit=5,
        route_distance_km=741.0,
        route_duration_minutes=420.0,
    )
    assert len(plan.planned_stops) >= 2
    assert plan.projected_soc_at_destination_with_plan is not None


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
    assert any(strategy.id == "charge_at_origin" for strategy in plan.strategies)


def test_planned_stops_prefer_two_hour_spacing_over_one_hour() -> None:
    """En fastest, un candidato ~1 h se descarta frente a uno ~2–2:30 h."""
    from api.routing.charging_plan import build_planned_route_stops_greedy

    profile = VehicleEnergyProfile(
        soc_percent=80,
        usable_capacity_kwh=60,
        consumption_wh_per_km=150,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        vehicle_preset_id="tesla-model3-sr-2023",
        max_charge_power_kw=100,
    )
    # ~106 km/h → target 135 min ≈ 239 km; min highway 0.90 ≈ 215 km
    matches = [
        CorridorMatch(
            station=sample_station("early", 40.0, 0.1, kw=150.0, operator="Ionity"),
            deviation_m=200,
            route_position_m=120_000,
            extra_minutes=1.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("target", 40.0, 0.2, kw=150.0, operator="Ionity"),
            deviation_m=300,
            route_position_m=240_000,
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        ),
        CorridorMatch(
            station=sample_station("later", 40.0, 0.3, kw=150.0, operator="Ionity"),
            deviation_m=300,
            route_position_m=460_000,
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        ),
    ]
    planned, _, _ = build_planned_route_stops_greedy(
        matches,
        origin_position_km=0.0,
        destination_distance_km=700.0,
        profile=profile,
        route_distance_km=700.0,
        route_duration_minutes=396.0,
        route_preference="fastest",
    )
    assert planned
    assert planned[0].station.id == "target"
    assert planned[0].leg_driving_minutes >= 110


def test_tesla_on_route_preferred_over_nearby_other_operator() -> None:
    from api.routing.charging_plan import ScoredChargingStop, _planned_stop_selection_key
    from api.routing.charging_preferences import ChargingPreferences

    prefs = ChargingPreferences(preferred_operators=("tesla",))
    tesla = ScoredChargingStop(
        station=sample_station("tesla-sc", 40.0, 0.1, kw=250.0, operator="Tesla Supercharger"),
        deviation_km=0.5,
        route_distance_km=240.0,
        extra_minutes=1.0,
        wrong_side=False,
        distance_from_origin_km=240.0,
        soc_arrival_pct=18.0,
        classification="safe",
    )
    other = ScoredChargingStop(
        station=sample_station("ionity", 40.0, 0.11, kw=250.0, operator="Ionity"),
        deviation_km=0.4,
        route_distance_km=241.0,
        extra_minutes=1.0,
        wrong_side=False,
        distance_from_origin_km=241.0,
        soc_arrival_pct=17.5,
        classification="safe",
    )
    key_tesla = _planned_stop_selection_key(
        tesla,
        charge_minutes=20.0,
        target_stop_km=240.0,
        preferences=prefs,
    )
    key_other = _planned_stop_selection_key(
        other,
        charge_minutes=20.0,
        target_stop_km=240.0,
        preferences=prefs,
    )
    assert key_tesla < key_other


def test_tesla_high_deviation_loses_to_low_deviation_other() -> None:
    from api.routing.charging_plan import ScoredChargingStop, _planned_stop_selection_key
    from api.routing.charging_preferences import ChargingPreferences

    prefs = ChargingPreferences(preferred_operators=("tesla",))
    tesla = ScoredChargingStop(
        station=sample_station("tesla-far", 40.0, 0.1, kw=250.0, operator="Tesla"),
        deviation_km=8.0,
        route_distance_km=240.0,
        extra_minutes=8.0,
        wrong_side=False,
        distance_from_origin_km=240.0,
        soc_arrival_pct=18.0,
        classification="safe",
    )
    other = ScoredChargingStop(
        station=sample_station("ionity-near", 40.0, 0.11, kw=250.0, operator="Ionity"),
        deviation_km=0.5,
        route_distance_km=240.0,
        extra_minutes=1.0,
        wrong_side=False,
        distance_from_origin_km=240.0,
        soc_arrival_pct=18.0,
        classification="safe",
    )
    key_tesla = _planned_stop_selection_key(
        tesla,
        charge_minutes=20.0,
        target_stop_km=240.0,
        preferences=prefs,
    )
    key_other = _planned_stop_selection_key(
        other,
        charge_minutes=20.0,
        target_stop_km=240.0,
        preferences=prefs,
    )
    assert key_other < key_tesla


def test_intermediate_legs_not_much_shorter_than_target() -> None:
    """#6140: tras 1.ª parada ~2h, la 2.ª no debe caer a ~1h si hay candidatos ~2h."""
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        vehicle_preset_id="tesla-model3-sr-2023",
        max_charge_power_kw=170,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    # ~90 km/h → target 135 min ≈ 202 km. Candidatos: ~200, luego corto 300, luego ~400.
    positions = [200.0, 300.0, 410.0, 620.0, 800.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"s{idx}", 38.0 + idx * 0.01, -1.5 + idx * 0.1, kw=250.0),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions, start=1)
    ]
    planned, _, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=900.0,
        profile=profile,
        route_distance_km=900.0,
        route_duration_minutes=600.0,
        route_preference="fastest",
    )
    assert projected is not None
    assert len(planned) >= 2
    for stop in planned:
        # Evitar el patrón 1h–1:30 entre paradas intermedias (salvo tramo final corto).
        if stop.order < len(planned):
            assert stop.leg_driving_minutes >= 110, (
                f"tramo #{stop.order} demasiado corto: {stop.leg_driving_minutes} min @ {stop.distance_from_origin_km} km"
            )


def test_slow_shortest_style_route_still_plans_stops() -> None:
    """#6140 / #6162: ruta lenta sigue planificando; sin techo por tiempo de conducción."""
    from api.routing.charging_plan import build_planned_route_stops, estimate_charging_reach_km

    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=57,
        consumption_wh_per_km=136,
        vehicle_preset_id="tesla-model3-sr-2023",
        max_charge_power_kw=170,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    # Velocidad media ~64 km/h: max_leg ≈ 192 km. Candidatos dentro y fuera de la ventana.
    positions = [155.0, 177.0, 187.0, 228.0, 340.0, 480.0, 620.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"s{idx}", 38.0 + idx * 0.02, -1.2 + idx * 0.05, kw=200.0),
            deviation_m=300,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions, start=1)
    ]
    planned, warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=748.0,
        profile=profile,
        route_distance_km=748.0,
        route_duration_minutes=699.0,
        route_preference="shortest",
    )
    assert len(planned) >= 2, f"expected stops, got {planned!r}; warnings={warnings}"
    assert projected is not None
    # Autonomía-primero: 1.ª parada hacia el final del alcance (puede superar ~3 h a baja velocidad).
    assert planned[0].distance_from_origin_km <= estimate_charging_reach_km(profile) + 5
    assert planned[0].station.id in {"s3", "s4", "s2", "s1"}


def test_fastest_relaxes_origin_exclusion_when_reach_window_empty() -> None:
    """#6151 — rápida con SOC medio: sin DC en [~2 h, alcance] no debe dejar plan vacío.

    Corredor tipo Cartagena→interior: paradas tempranas (~50–90 km) y 1.ª DC «ideal»
    más allá del alcance (~200 km). Con exclusión ~2 h el plan fallaba; directa sí
    encontraba paradas por ir más despacio.
    """
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=45,
        usable_capacity_kwh=50,
        consumption_wh_per_km=122.0,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        max_charge_power_kw=150,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    # ~80 km/h → target ~2 h ≈ 180 km; alcance ~163 km → ventana [~133, 163] vacía.
    route_km = 503.0
    route_duration = 375.0
    positions = [48.0, 92.0, 198.0, 302.0, 400.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"s{idx}", 38.0 + idx * 0.02, -1.0 + idx * 0.05, kw=150.0),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions, start=1)
    ]
    planned, warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=route_km,
        profile=profile,
        route_distance_km=route_km,
        route_duration_minutes=route_duration,
        route_preference="fastest",
    )
    assert len(planned) >= 1, f"expected early stop, got {planned!r}; warnings={warnings}"
    assert planned[0].distance_from_origin_km < 160.0
    assert projected is not None
    assert planned[0].distance_from_origin_km < 120.0 or any(
        "anticipada" in w.lower() for w in warnings
    )


def test_first_stop_prefers_comfort_soc_over_two_hour_target() -> None:
    """1.ª parada ~2 h al ~6 % SOC no debe ganar a Hellín (~25 %) más temprano.

    Caso Ship→Riba: exclusión DGT deja Albacete (~198 km); Hellín (~128 km) está
    dentro del alcance y llega con batería cómoda.
    """
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=61,
        usable_capacity_kwh=57.5,
        consumption_wh_per_km=160.0,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        max_charge_power_kw=170,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    route_km = 503.0
    route_duration = 375.0
    positions = [128.0, 198.0, 302.0, 400.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"s{idx}", 38.0 + idx * 0.02, -1.0 + idx * 0.05, kw=150.0),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions, start=1)
    ]
    planned, warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=route_km,
        profile=profile,
        route_distance_km=route_km,
        route_duration_minutes=route_duration,
        route_preference="fastest",
    )
    assert len(planned) >= 1, f"expected stops, got {planned!r}; warnings={warnings}"
    assert planned[0].station.id == "s1"
    assert planned[0].distance_from_origin_km < 160.0
    assert planned[0].soc_arrival_pct >= 20.0
    assert any("anticipada" in w.lower() or "poca batería" in w.lower() for w in warnings)
    assert projected is not None


def test_spaced_leg_rejects_micro_soc_gain() -> None:
    """#6154: tramo ~2 h con +5 % SOC (Totana/Cúllar ~5 min) no es parada útil."""
    from api.routing.charging_plan import _is_worth_charging_stop

    assert not _is_worth_charging_stop(
        arrival_soc_pct=56.6,
        departure_soc_pct=61.6,
        charge_minutes=6.0,
        leg_distance_km=156.0,
        min_leg_km=120.0,
        stop_route_km=156.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=100.0,
        trip_start_soc_pct=100.0,
        avg_speed_kmh=56.0,
    )


def test_after_early_first_stop_still_fills_corridor() -> None:
    """#6156 / #6162 — 1.ª anticipada (comfort) no debe dejar hueco vacío en el corredor.

    Comfort puede elegir Lorca (~70 km); la siguiente parada debe seguir por autonomía
    (Cúllar / Linares), sin exigir espaciado ~2 h.
    """
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=55,
        usable_capacity_kwh=57.5,
        consumption_wh_per_km=160.0,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        max_charge_power_kw=170,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    route_km = 480.0
    route_duration = 480.0
    stations = [
        ("lorca", 70.0, 50.0),
        ("cullar", 156.0, 250.0),
        ("linares", 280.0, 150.0),
        ("andujar", 340.0, 150.0),
        ("pozoblanco", 410.0, 50.0),
    ]
    matches = [
        CorridorMatch(
            station=sample_station(sid, 37.5 + i * 0.1, -1.0 - i * 0.2, kw=kw),
            deviation_m=250,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for i, (sid, km, kw) in enumerate(stations)
    ]
    planned, warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=route_km,
        profile=profile,
        route_distance_km=route_km,
        route_duration_minutes=route_duration,
        route_preference="shortest",
    )
    assert len(planned) >= 2, f"expected ≥2 stops, got {planned!r}; warnings={warnings}"
    ids = {s.station.id for s in planned}
    assert "lorca" in ids or "cullar" in ids
    assert ids & {"cullar", "linares", "andujar"}
    assert projected is not None and projected > 0


def test_allows_origin_zone_at_exactly_ten_percent() -> None:
    """#6157 — SOC 10 % cuenta como zona origen (umbral inclusivo)."""
    from api.routing.charging_plan import allows_origin_zone_charging, origin_exclusion_radius_km

    assert allows_origin_zone_charging(10.0)
    assert allows_origin_zone_charging(9.0)
    assert not allows_origin_zone_charging(10.1)
    assert origin_exclusion_radius_km(180.0, 10.0, charging_reach_km=18.0, max_leg_km=200.0) == 0.0


def test_soc_ten_percent_plans_near_origin_then_continues() -> None:
    """#6157 — con SOC 10 % el plan debe incluir carga cerca de la salida y seguir.

    Antes el mínimo de tramo (~15–17 km) dejaba ventana [17, 18] vacía y planned_stops=[].
    """
    from api.routing.charging_plan import build_planned_route_stops

    profile = VehicleEnergyProfile(
        soc_percent=10,
        usable_capacity_kwh=57.5,
        consumption_wh_per_km=160.0,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        max_charge_power_kw=170,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    route_km = 480.0
    route_duration = 480.0
    stations = [
        ("origin_dc", 4.0, 150.0),
        ("mid_a", 160.0, 250.0),
        ("mid_b", 300.0, 150.0),
        ("late", 410.0, 100.0),
    ]
    matches = [
        CorridorMatch(
            station=sample_station(sid, 37.5 + i * 0.1, -1.0 - i * 0.2, kw=kw),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for i, (sid, km, kw) in enumerate(stations)
    ]
    planned, warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=route_km,
        profile=profile,
        route_distance_km=route_km,
        route_duration_minutes=route_duration,
        route_preference="shortest",
    )
    assert len(planned) >= 2, f"expected ≥2 stops, got {planned!r}; warnings={warnings}"
    assert planned[0].station.id == "origin_dc"
    assert planned[0].distance_from_origin_km < 20.0
    assert planned[0].soc_departure_pct >= 40.0
    assert projected is not None and projected > 0


def test_reachable_segment_candidates_battery_first() -> None:
    """#6158 — ventana = (current+forward, current+reach], sin exclusión DGT."""
    from api.routing.charging_plan import reachable_segment_candidates

    matches = [
        CorridorMatch(
            station=sample_station(f"s{i}", 38.0, -1.0 - i * 0.1, kw=150.0),
            deviation_m=100,
            route_position_m=int(km * 1000),
            extra_minutes=1.0,
            behind_route=False,
            wrong_side=False,
        )
        for i, km in enumerate([10.0, 70.0, 150.0, 220.0], start=1)
    ]
    cands, seg_min, seg_end = reachable_segment_candidates(
        matches,
        current_route_km=0.0,
        charging_reach_km=160.0,
        used_station_ids=set(),
        min_forward_km=5.0,
        remaining_km=500.0,
    )
    ids = [m.station.id for m in cands]
    assert ids == ["s1", "s2", "s3"]
    assert seg_min == 5.0
    assert seg_end == 160.0


def test_battery_first_matrix_soc_and_preferences() -> None:
    """#6158 — matriz mínima SOC × preferencia sobre un corredor tipo largo."""
    from api.routing.charging_plan import build_planned_route_stops

    stations = [
        ("near", 4.0, 150.0),
        ("early", 70.0, 50.0),
        ("mid", 156.0, 250.0),
        ("late", 280.0, 150.0),
        ("tail", 410.0, 100.0),
    ]
    matches = [
        CorridorMatch(
            station=sample_station(sid, 37.5 + i * 0.1, -1.0 - i * 0.2, kw=kw),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for i, (sid, km, kw) in enumerate(stations)
    ]
    route_km = 480.0

    def run(soc: float, pref: str, duration: float):
        profile = VehicleEnergyProfile(
            soc_percent=soc,
            usable_capacity_kwh=57.5,
            consumption_wh_per_km=160.0,
            terrain_factor=1.0,
            reserve_soc_percent=10,
            max_charge_power_kw=170,
            min_destination_soc_pct=10,
            min_stop_arrival_soc_pct=10,
            max_charge_soc_pct=80,
        )
        return build_planned_route_stops(
            matches,
            origin_position_km=0.0,
            destination_distance_km=route_km,
            profile=profile,
            route_distance_km=route_km,
            route_duration_minutes=duration,
            route_preference=pref,
        )

    # SOC 10: 1.ª cerca del origen y plan usable.
    for pref, dur in (("shortest", 480.0), ("fastest", 320.0)):
        planned, _, projected = run(10.0, pref, dur)
        assert len(planned) >= 2, f"SOC10 {pref}: {planned!r}"
        assert planned[0].distance_from_origin_km < 20.0
        assert projected is not None and projected > 0

    # SOC 55 directa: ≥2 paradas (no cortar en early).
    planned, _, projected = run(55.0, "shortest", 480.0)
    assert len(planned) >= 2, f"SOC55 shortest: {planned!r}"
    assert projected is not None and projected > 0

    # Madrid-like: hueco tras origen — bump o 2.ª parada.
    madrid_matches = [
        CorridorMatch(
            station=sample_station(sid, 40.0, -3.0 - i * 0.1, kw=kw),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for i, (sid, km, kw) in enumerate(
            [
                ("origin_dc", 3.0, 60.0),
                ("gap_a", 180.0, 150.0),
                ("gap_b", 320.0, 150.0),
                ("tail", 400.0, 100.0),
            ]
        )
    ]
    profile = VehicleEnergyProfile(
        soc_percent=10,
        usable_capacity_kwh=57.5,
        consumption_wh_per_km=160.0,
        terrain_factor=1.0,
        reserve_soc_percent=10,
        max_charge_power_kw=170,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    planned, warnings, projected = build_planned_route_stops(
        madrid_matches,
        origin_position_km=0.0,
        destination_distance_km=436.0,
        profile=profile,
        route_distance_km=436.0,
        route_duration_minutes=300.0,
        route_preference="shortest",
    )
    assert len(planned) >= 2, f"Madrid-like: {planned!r}; {warnings}"
    assert planned[0].distance_from_origin_km < 15.0
    assert projected is not None and projected > 0

    # SOC alto + viaje corto: 0–1 parada.
    short_matches = matches[:3]
    planned, _, projected = build_planned_route_stops(
        short_matches,
        origin_position_km=0.0,
        destination_distance_km=200.0,
        profile=VehicleEnergyProfile(
            soc_percent=80,
            usable_capacity_kwh=57.5,
            consumption_wh_per_km=160.0,
            terrain_factor=1.0,
            reserve_soc_percent=10,
            max_charge_power_kw=170,
            min_destination_soc_pct=10,
            min_stop_arrival_soc_pct=10,
            max_charge_soc_pct=80,
        ),
        route_distance_km=200.0,
        route_duration_minutes=150.0,
        route_preference="fastest",
    )
    assert len(planned) <= 1
    assert projected is not None and projected >= 10.0

    # Comfort: 1.ª con llegada ≥20 % si existe.
    planned, _, _ = run(61.0, "fastest", 375.0)
    assert planned
    assert planned[0].soc_arrival_pct >= 20.0 or planned[0].distance_from_origin_km < 160.0
