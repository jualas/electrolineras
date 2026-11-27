from __future__ import annotations

from fastapi.testclient import TestClient

from api.config import settings
from api.integrations.push_telemetry import (
    clear_push_telemetry,
    get_push_telemetry,
    store_push_telemetry,
)
from api.integrations.telemetry_energy import nominal_range_km, vehicle_energy_from_telemetry
from api.integrations.teslamate import VehicleTelemetry
from api.integrations.vehicle_telemetry import fetch_vehicle_telemetry, vehicle_telemetry_configured
from api.main import app


def test_push_telemetry_store_and_ttl_expiry() -> None:
    clear_push_telemetry()
    sample = VehicleTelemetry(
        car_id=2,
        display_name="Renault Scenic E-Tech",
        state="driving",
        lat=37.18,
        lon=-3.60,
        battery_level_pct=62.0,
        usable_battery_level_pct=62.0,
        est_battery_range_km=248.0,
        car_model_label="Renault Scenic E-Tech",
        source="android_car",
    )
    store_push_telemetry(sample, ttl_seconds=60.0)
    assert vehicle_telemetry_configured() is True
    fetched = fetch_vehicle_telemetry(car_id=2)
    assert fetched.source == "android_car"
    assert fetched.battery_level_pct == 62.0

    # Sin car_id explícito devuelve el último vehículo reportado
    assert get_push_telemetry() is not None
    clear_push_telemetry()
    assert get_push_telemetry() is None


def test_android_car_telemetry_energy_uses_estimated_range_without_tesla_rated() -> None:
    telemetry = VehicleTelemetry(
        car_id=1,
        display_name="Coche AAOS",
        state="driving",
        lat=37.18,
        lon=-3.60,
        battery_level_pct=50.0,
        usable_battery_level_pct=50.0,
        est_battery_range_km=200.0,
        rated_battery_range_km=None,
        efficiency_kwh_per_km=None,
        source="android_car",
    )
    # 200 km al 50 % -> 400 km nominales al 100 %
    assert nominal_range_km(telemetry) == 400.0
    soc, cap_kwh, wh_per_km, reserve = vehicle_energy_from_telemetry(
        telemetry,
        usable_capacity_kwh=64.0,
    )
    assert soc == 50.0
    assert cap_kwh == 64.0
    assert wh_per_km > 0
    assert reserve == 10.0


def test_private_telemetry_ingest_endpoint_and_readback() -> None:
    clear_push_telemetry()
    orig_enabled = settings.private_stack_enabled
    orig_token = settings.private_api_token
    orig_provider = settings.vehicle_telemetry_provider
    try:
        settings.private_stack_enabled = True
        settings.private_api_token = "test-push-token"
        settings.vehicle_telemetry_provider = "auto"

        client = TestClient(app)
        headers = {"X-Private-Token": "test-push-token"}

        resp = client.post(
            "/api/v1/private/telemetry/ingest",
            headers=headers,
            json={
                "lat": 37.25,
                "lon": -3.12,
                "battery_level_pct": 48.0,
                "est_battery_range_km": 195.0,
                "display_name": "Polestar AAOS",
                "car_model_label": "Polestar 2 LR",
                "charging_state": "Disconnected",
                "source": "android_car",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["source"] == "android_car"
        assert body["battery_level_pct"] == 48.0
        assert body["est_battery_range_km"] == 195.0

        state_resp = client.get("/api/v1/private/vehicle/state", headers=headers)
        assert state_resp.status_code == 200
        state_body = state_resp.json()
        assert state_body["source"] == "android_car"
        assert state_body["display_name"] == "Polestar AAOS"

        status_resp = client.get("/api/v1/private/status", headers=headers)
        assert status_resp.status_code == 200
        assert status_resp.json()["push_telemetry_active"] is True
    finally:
        clear_push_telemetry()
        settings.private_stack_enabled = orig_enabled
        settings.private_api_token = orig_token
        settings.vehicle_telemetry_provider = orig_provider
