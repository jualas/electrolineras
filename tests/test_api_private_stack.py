from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from test_api_charging_plan import (
    MOCK_OSRM,
    memory_repo,
    sample_station,
)

from api.config import settings
from api.dependencies import get_repository
from api.main import app


@pytest.fixture
def private_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations([sample_station("dest-slow", 40.0, 1.01, 11.0)])

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_private_stack_requires_token_when_enabled(private_client: TestClient) -> None:
    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    try:
        response = private_client.get("/api/v1/private/status")
        assert response.status_code == 401
        ok = private_client.get(
            "/api/v1/private/status",
            headers={"Authorization": "Bearer test-private-token-min-32-chars-long"},
        )
        assert ok.status_code == 200
        assert ok.json()["private_stack_enabled"] is True
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token


@patch("api.routes.private_stack.fetch_consumption_profile")
def test_private_consumption_profile(mock_profile, private_client: TestClient) -> None:
    from api.integrations.consumption_profile_service import (
        ConsumptionBinStats,
        ConsumptionProfile,
    )

    mock_profile.return_value = ConsumptionProfile(
        bins={
            "highway": ConsumptionBinStats(
                bin="highway",
                wh_per_km=134.5,
                kwh_per_100km=13.45,
                sample_count=24,
                total_distance_km=3200.0,
            ),
            "mixed": ConsumptionBinStats(
                bin="mixed",
                wh_per_km=140.0,
                kwh_per_100km=14.0,
                sample_count=10,
                total_distance_km=900.0,
            ),
            "conventional": ConsumptionBinStats(
                bin="conventional",
                wh_per_km=130.0,
                kwh_per_100km=13.0,
                sample_count=8,
                total_distance_km=500.0,
            ),
            "mountain": ConsumptionBinStats(
                bin="mountain",
                wh_per_km=None,
                kwh_per_100km=None,
                sample_count=0,
                total_distance_km=0.0,
            ),
        },
        lookback_days=0,
        car_id=1,
        source="historical",
        available=True,
        note="test",
    )

    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    try:
        response = private_client.get(
            "/api/v1/private/consumption-profile",
            headers={"X-Private-Token": "test-private-token-min-32-chars-long"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["available"] is True
        assert payload["bins"]["highway"]["kwh_per_100km"] == 13.45
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token


@patch("api.routes.private_stack.fetch_vehicle_telemetry")
def test_private_vehicle_state(mock_fetch, private_client: TestClient) -> None:
    from api.integrations.teslamate import VehicleTelemetry

    mock_fetch.return_value = VehicleTelemetry(
        car_id=1,
        display_name="Test",
        state="online",
        lat=40.0,
        lon=0.1,
        battery_level_pct=55,
        usable_battery_level_pct=53,
        est_battery_range_km=300,
        rated_battery_range_km=400,
        charging_state=None,
        inside_temp_c=None,
        outside_temp_c=None,
        odometer_km=None,
    )

    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    original_tm_url = settings.teslamate_api_base_url
    original_tm_token = settings.teslamate_api_token
    original_mqtt_host = settings.teslamate_mqtt_host
    original_mqtt_user = settings.teslamate_mqtt_username
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    settings.teslamate_mqtt_host = "<IP-LAN-SERVIDOR>"
    settings.teslamate_mqtt_username = "jualas"
    try:
        response = private_client.get(
            "/api/v1/private/vehicle/state",
            headers={"X-Private-Token": "test-private-token-min-32-chars-long"},
        )
        assert response.status_code == 200
        assert response.json()["battery_level_pct"] == 55
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token
        settings.teslamate_api_base_url = original_tm_url
        settings.teslamate_api_token = original_tm_token
        settings.teslamate_mqtt_host = original_mqtt_host
        settings.teslamate_mqtt_username = original_mqtt_user


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
@patch("api.routes.private_stack.fetch_vehicle_telemetry")
def test_private_trip_advice_from_car(mock_fetch, mock_osrm, private_client: TestClient) -> None:
    from api.integrations.teslamate import VehicleTelemetry

    mock_fetch.return_value = VehicleTelemetry(
        car_id=1,
        display_name="Test",
        state="online",
        lat=40.0,
        lon=0.1,
        battery_level_pct=45,
        usable_battery_level_pct=43,
        est_battery_range_km=250,
        rated_battery_range_km=333,
        charging_state=None,
        inside_temp_c=None,
        outside_temp_c=None,
        odometer_km=None,
    )

    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    original_tm_url = settings.teslamate_api_base_url
    original_tm_token = settings.teslamate_api_token
    original_mqtt_host = settings.teslamate_mqtt_host
    original_mqtt_user = settings.teslamate_mqtt_username
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    settings.teslamate_mqtt_host = "<IP-LAN-SERVIDOR>"
    settings.teslamate_mqtt_username = "jualas"
    try:
        response = private_client.get(
            "/api/v1/private/trip-advice-from-car",
            params={"dest_lat": 40.0, "dest_lon": 1.0},
            headers={"X-Private-Token": "test-private-token-min-32-chars-long"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["vehicle"]["battery_level_pct"] == 45
        assert payload["plan"]["destination_stay"] is not None
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token
        settings.teslamate_api_base_url = original_tm_url
        settings.teslamate_api_token = original_tm_token
        settings.teslamate_mqtt_host = original_mqtt_host
        settings.teslamate_mqtt_username = original_mqtt_user


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
@patch("api.routes.private_stack.fetch_vehicle_telemetry")
def test_private_trip_advice_departure_soc_simulation(
    mock_fetch, mock_osrm, private_client: TestClient
) -> None:
    from api.integrations.teslamate import VehicleTelemetry

    mock_fetch.return_value = VehicleTelemetry(
        car_id=1,
        display_name="Test",
        state="online",
        lat=40.0,
        lon=0.1,
        battery_level_pct=45,
        usable_battery_level_pct=43,
        est_battery_range_km=250,
        rated_battery_range_km=333,
        charging_state=None,
        inside_temp_c=None,
        outside_temp_c=None,
        odometer_km=None,
    )

    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    original_mqtt_host = settings.teslamate_mqtt_host
    original_mqtt_user = settings.teslamate_mqtt_username
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    settings.teslamate_mqtt_host = "<IP-LAN-SERVIDOR>"
    settings.teslamate_mqtt_username = "jualas"
    try:
        response = private_client.get(
            "/api/v1/private/trip-advice-from-car",
            params={"dest_lat": 40.0, "dest_lon": 1.0, "departure_soc_percent": 90},
            headers={"X-Private-Token": "test-private-token-min-32-chars-long"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["live_soc_percent"] == 45
        assert payload["departure_soc_percent"] == 90
        assert any("Simulación al salir" in bullet for bullet in payload["agent_bullets"])
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token
        settings.teslamate_mqtt_host = original_mqtt_host
        settings.teslamate_mqtt_username = original_mqtt_user


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
@patch("api.routes.private_stack.fetch_vehicle_telemetry")
def test_private_trip_guide_from_car(mock_fetch, mock_osrm, private_client: TestClient) -> None:
    from api.integrations.teslamate import VehicleTelemetry

    mock_fetch.return_value = VehicleTelemetry(
        car_id=1,
        display_name="Test",
        state="online",
        lat=40.0,
        lon=0.1,
        battery_level_pct=45,
        usable_battery_level_pct=43,
        est_battery_range_km=250,
        rated_battery_range_km=333,
        charging_state=None,
        inside_temp_c=None,
        outside_temp_c=None,
        odometer_km=None,
    )

    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    original_mqtt_host = settings.teslamate_mqtt_host
    original_mqtt_user = settings.teslamate_mqtt_username
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    settings.teslamate_mqtt_host = "<IP-LAN-SERVIDOR>"
    settings.teslamate_mqtt_username = "jualas"
    try:
        response = private_client.get(
            "/api/v1/private/trip-guide-from-car",
            params={
                "dest_lat": 40.0,
                "dest_lon": 1.0,
                "dest_label": "Test dest",
                "invoke_dify": "false",
                "cultural_poi": "false",
            },
            headers={"X-Private-Token": "test-private-token-min-32-chars-long"},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["guide_source"] == "deterministic"
        assert payload["guide_text"]
        assert payload["context"]["destination_label"] == "Test dest"
        assert payload["plan"]["destination_stay"] is not None
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token
        settings.teslamate_mqtt_host = original_mqtt_host
        settings.teslamate_mqtt_username = original_mqtt_user
