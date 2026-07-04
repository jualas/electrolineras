from __future__ import annotations

from api.integrations.teslamate_mqtt import _build_telemetry


def test_build_telemetry_from_mqtt_topics() -> None:
    prefix = "teslamate/cars/1/"
    values = {
        f"{prefix}battery_level": "62",
        f"{prefix}usable_battery_level": "60",
        f"{prefix}state": "online",
        f"{prefix}location": '{"latitude": 37.18, "longitude": -3.60}',
        f"{prefix}est_battery_range_km": "280",
        f"{prefix}rated_battery_range_km": "305",
        f"{prefix}model": "3",
        f"{prefix}trim_badging": "SR+",
        f"{prefix}version": "2026.20",
        f"{prefix}charging_state": "Complete",
    }
    telemetry = _build_telemetry(1, values)
    assert telemetry.battery_level_pct == 62
    assert telemetry.lat == 37.18
    assert telemetry.lon == -3.60
    assert telemetry.rated_battery_range_km == 305.0
    assert telemetry.car_model_label == "Model 3 SR+"
    assert telemetry.version == "2026.20"
    assert telemetry.source == "teslamate-mqtt"


def test_build_telemetry_from_lat_lon_topics() -> None:
    prefix = "teslamate/cars/1/"
    values = {
        f"{prefix}battery_level": "45",
        f"{prefix}latitude": "40.0",
        f"{prefix}longitude": "1.0",
    }
    telemetry = _build_telemetry(1, values)
    assert telemetry.lat == 40.0
    assert telemetry.lon == 1.0
