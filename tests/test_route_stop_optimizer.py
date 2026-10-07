from __future__ import annotations

from test_charging_plan import sample_station

from api.routing.charging_plan import (
    HIGH_ARRIVAL_MICRO_STOP_SOC_PCT,
    VehicleEnergyProfile,
    _is_worth_charging_stop,
    build_planned_route_stops,
)
from api.routing.corridor import CorridorMatch


def test_optimizer_prefers_more_short_stops_over_few_long_ones() -> None:
    """El optimizador global debe poder elegir 4 paradas cortas si reducen tiempo total."""
    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=60,
        consumption_wh_per_km=170,
        vehicle_preset_id="tesla-model3-sr-2023",
        max_charge_power_kw=100,
        min_destination_soc_pct=10,
        min_stop_arrival_soc_pct=10,
        max_charge_soc_pct=80,
    )
    positions = [250.0, 450.0, 620.0, 750.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"s{idx}", 40.0, 0.1 * idx, kw=200.0),
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
        destination_distance_km=812.0,
        profile=profile,
        route_distance_km=812.0,
        route_duration_minutes=560.0,
    )
    assert len(planned) >= 3
    kms = [s.distance_from_origin_km for s in planned]
    assert all(kms[i] < kms[i + 1] for i in range(len(kms) - 1))
    assert any("Plan optimizado" in w for w in warnings)
    assert projected is not None
    assert projected >= 10.0
    total_charge = sum(s.charge_minutes for s in planned)
    assert total_charge < 150


def test_optimizer_skips_high_soc_micro_stop() -> None:
    """#6098: no parar en km ~200 con 53 % y carga de 5 min si hay opción más adelante."""
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
    # Ventana válida tras 1.ª parada (~250): min progress ~0.85 y alcance SOC; 320 quedaba fuera por mínimo
    positions = [250.0, 440.0, 620.0, 780.0]
    matches = [
        CorridorMatch(
            station=sample_station(f"s{idx}", 38.0 + idx * 0.01, -1.5 + idx * 0.1, kw=300.0),
            deviation_m=200,
            route_position_m=int(km * 1000),
            extra_minutes=2.0,
            behind_route=False,
            wrong_side=False,
        )
        for idx, km in enumerate(positions, start=1)
    ]
    planned, _warnings, projected = build_planned_route_stops(
        matches,
        origin_position_km=0.0,
        destination_distance_km=868.0,
        profile=profile,
        route_distance_km=868.0,
        route_duration_minutes=578.0,
    )
    assert projected is not None
    assert projected >= 10.0
    assert planned
    kms = [s.distance_from_origin_km for s in planned]
    assert kms[0] >= 220.0, f"first stop too early: {kms}"
    for stop in planned:
        assert not (
            stop.soc_arrival_pct > HIGH_ARRIVAL_MICRO_STOP_SOC_PCT
            and stop.charge_minutes < 12
            and stop.soc_departure_pct - stop.soc_arrival_pct < 10
        ), stop


def test_is_worth_charging_stop_rejects_albacete_pattern() -> None:
    # Micro-parada: tramo corto + poca carga con llegada alta.
    assert not _is_worth_charging_stop(
        arrival_soc_pct=52.8,
        departure_soc_pct=57.8,
        charge_minutes=5.0,
        leg_distance_km=100.0,
        min_leg_km=200.0,
        stop_route_km=100.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=180.0,
        trip_start_soc_pct=100.0,
        avg_speed_kmh=90.0,
    )
    assert not _is_worth_charging_stop(
        arrival_soc_pct=44.6,
        departure_soc_pct=56.0,
        charge_minutes=7.0,
        leg_distance_km=110.0,
        min_leg_km=200.0,
        stop_route_km=110.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=180.0,
        trip_start_soc_pct=100.0,
        avg_speed_kmh=90.0,
    )
    assert _is_worth_charging_stop(
        arrival_soc_pct=22.0,
        departure_soc_pct=56.0,
        charge_minutes=15.0,
        leg_distance_km=280.0,
        min_leg_km=120.0,
        stop_route_km=280.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=180.0,
        trip_start_soc_pct=100.0,
        avg_speed_kmh=90.0,
    )
    # #6154: tramo ~2 h NO valida micro-carga (+5–7 % SOC / ~5–8 min).
    assert not _is_worth_charging_stop(
        arrival_soc_pct=55.0,
        departure_soc_pct=62.0,
        charge_minutes=8.0,
        leg_distance_km=200.0,
        min_leg_km=200.0,
        stop_route_km=200.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=180.0,
        trip_start_soc_pct=100.0,
        avg_speed_kmh=90.0,
    )
    # Llegada crítica: sí permitir ganancia pequeña para no quedarse tirado.
    assert _is_worth_charging_stop(
        arrival_soc_pct=12.0,
        departure_soc_pct=22.0,
        charge_minutes=8.0,
        leg_distance_km=200.0,
        min_leg_km=200.0,
        stop_route_km=200.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=180.0,
        trip_start_soc_pct=60.0,
        avg_speed_kmh=90.0,
    )
    # Tras suelo +10 % SOC, la parada intermedia sí es válida.
    assert _is_worth_charging_stop(
        arrival_soc_pct=52.0,
        departure_soc_pct=62.0,
        charge_minutes=10.0,
        leg_distance_km=200.0,
        min_leg_km=200.0,
        stop_route_km=200.0,
        trip_start_route_km=0.0,
        origin_exclusion_km=180.0,
        trip_start_soc_pct=100.0,
        avg_speed_kmh=90.0,
    )
