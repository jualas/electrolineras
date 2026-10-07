from __future__ import annotations

import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

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


@pytest.fixture
def live_api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("slow-near", 40.4169, -3.7038, kw=22.0, site_name="Lento cerca"),
            sample_station("hpc-near", 40.4200, -3.7000, kw=150.0, site_name="HPC cerca"),
            sample_station("hpc-far", 40.4500, -3.6500, kw=350.0, site_name="HPC lejos"),
            sample_station("mid", 40.4180, -3.7020, kw=50.0, site_name="50 kW"),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_nearest_live_prefers_nearest_hpc(live_api_client: TestClient) -> None:
    response = live_api_client.get(
        "/api/v1/stations/nearest-live",
        params={"lat": 40.4168, "lon": -3.7038, "radius_m": 50000, "min_kw": 100},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["station"]["id"] == "hpc-near"
    assert payload["used_min_kw"] == 100
    assert payload["distance_m"] is not None
    assert payload["distance_m"] < 2000


def test_nearest_live_fallback_to_50kw(live_api_client: TestClient) -> None:
    response = live_api_client.get(
        "/api/v1/stations/nearest-live",
        params={"lat": 41.0, "lon": -3.7, "radius_m": 5000, "min_kw": 100},
    )
    # Ningún ≥100 cerca de 41.0; el fixture no tiene estaciones ahí → null
    assert response.status_code == 200
    assert response.json()["station"] is None


def test_nearest_live_respects_max_kw(live_api_client: TestClient) -> None:
    response = live_api_client.get(
        "/api/v1/stations/nearest-live",
        params={"lat": 40.4168, "lon": -3.7038, "radius_m": 50000, "min_kw": 0, "max_kw": 30},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["station"]["id"] == "slow-near"
    assert payload["station"]["max_power_kw"] <= 30


def test_nearest_live_all_powers(live_api_client: TestClient) -> None:
    response = live_api_client.get(
        "/api/v1/stations/nearest-live",
        params={"lat": 40.4168, "lon": -3.7038, "radius_m": 5000, "min_kw": 0},
    )
    assert response.status_code == 200
    # El más cercano sin filtro de potencia es slow-near (22 kW en el mismo punto)
    assert response.json()["station"]["id"] == "slow-near"


def test_nearest_live_fallback_when_only_50(live_api_client: TestClient) -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("only-50", 40.4169, -3.7038, kw=50.0, site_name="Solo 50"),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/stations/nearest-live",
            params={"lat": 40.4168, "lon": -3.7038, "radius_m": 5000, "min_kw": 100},
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["station"]["id"] == "only-50"
        assert payload["used_min_kw"] == 50
    finally:
        app.dependency_overrides.clear()