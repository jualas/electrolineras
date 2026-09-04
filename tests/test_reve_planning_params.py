from types import SimpleNamespace

from api.charging_plan_service import (
    resolve_consumption_wh_per_km,
    resolve_fallback_planning_min_kw,
    resolve_planning_min_kw,
    route_plan_needs_power_fallback,
    vehicle_profile_from_inputs as build_profile,
)
from api.routing.charging_plan import DEFAULT_DESTINATION_TARGET_SOC_PCT, VehicleEnergyProfile


def test_default_destination_soc_is_reve_10() -> None:
    assert DEFAULT_DESTINATION_TARGET_SOC_PCT == 10.0


def test_resolve_consumption_kwh_per_100km_alias() -> None:
    wh = resolve_consumption_wh_per_km(150.0, 17.0)
    assert wh == 170.0


def test_resolve_planning_min_kw_exclude_slow() -> None:
    assert resolve_planning_min_kw(100.0, exclude_slow_chargers=True) == 100.0
    assert resolve_planning_min_kw(22.0, exclude_slow_chargers=True) == 100.0
    assert resolve_planning_min_kw(None, exclude_slow_chargers=True) == 100.0
    assert resolve_planning_min_kw(150.0, exclude_slow_chargers=True) == 150.0
    assert resolve_planning_min_kw(22.0, exclude_slow_chargers=False) == 22.0


def test_resolve_fallback_planning_min_kw() -> None:
    assert resolve_fallback_planning_min_kw(None, preferred_min_kw=100.0) == 50.0
    assert resolve_fallback_planning_min_kw(100.0, preferred_min_kw=100.0) == 50.0
    assert resolve_fallback_planning_min_kw(150.0, preferred_min_kw=150.0) is None
    assert resolve_fallback_planning_min_kw(22.0, preferred_min_kw=22.0) is None
    assert resolve_fallback_planning_min_kw(50.0, preferred_min_kw=50.0) is None


def test_route_plan_needs_power_fallback() -> None:
    vehicle = build_profile(55.0, 57.5, 160.0, 1.0, 10.0)
    assert not route_plan_needs_power_fallback(
        SimpleNamespace(
            reachable_without_stop=True,
            projected_soc_at_destination_with_plan=None,
        ),
        vehicle,
    )
    assert route_plan_needs_power_fallback(
        SimpleNamespace(
            reachable_without_stop=False,
            projected_soc_at_destination_with_plan=None,
        ),
        vehicle,
    )
    assert route_plan_needs_power_fallback(
        SimpleNamespace(
            reachable_without_stop=False,
            projected_soc_at_destination_with_plan=5.0,
        ),
        vehicle,
    )
    assert not route_plan_needs_power_fallback(
        SimpleNamespace(
            reachable_without_stop=False,
            projected_soc_at_destination_with_plan=12.0,
        ),
        vehicle,
    )


def test_vehicle_profile_reve_defaults() -> None:
    profile = build_profile(
        100.0,
        60.0,
        170.0,
        1.0,
        10.0,
    )
    assert profile.min_destination_soc_pct == 10.0
    assert profile.min_stop_arrival_soc_pct == 10.0
    assert profile.max_charge_soc_pct == 80.0
    assert profile.max_charge_power_kw == 100.0


def test_vehicle_profile_custom_reve_params() -> None:
    profile = build_profile(
        100.0,
        60.0,
        170.0,
        1.0,
        10.0,
        max_charge_power_kw=150.0,
        min_destination_soc_pct=15.0,
        min_stop_arrival_soc_pct=12.0,
        max_charge_soc_pct=90.0,
    )
    assert profile.max_charge_power_kw == 150.0
    assert profile.min_destination_soc_pct == 15.0
    cloned = VehicleEnergyProfile(
        soc_percent=50.0,
        usable_capacity_kwh=profile.usable_capacity_kwh,
        consumption_wh_per_km=profile.consumption_wh_per_km,
        terrain_factor=profile.terrain_factor,
        reserve_soc_percent=profile.reserve_soc_percent,
        vehicle_preset_id=profile.vehicle_preset_id,
        max_charge_power_kw=profile.max_charge_power_kw,
        min_destination_soc_pct=profile.min_destination_soc_pct,
        min_stop_arrival_soc_pct=profile.min_stop_arrival_soc_pct,
        max_charge_soc_pct=profile.max_charge_soc_pct,
    )
    assert cloned.min_destination_soc_pct == 15.0
