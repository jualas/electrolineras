from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from osrm_mocks import MOCK_OSRM, MOCK_ROUTE

from api.config import settings
from api.dependencies import get_repository
from api.main import app
from db.repository import StationRepository
from models.station import Connector, Station, StationLocation


def memory_repo() -> StationRepository:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return StationRepository(connection)


def sample_station(station_id: str, lat: float, lon: float, kw: float = 150.0, price: float | None = None) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="ccs", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=station_id,
        dynamic_price_eur_kwh=price,
        dynamic_status="available",
    )


VEHICLE_PARAMS = {
    "soc_percent": 45,
    "usable_capacity_kwh": 57,
    "consumption_wh_per_km": 150,
    "terrain_factor": 1.0,
    "reserve_soc_percent": 10,
}


@pytest.fixture
def api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("ahead-safe", 40.01, 0.25, 350.0, 0.42),
            sample_station("ahead-far", 40.01, 0.75, 350.0, 0.38),
            sample_station("behind", 40.01, -0.2, 350.0),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_charging_plan_route_mode(mock_fetch, api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.1,
            "dest_lat": 40.0,
            "dest_lon": 1.0,
            "min_kw": 100,
            "corridor_km": 20,
            **VEHICLE_PARAMS,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "route"
    assert payload["range_km"] > 0
    assert payload["charging_reach_km"] >= payload["range_km"]
    assert payload["stops"]
    assert len(payload["strategies"]) >= 3
    assert "origin_stops" in payload
    assert isinstance(payload["origin_stops"], list)
    assert payload["stops"][0]["classification"] in {"safe", "adjusted", "critical", "unreachable"}
    assert payload["route_geometry"]["type"] == "LineString"
    assert payload["route_shortest_geometry"]["type"] == "LineString"
    assert payload["route_fastest_geometry"]["type"] == "LineString"
    assert payload["route_shortest_distance_km"] == 111.32
    assert payload["route_fastest_distance_km"] == 115.0
    assert payload["destination_stay"] is not None
    assert payload["destination_stay"]["bands"]["total"] >= 0
    assert payload["route_trip_summary"] is not None
    assert payload["route_trip_summary"]["total_energy_kwh"] > 0
    assert payload["route_variant_plans"] is not None
    assert set(payload["route_variant_plans"]) >= {"shortest", "fastest", "conventional"}
    assert payload["route_variant_plans"]["fastest"]["planned_stops"] is not None


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_charging_plan_requires_auth_when_private_stack_enabled(mock_fetch, api_client: TestClient) -> None:
    params = {
        "origin_lat": 40.0,
        "origin_lon": 0.1,
        "dest_lat": 40.0,
        "dest_lon": 1.0,
        "min_kw": 100,
        "corridor_km": 20,
        **VEHICLE_PARAMS,
    }
    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    try:
        blocked = api_client.get("/api/v1/stations/charging-plan", params=params)
        assert blocked.status_code == 401

        allowed = api_client.get(
            "/api/v1/stations/charging-plan",
            params=params,
            headers={"Authorization": "Bearer test-private-token-min-32-chars-long"},
        )
        assert allowed.status_code == 200
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_charging_plan_route_destination_slow_infra(mock_fetch, api_client: TestClient) -> None:
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

    response = client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.1,
            "dest_lat": 40.0,
            "dest_lon": 1.0,
            "min_kw": 100,
            "corridor_km": 20,
            **VEHICLE_PARAMS,
        },
    )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    stay = response.json()["destination_stay"]
    assert stay["infrastructure_level"] in {"ac_slow", "ac_fast"}
    assert stay["recommended_soc_at_arrival_pct"] >= 40
    assert stay["bands"]["ac_slow"] >= 1


@patch("api.charging_plan_service.fetch_osrm_route", return_value=MOCK_ROUTE)
def test_charging_plan_emergency_mode(mock_fetch, api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.0,
            "min_kw": 100,
            **VEHICLE_PARAMS,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "emergency"
    assert payload["destination"] is None
    assert any(stop["station"]["id"] == "ahead-safe" for stop in payload["stops"])
    assert payload["preview_route_geometry"]["type"] == "LineString"
    mock_fetch.assert_called_once()


def test_charging_plan_rejects_partial_destination(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.0,
            "dest_lat": 40.0,
            **VEHICLE_PARAMS,
        },
    )
    assert response.status_code == 422
