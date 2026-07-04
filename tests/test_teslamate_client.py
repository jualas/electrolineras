from __future__ import annotations

from api.integrations.teslamate import _parse_status


def test_parse_teslamate_status_flat() -> None:
    payload = {
        "data": {
            "battery_level": 62,
            "usable_battery_level": 60,
            "latitude": 37.18,
            "longitude": -3.60,
            "state": "online",
            "display_name": "Model 3",
            "est_battery_range_km": 280,
        }
    }
    telemetry = _parse_status(1, payload)
    assert telemetry.battery_level_pct == 62
    assert telemetry.lat == 37.18
    assert telemetry.lon == -3.60
    assert telemetry.display_name == "Model 3"


def test_parse_teslamate_status_nested_location() -> None:
    payload = {
        "data": {
            "battery_level": 45,
            "location": {"latitude": 40.0, "longitude": 1.0},
        }
    }
    telemetry = _parse_status(2, payload)
    assert telemetry.lat == 40.0
    assert telemetry.lon == 1.0
