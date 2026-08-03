from __future__ import annotations

import pytest

from api.integrations.telemetry_energy import (
    charging_reach_km,
    consumption_divergence_pct,
    current_range_from_nominal,
    live_consumption_wh_per_km,
    planning_range_km,
    vehicle_energy_from_telemetry,
)
from api.integrations.teslamate import TeslaMateError, VehicleTelemetry, build_car_model_label


def _telemetry(**kwargs) -> VehicleTelemetry:
    defaults = {
        "car_id": 1,
        "display_name": "The Ship",
        "state": "online",
        "lat": 40.0,
        "lon": -3.0,
        "battery_level_pct": 75.0,
        "usable_battery_level_pct": 75.0,
        "est_battery_range_km": 483.0,
        "rated_battery_range_km": 305.12,
        "source": "teslamate-mqtt",
    }
    defaults.update(kwargs)
    return VehicleTelemetry(**defaults)


def test_build_car_model_label() -> None:
    assert build_car_model_label("3", "SR+") == "Model 3 SR+"


def test_current_range_from_nominal() -> None:
    telemetry = _telemetry()
    assert round(current_range_from_nominal(telemetry), 1) == round(305.12 * 0.75, 1)


def test_planning_range_from_nominal() -> None:
    assert planning_range_km(305.12, 75.0, 10.0) == 305.12 * 65 / 100


def test_vehicle_energy_ignores_est_uses_nominal() -> None:
    telemetry = _telemetry(est_battery_range_km=483.0, rated_battery_range_km=305.12)
    soc, capacity, consumption, reserve = vehicle_energy_from_telemetry(
        telemetry,
        terrain_factor=1.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    assert soc == 75.0
    assert capacity == 57.0
    assert reserve == 10.0
    range_km = capacity * (soc - reserve) / 100 / (consumption / 1000)
    assert round(range_km) == round(planning_range_km(305.12, soc, reserve))


def test_vehicle_energy_requires_rated() -> None:
    telemetry = _telemetry(rated_battery_range_km=None, est_battery_range_km=483.0)
    with pytest.raises(TeslaMateError):
        vehicle_energy_from_telemetry(telemetry)


def test_charging_reach_from_nominal() -> None:
    assert charging_reach_km(305.0, 75.0, 5.0) == 305.0 * 70 / 100


def test_live_consumption_from_est_range() -> None:
    telemetry = _telemetry(battery_level_pct=80.0, est_battery_range_km=200.0)
    # 57 kWh * 0.8 / 200 km = 0.228 kWh/km → 228 Wh/km
    live = live_consumption_wh_per_km(telemetry, capacity_kwh=57.0)
    assert live == 228.0
    assert live_consumption_wh_per_km(telemetry, capacity_kwh=57.0, soc_percent=0) is None


def test_consumption_divergence_pct_alert_threshold() -> None:
    planned = 140.0
    live_ok = 150.0  # ~7 %
    live_alert = 168.0  # +20 %
    assert consumption_divergence_pct(live_ok, planned) == pytest.approx(7.1, abs=0.1)
    assert abs(consumption_divergence_pct(live_ok, planned) or 0) < 15
    assert consumption_divergence_pct(live_alert, planned) == pytest.approx(20.0, abs=0.1)
    assert abs(consumption_divergence_pct(live_alert, planned) or 0) >= 15
