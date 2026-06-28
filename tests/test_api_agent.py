from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.dependencies import get_repository
from api.main import app
from test_api_charging_plan import MOCK_ROUTE, VEHICLE_PARAMS, memory_repo, sample_station


@pytest.fixture
def agent_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("ahead-safe", 40.01, 0.25, 350.0, 0.42),
            sample_station("dest-slow", 40.0, 1.01, 11.0),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("api.charging_plan_service.fetch_osrm_route", return_value=MOCK_ROUTE)
def test_agent_trip_advice(mock_fetch, agent_client: TestClient) -> None:
    original = settings.charging_agent_enabled
    settings.charging_agent_enabled = True
    try:
        response = agent_client.get(
            "/api/v1/agent/trip-advice",
            params={
                "origin_lat": 40.0,
                "origin_lon": 0.1,
                "dest_lat": 40.0,
                "dest_lon": 1.0,
                **VEHICLE_PARAMS,
            },
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["agent_summary"]
        assert payload["agent_bullets"]
        assert payload["plan"]["destination_stay"]["bands"]["ac_slow"] >= 1
    finally:
        settings.charging_agent_enabled = original


def test_agent_trip_advice_disabled(agent_client: TestClient) -> None:
    original = settings.charging_agent_enabled
    settings.charging_agent_enabled = False
    try:
        response = agent_client.get(
            "/api/v1/agent/trip-advice",
            params={
                "origin_lat": 40.0,
                "origin_lon": 0.1,
                "dest_lat": 40.0,
                "dest_lon": 1.0,
                **VEHICLE_PARAMS,
            },
        )
        assert response.status_code == 503
    finally:
        settings.charging_agent_enabled = original
