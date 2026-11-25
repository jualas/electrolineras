from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from api.config import settings
from api.dependencies import get_repository
from api.integrations.google_places_ev import (
    GooglePlacesEvSnapshot,
    clear_google_places_ev_cache,
    fetch_google_places_ev_status,
)
from api.main import app
from api.routing.station_reliability import evaluate_station_reliability
from db.repository import StationRepository
from models.station import Connector, Station, StationLocation


def _make_station(
    station_id: str = "es-sierra-1",
    *,
    lat: float = 37.9,
    lon: float = -2.9,
    connectors: int = 2,
    power_kw: float = 100.0,
    dynamic_status: str | None = "AVAILABLE",
    dynamic_updated_at: datetime | None = None,
) -> Station:
    return Station(
        id=station_id,
        source="datex2_es",
        country="ES",
        site_name="Cargador Sierra",
        operator="Operador Demo",
        location=StationLocation(lat=lat, lon=lon, address="Ctra. Sierra km 12"),
        connectors=[
            Connector(connector_type="CCS2", power_kw=power_kw) for _ in range(connectors)
        ],
        max_power_kw=power_kw,
        raw_ref=station_id,
        dynamic_status=dynamic_status,
        dynamic_updated_at=dynamic_updated_at,
    )


def test_reliability_high_when_reve_and_google_agree_with_backups() -> None:
    now = datetime.now(UTC)
    station = _make_station(
        connectors=4,
        dynamic_status="AVAILABLE",
        dynamic_updated_at=now - timedelta(minutes=10),
    )
    google = GooglePlacesEvSnapshot(
        place_id="ChIJ-demo",
        display_name="Cargador Sierra",
        distance_m=15.0,
        business_status="OPERATIONAL",
        google_maps_uri="https://maps.google.com/?cid=123",
        rating=4.5,
        user_rating_count=22,
        total_connectors=4,
        available_count=3,
        out_of_service_count=0,
        max_charge_rate_kw=150.0,
        availability_last_update=now.isoformat(),
    )
    report = evaluate_station_reliability(
        station,
        backup_count=5,
        backup_km=12.4,
        backup_label="Plan B Autovía",
        google_snapshot=google,
        google_checked=True,
        now=now,
    )
    assert report.level == "high"
    assert report.score >= 85
    assert not report.isolated_area
    assert not report.single_connector
    assert "REVE + Google" in report.summary


def test_reliability_low_when_google_reports_out_of_service_despite_reve_available() -> None:
    now = datetime.now(UTC)
    station = _make_station(
        connectors=2,
        dynamic_status="AVAILABLE",
        dynamic_updated_at=now - timedelta(minutes=20),
    )
    google = GooglePlacesEvSnapshot(
        place_id="ChIJ-broken",
        display_name="Cargador Sierra",
        distance_m=10.0,
        business_status="OPERATIONAL",
        google_maps_uri="https://maps.google.com/?cid=999",
        rating=2.1,
        user_rating_count=8,
        total_connectors=2,
        available_count=0,
        out_of_service_count=2,
        max_charge_rate_kw=100.0,
        availability_last_update=now.isoformat(),
    )
    report = evaluate_station_reliability(
        station,
        backup_count=2,
        backup_km=18.0,
        backup_label="Alternativa",
        google_snapshot=google,
        google_checked=True,
        now=now,
    )
    assert report.level == "low"
    assert any("fuera de servicio" in w.lower() for w in report.warnings)


def test_reliability_flags_isolated_sierra_single_connector_station() -> None:
    now = datetime.now(UTC)
    station = _make_station(
        connectors=1,
        dynamic_status="AVAILABLE",
        dynamic_updated_at=now - timedelta(minutes=15),
    )
    report = evaluate_station_reliability(
        station,
        backup_count=0,
        backup_km=None,
        backup_label=None,
        isolation_radius_km=50.0,
        google_snapshot=None,
        google_checked=False,
        now=now,
    )
    assert report.isolated_area is True
    assert report.single_connector is True
    assert report.level == "medium"
    assert any("50 km" in w for w in report.warnings)
    assert any("único conector" in w.lower() for w in report.warnings)


def test_fetch_google_places_ev_status_parses_and_caches() -> None:
    clear_google_places_ev_cache()
    calls = 0

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float):
        nonlocal calls
        calls += 1
        assert headers["X-Goog-Api-Key"] == "test-key"
        assert "places.evChargeOptions" in headers["X-Goog-FieldMask"]
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {
            "places": [
                {
                    "id": "place-1",
                    "displayName": {"text": "Ionity Sierra"},
                    "location": {"latitude": 37.9001, "longitude": -2.9001},
                    "businessStatus": "OPERATIONAL",
                    "googleMapsUri": "https://maps.google.com/?cid=1",
                    "rating": 4.4,
                    "userRatingCount": 31,
                    "evChargeOptions": {
                        "connectorCount": 4,
                        "connectorAggregations": [
                            {
                                "type": "EV_CONNECTOR_TYPE_CCS_2",
                                "maxChargeRateKw": 350,
                                "count": 4,
                                "availableCount": 3,
                                "outOfServiceCount": 1,
                                "availabilityLastUpdateTime": "2026-11-25T18:00:00Z",
                            }
                        ],
                    },
                }
            ]
        }
        return resp

    with patch("api.integrations.google_places_ev.httpx.post", side_effect=fake_post):
        snap1 = fetch_google_places_ev_status(37.9, -2.9, api_key="test-key")
        snap2 = fetch_google_places_ev_status(37.9, -2.9, api_key="test-key")

    assert calls == 1
    assert snap1 is not None and snap2 == snap1
    assert snap1.available_count == 3
    assert snap1.out_of_service_count == 1
    assert snap1.total_connectors == 4
    assert snap1.max_charge_rate_kw == 350.0


def test_api_station_reliability_endpoint() -> None:
    connection = sqlite3.connect(":memory:", check_same_thread=False)
    connection.row_factory = sqlite3.Row
    repo = StationRepository(connection)
    repo.upsert_stations([_make_station("es-sierra-only", connectors=1)])

    app.dependency_overrides[get_repository] = lambda: repo
    orig_key = settings.google_maps_api_key
    try:
        settings.google_maps_api_key = ""
        client = TestClient(app)
        resp = client.get("/api/v1/stations/es-sierra-only/reliability?verify_google=false")
        assert resp.status_code == 200
        body = resp.json()
        assert body["station_id"] == "es-sierra-only"
        assert body["level"] == "medium"
        assert body["isolated_area"] is True
        assert body["single_connector"] is True
        assert body["backup_stations_in_radius"] == 0
        assert "google_maps_uri" in body
    finally:
        app.dependency_overrides.pop(get_repository, None)
        settings.google_maps_api_key = orig_key
        connection.close()
