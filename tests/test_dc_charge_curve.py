from __future__ import annotations

from api.routing.charging_plan import estimate_charge_minutes
from api.routing.dc_charge_curve import (
    estimate_dc_charge_minutes,
    estimate_linear_charge_minutes,
    resolve_dc_profile,
)


def test_resolve_dc_profile_by_preset_id() -> None:
    profile = resolve_dc_profile("tesla-model3-sr-2023", 57.0)
    assert profile.id == "tesla-model3-sr-2023"
    assert profile.peak_dc_kw == 170.0


def test_resolve_dc_profile_by_capacity() -> None:
    profile = resolve_dc_profile(None, 75.0)
    assert profile.id == "tesla-model-y-lr"


def test_dc_curve_slower_than_linear_at_high_soc_window() -> None:
    """80→90 % tarda más que extrapolar potencia constante del tramo bajo."""
    linear_low = estimate_linear_charge_minutes(
        20.0,
        30.0,
        usable_capacity_kwh=57.0,
        max_power_kw=150.0,
    )
    curve_high = estimate_dc_charge_minutes(
        80.0,
        90.0,
        usable_capacity_kwh=57.0,
        station_max_kw=150.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    linear_high = estimate_linear_charge_minutes(
        80.0,
        90.0,
        usable_capacity_kwh=57.0,
        max_power_kw=150.0,
    )
    assert curve_high > linear_high * 1.5
    assert linear_low > 0


def test_model3_mid_soc_charge_realistic_at_150kw() -> None:
    """18→72 % en HPC 150 kW: curva DC más lenta que lineal optimista (~17 min)."""
    minutes = estimate_charge_minutes(
        18.0,
        72.0,
        usable_capacity_kwh=57.0,
        max_power_kw=150.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    linear = estimate_linear_charge_minutes(
        18.0,
        72.0,
        usable_capacity_kwh=57.0,
        max_power_kw=150.0,
    )
    assert 22 <= minutes <= 38
    assert minutes > linear


def test_slow_station_caps_charge_time() -> None:
    fast = estimate_dc_charge_minutes(
        25.0,
        65.0,
        usable_capacity_kwh=57.0,
        station_max_kw=250.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    slow = estimate_dc_charge_minutes(
        25.0,
        65.0,
        usable_capacity_kwh=57.0,
        station_max_kw=50.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    assert slow > fast


def test_no_charge_when_departure_not_above_arrival() -> None:
    assert (
        estimate_dc_charge_minutes(
            60.0,
            60.0,
            usable_capacity_kwh=57.0,
            station_max_kw=150.0,
            vehicle_preset_id="tesla-model3-sr-2023",
        )
        == 0.0
    )


def test_reve_style_mid_soc_charge_at_200kw() -> None:
    """46→73 % @200 kW (parada REVE típica): orden de magnitud ~5–10 min."""
    minutes = estimate_dc_charge_minutes(
        46.0,
        73.0,
        usable_capacity_kwh=50.0,
        station_max_kw=200.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    assert 4.0 <= minutes <= 12.0


def test_leaf_slower_than_model3_same_station() -> None:
    leaf = estimate_dc_charge_minutes(
        20.0,
        70.0,
        usable_capacity_kwh=59.0,
        station_max_kw=150.0,
        vehicle_preset_id="nissan-leaf-62",
    )
    model3 = estimate_dc_charge_minutes(
        20.0,
        70.0,
        usable_capacity_kwh=57.0,
        station_max_kw=150.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    assert leaf > model3
