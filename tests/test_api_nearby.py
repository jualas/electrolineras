from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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


def sample_station(
    station_id: str,
    lat: float,
    lon: float,
    kw: float = 22.0,
    site_name: str | None = None,
    access: str | None = "public",
    payment_methods: list[str] | None = None,
) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        site_name=site_name,
        location=StationLocation(lat=lat, lon=lon),
        connectors=[Connector(connector_type="iec62196T2", power_kw=kw)],
        max_power_kw=kw,
        access=access,
        payment_methods=payment_methods or ["card"],
        raw_ref=station_id,
    )


@pytest.fixture
def api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("near", 40.4169, -3.7038, site_name="Calle Test"),
            sample_station("far", 40.45, -3.65, site_name="Lejos"),
            sample_station("cc", 40.4170, -3.7040, site_name="Centro Comercial Test"),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_nearby_by_coordinates(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/nearby",
        params={"lat": 40.4168, "lon": -3.7038, "radius_m": 500},
    )
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["results"]) >= 1
    assert payload["results"][0]["station"]["id"] == "near"
    assert payload["results"][0]["distance_m"] < 200
    assert payload["radius_m"] == 500


def test_nearby_default_radius_1km(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/nearby",
        params={"lat": 40.4168, "lon": -3.7038},
    )
    assert response.json()["radius_m"] == 1000


@patch(
    "api.routes.nearby.geocode_address",
    return_value=(40.4168, -3.7038, "Plaza Nueva, Granada"),
)
def test_nearby_by_address(mock_geocode, api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/nearby",
        params={"q": "Plaza Nueva Granada", "radius_m": 800},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["reference_label"] == "Plaza Nueva, Granada"
    assert len(payload["results"]) >= 1
    mock_geocode.assert_called_once()


def test_nearby_exclude_commercial(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/nearby",
        params={
            "lat": 40.4168,
            "lon": -3.7038,
            "radius_m": 1000,
            "exclude_commercial": True,
        },
    )
    ids = [item["station"]["id"] for item in response.json()["results"]]
    assert "cc" not in ids
    assert "near" in ids


def test_nearby_bbox_mode(api_client: TestClient) -> None:
    response = api_client.get(
        "/api/v1/stations/nearby",
        params={"bbox": "-3.75,40.40,-3.65,40.43"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["bbox"] == [-3.75, 40.4, -3.65, 40.43]
    assert payload["radius_m"] is None
    assert len(payload["results"]) >= 2


def test_nearby_requires_location(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations/nearby")
    assert response.status_code == 422


def test_nearby_requires_auth_when_private_stack_enabled(api_client: TestClient) -> None:
    original_enabled = settings.private_stack_enabled
    original_token = settings.private_api_token
    settings.private_stack_enabled = True
    settings.private_api_token = "test-private-token-min-32-chars-long"
    try:
        blocked = api_client.get(
            "/api/v1/stations/nearby",
            params={"bbox": "-3.75,40.40,-3.65,40.43"},
        )
        assert blocked.status_code == 401

        allowed = api_client.get(
            "/api/v1/stations/nearby",
            params={"bbox": "-3.75,40.40,-3.65,40.43"},
            headers={"Authorization": "Bearer test-private-token-min-32-chars-long"},
        )
        assert allowed.status_code == 200
    finally:
        settings.private_stack_enabled = original_enabled
        settings.private_api_token = original_token
