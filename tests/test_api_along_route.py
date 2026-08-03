from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from osrm_mocks import MOCK_OSRM

from api.dependencies import get_repository
from api.main import app
from db.repository import StationRepository
from models.station import Connector, Station, StationLocation


def memory_repo() -> StationRepository:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return StationRepository(connection)


def sample_station(station_id: str, lat: float, lon: float, kw: float = 150.0) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="ccs", power_kw=kw)],
        max_power_kw=kw,
        raw_ref=station_id,
    )


@pytest.fixture
def api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("ahead", 40.01, 0.6, 350.0),
            sample_station("behind", 40.01, -0.2, 350.0),
            sample_station("low-kw", 40.01, 0.55, 22.0),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("api.routes.along_route.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_along_route_returns_ranked_results(mock_fetch, api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/along-route",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.1,
            "dest_lat": 40.0,
            "dest_lon": 1.0,
            "min_kw": 100,
            "corridor_km": 20,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["route_distance_km"] > 0
    assert payload["route_shortest_distance_km"] == 111.32
    assert payload["route_fastest_distance_km"] == 115.0
    assert payload["route_geometry"]["type"] == "LineString"
    assert payload["route_shortest_geometry"]["type"] == "LineString"
    assert payload["route_fastest_geometry"]["type"] == "LineString"
    assert len(payload["results"]) == 1
    assert payload["results"][0]["station"]["id"] == "ahead"
    assert payload["results"][0]["deviation_km"] >= 0
    assert payload["route_variant_results"] is not None
    assert set(payload["route_variant_results"]) >= {"shortest", "fastest", "conventional"}
    mock_fetch.assert_called_once()


@patch("api.routes.along_route.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_along_route_excludes_low_kw(mock_fetch, api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/along-route",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.0,
            "dest_lat": 40.0,
            "dest_lon": 1.0,
            "min_kw": 100,
        },
    )
    ids = [item["station"]["id"] for item in response.json()["results"]]
    assert "low-kw" not in ids


@patch("api.routes.along_route.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_along_route_without_geometry(mock_fetch, api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/along-route",
        params={
            "origin_lat": 40.0,
            "origin_lon": 0.0,
            "dest_lat": 40.0,
            "dest_lon": 1.0,
            "include_route": False,
        },
    )
    assert response.json()["route_geometry"] is None
