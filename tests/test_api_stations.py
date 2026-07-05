from __future__ import annotations

import sqlite3

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
    station_id: str = "es-dgt-S1",
    raw_ref: str = "S1",
    country: str = "ES",
    lat: float = 40.4,
    lon: float = -3.7,
    max_kw: float = 150.0,
    operator: str = "Operador Test",
    *,
    site_name: str = "Estación prueba",
    dynamic_status: str | None = None,
    dynamic_price_eur_kwh: float | None = None,
) -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt" if country == "ES" else "pt-mobie",
        country=country,
        site_name=site_name,
        operator=operator,
        location=StationLocation(lat=lat, lon=lon, address="Calle Test 1"),
        connectors=[Connector(connector_type="iec62196T2COMBO", power_kw=max_kw)],
        max_power_kw=max_kw,
        access="public",
        raw_ref=raw_ref,
        source_version="2026-06-23T10:00:00+02:00",
        dynamic_status=dynamic_status,
        dynamic_price_eur_kwh=dynamic_price_eur_kwh,
    )


@pytest.fixture
def api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("es-dgt-A", "A", "ES", 40.4, -3.7, 150.0, "Operador A"),
            sample_station("es-dgt-B", "B", "ES", 41.0, -3.0, 22.0, "Operador B"),
            sample_station("pt-mobie-C", "C", "PT", 38.7, -9.1, 50.0, "Operador A"),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


def test_list_stations_json(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload["stations"]) == 3
    assert payload["pagination"]["total"] == 3
    assert payload["pagination"]["has_more"] is False


def test_list_stations_geojson(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?format=geojson")
    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 3
    feature = payload["features"][0]
    assert feature["geometry"]["type"] == "Point"
    assert "max_power_kw" in feature["properties"]


def test_list_stations_exposes_dynamic_fields(api_client: TestClient) -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station(
                "es-dgt-dynamic",
                "D",
                dynamic_status="AVAILABLE",
                dynamic_price_eur_kwh=0.59,
            )
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    try:
        json_response = client.get("/api/v1/stations?country=ES")
        station = json_response.json()["stations"][0]
        assert station["dynamic_status"] == "AVAILABLE"
        assert station["dynamic_price_eur_kwh"] == pytest.approx(0.59)

        geo_response = client.get("/api/v1/stations?format=geojson&country=ES")
        props = geo_response.json()["features"][0]["properties"]
        assert props["dynamic_status"] == "AVAILABLE"
        assert props["dynamic_price_eur_kwh"] == pytest.approx(0.59)
    finally:
        app.dependency_overrides.clear()


def test_list_stations_min_kw_filter(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?min_kw=100")
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["stations"][0]["id"] == "es-dgt-A"


def test_list_stations_country_filter(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?country=PT")
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["stations"][0]["country"] == "PT"


def test_list_stations_bbox_filter(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?bbox=-4,40,-3.5,40.5")
    payload = response.json()
    assert payload["pagination"]["total"] == 1
    assert payload["stations"][0]["id"] == "es-dgt-A"


def test_list_stations_pagination(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?limit=2&offset=1")
    payload = response.json()
    assert len(payload["stations"]) == 2
    assert payload["pagination"]["total"] == 3
    assert payload["pagination"]["has_more"] is False


def test_list_stations_invalid_bbox(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?bbox=1,2")
    assert response.status_code == 422


def test_list_stations_invalid_kw_range(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?min_kw=100&max_kw=50")
    assert response.status_code == 422


def test_get_station_by_id(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations/es-dgt-A")
    assert response.status_code == 200
    assert response.json()["id"] == "es-dgt-A"
    assert response.json()["max_power_kw"] == 150.0


def test_get_station_not_found(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations/missing-id")
    assert response.status_code == 404


def test_meta_stats(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/meta/stats")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_stations"] == 3
    assert len(payload["by_country"]) == 2
    assert len(payload["by_power_band"]) == 2


def test_meta_operators(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/meta/operators")
    assert response.status_code == 200
    payload = response.json()
    assert payload["operators"][0]["operator"] == "Operador A"
    assert payload["operators"][0]["count"] == 2


def test_meta_operators_by_country(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/meta/operators?country=PT")
    payload = response.json()
    assert payload["country"] == "PT"
    assert len(payload["operators"]) == 1


def test_list_stations_geojson_serializes_external_comments(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/stations?format=geojson&limit=1")
    assert response.status_code == 200
    comments = response.json()["features"][0]["properties"]["external_comments"]
    assert isinstance(comments, str)


def test_list_stations_public_open_only_scans_past_commercial(api_client: TestClient) -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("es-dgt-cc-slow", "CC-SLOW", "ES", 40.41, -3.71, 22.0, site_name="Mercadona Test"),
            sample_station("es-dgt-cc-fast", "CC-FAST", "ES", 40.41, -3.71, 90.0, site_name="CC Mazarrón Park"),
            sample_station("es-dgt-public", "PUB", "ES", 40.41, -3.71, 50.0, site_name="Plaza Mayor"),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    try:
        response = client.get(
            "/api/v1/stations?format=geojson&bbox=-4,40,0,41&public_open_only=true&limit=10"
        )
        assert response.status_code == 200
        payload = response.json()
        ids = {feature["properties"]["id"] for feature in payload["features"]}
        assert "es-dgt-public" in ids
        assert "es-dgt-cc-fast" in ids
        assert "es-dgt-cc-slow" not in ids
    finally:
        app.dependency_overrides.clear()


def test_list_stations_available_only(api_client: TestClient) -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("es-dgt-avail", "A1", dynamic_status="AVAILABLE"),
            sample_station("es-dgt-busy", "B1", dynamic_status="CHARGING"),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    try:
        response = client.get("/api/v1/stations?available_only=true&limit=10")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["stations"]}
        assert ids == {"es-dgt-avail"}
    finally:
        app.dependency_overrides.clear()


def test_list_stations_connector_types_filter(api_client: TestClient) -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("es-dgt-ccs", "C1"),
            Station(
                id="es-dgt-type2",
                source="es-nap-dgt",
                country="ES",
                site_name="AC lento",
                operator="Operador Test",
                location=StationLocation(lat=40.4, lon=-3.7, address="Calle Test 1"),
                connectors=[Connector(connector_type="Type2", power_kw=22.0)],
                max_power_kw=22.0,
                access="public",
                raw_ref="T1",
                source_version="2026-06-23T10:00:00+02:00",
            ),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    try:
        response = client.get("/api/v1/stations?connector_types=CCS2&limit=10")
        assert response.status_code == 200
        ids = {item["id"] for item in response.json()["stations"]}
        assert ids == {"es-dgt-ccs"}
    finally:
        app.dependency_overrides.clear()


def test_count_matching() -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("es-dgt-A", "A", "ES", 40.4, -3.7, 150.0),
            sample_station("es-dgt-B", "B", "ES", 41.0, -3.0, 22.0),
        ]
    )
    assert repo.count_matching(min_kw=100) == 1
    assert repo.count_matching(countries=["ES"]) == 2
