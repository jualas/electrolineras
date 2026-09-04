from __future__ import annotations

import pytest

from api.config import settings
from api.integrations.telemetry_energy import (
    MODEL_3_SR_USABLE_KWH,
    charging_reach_km,
    current_range_from_nominal,
    nominal_range_km,
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


def test_nominal_range_normalizes_to_100_pct_soc() -> None:
    # TeslaMate publica rated_battery_range_km al SOC actual (75 %), no al 100 %.
    telemetry = _telemetry()
    assert round(nominal_range_km(telemetry), 2) == round(305.12 * 100 / 75, 2)


def test_current_range_from_nominal() -> None:
    # Al normalizar y volver a escalar por el mismo SOC, coincide con el valor crudo de TeslaMate.
    telemetry = _telemetry()
    assert round(current_range_from_nominal(telemetry), 1) == round(305.12, 1)


def test_planning_range_from_nominal() -> None:
    assert planning_range_km(305.12, 75.0, 10.0) == 305.12 * 65 / 100


def test_vehicle_energy_ignores_est_uses_nominal(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "teslamate_efficiency_kwh_per_km", None)
    monkeypatch.setattr(settings, "teslamate_usable_capacity_kwh", None)
    telemetry = _telemetry(est_battery_range_km=483.0, rated_battery_range_km=305.12)
    soc, capacity, consumption, reserve = vehicle_energy_from_telemetry(
        telemetry,
        terrain_factor=1.0,
        vehicle_preset_id="tesla-model3-sr-2023",
    )
    assert soc == 75.0
    assert capacity == 57.5
    assert reserve == 10.0
    # Sin efficiency: consumo = capacidad / rated_100
    rated_100 = nominal_range_km(telemetry)
    assert rated_100 is not None
    assert round(consumption, 2) == round(capacity * 1000.0 / rated_100, 2)


def test_vehicle_energy_prefers_teslamate_efficiency() -> None:
    telemetry = _telemetry(
        rated_battery_range_km=251.5,
        battery_level_pct=62.0,
        usable_battery_level_pct=61.0,
        efficiency_kwh_per_km=0.13733,
        model="3",
        trim_badging="50",
    )
    soc, capacity, consumption, reserve = vehicle_energy_from_telemetry(
        telemetry,
        terrain_factor=1.0,
    )
    assert soc == 62.0
    assert capacity == MODEL_3_SR_USABLE_KWH
    assert round(consumption, 1) == 137.3
    assert reserve == 10.0


def test_vehicle_energy_sr_trim_capacity_not_badging_50() -> None:
    telemetry = _telemetry(model="3", trim_badging="50", rated_battery_range_km=250.0)
    _, capacity, _, _ = vehicle_energy_from_telemetry(telemetry)
    assert capacity == 57.5


def test_vehicle_energy_requires_rated() -> None:
    telemetry = _telemetry(rated_battery_range_km=None, est_battery_range_km=483.0)
    with pytest.raises(TeslaMateError):
        vehicle_energy_from_telemetry(telemetry)


def test_charging_reach_from_nominal() -> None:
    assert charging_reach_km(305.0, 75.0, 5.0) == 305.0 * 70 / 100


def test_settings_efficiency_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "teslamate_efficiency_kwh_per_km", 0.14)
    monkeypatch.setattr(settings, "teslamate_usable_capacity_kwh", 57.5)
    telemetry = _telemetry(rated_battery_range_km=250.0, model="3", trim_badging="50")
    _, capacity, consumption, _ = vehicle_energy_from_telemetry(telemetry)
    assert capacity == 57.5
    assert round(consumption, 1) == 140.0
