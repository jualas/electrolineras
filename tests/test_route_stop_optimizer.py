from __future__ import annotations

from api.routing.charging_plan import VehicleEnergyProfile, build_planned_route_stops
from api.routing.corridor import CorridorMatch
from test_charging_plan import sample_station


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
    positions = [200.0, 400.0, 580.0, 720.0]
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
