from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from db.repository import StationRepository
from ingest.reve_parser import location_to_station
from ingest.reve_sync import sync_reve_locations
from models.station import Connector, Station, StationLocation

FIXTURES = Path(__file__).parent / "fixtures"


def load_baza_fixture() -> dict:
    return json.loads((FIXTURES / "reve_location_baza.json").read_text(encoding="utf-8"))


def test_location_to_station_parses_zunder_baza() -> None:
    station = location_to_station(load_baza_fixture(), fetched_at=datetime(2026, 6, 25, tzinfo=UTC))

    assert station.id == "es-reve-2098d74a-7782-4b40-bc20-759cd2e2a7ed"
    assert station.source == "es-reve-public"
    assert station.operator == "Zunder"
    assert station.max_power_kw == 360.0
    assert station.dynamic_status == "AVAILABLE"
    assert station.dynamic_price_eur_kwh == pytest.approx(0.59)
    assert len(station.connectors) == 4
    assert all(connector.connector_type == "CCS2" for connector in station.connectors)


def test_sync_reve_inserts_missing_station(tmp_path) -> None:
    db_path = tmp_path / "stations.db"
    with StationRepository(connection=_connect(db_path)) as repo:
        result = sync_reve_locations(
            repo,
            client=_FakeReveClient([load_baza_fixture()]),
            per_page=10,
            max_pages=1,
        )

        assert result.inserted == 1
        assert result.enriched == 0
        station = repo.get_by_id("es-reve-2098d74a-7782-4b40-bc20-759cd2e2a7ed")
        assert station is not None
        assert station.operator == "Zunder"


def test_sync_reve_enriches_nearby_nap_station(tmp_path) -> None:
    db_path = tmp_path / "stations.db"
    with StationRepository(connection=_connect(db_path)) as repo:
        repo.upsert_stations(
            [
                Station(
                    id="es-dgt-test-nearby",
                    source="es-nap-dgt",
                    country="ES",
                    site_name="Repsol ES, Gasóleos El Pilar",
                    operator="REPSOL",
                    location=StationLocation(lat=37.452035, lon=-2.73373, address="A-92"),
                    connectors=[Connector(connector_type="CCS2", power_kw=50.0)],
                    max_power_kw=50.0,
                    access="public",
                    payment_methods=[],
                    opening_hours=None,
                    raw_ref="test-nearby",
                    fetched_at=datetime.now(UTC),
                    source_version="test",
                )
            ]
        )

        result = sync_reve_locations(
            repo,
            client=_FakeReveClient([load_baza_fixture()]),
            per_page=10,
            max_pages=1,
            match_radius_m=150.0,
        )

        assert result.enriched == 0
        assert result.inserted == 1

        repsol = repo.get_by_id("es-dgt-test-nearby")
        assert repsol is not None
        assert repsol.dynamic_status is None


def test_sync_reve_enriches_when_coords_match(tmp_path) -> None:
    db_path = tmp_path / "stations.db"
    fixture = load_baza_fixture()
    with StationRepository(connection=_connect(db_path)) as repo:
        repo.upsert_stations(
            [
                Station(
                    id="es-dgt-zunder-placeholder",
                    source="es-nap-dgt",
                    country="ES",
                    site_name="Placeholder",
                    operator="Zunder",
                    location=StationLocation(
                        lat=float(fixture["coordinates"]["latitude"]),
                        lon=float(fixture["coordinates"]["longitude"]),
                    ),
                    connectors=[Connector(connector_type="CCS2", power_kw=50.0)],
                    max_power_kw=50.0,
                    access="public",
                    payment_methods=[],
                    opening_hours=None,
                    raw_ref="placeholder",
                    fetched_at=datetime.now(UTC),
                    source_version="test",
                )
            ]
        )

        result = sync_reve_locations(
            repo,
            client=_FakeReveClient([fixture]),
            per_page=10,
            max_pages=1,
        )

        assert result.enriched == 1
        assert result.inserted == 0
        station = repo.get_by_id("es-dgt-zunder-placeholder")
        assert station is not None
        assert station.dynamic_status == "AVAILABLE"
        assert station.dynamic_price_eur_kwh == pytest.approx(0.59)


def _connect(db_path: Path):
    import sqlite3

    from db.schema import init_schema

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    init_schema(connection)
    return connection


class _FakeReveClient:
    def __init__(self, locations: list[dict]) -> None:
        self._locations = locations

    def fetch_locations_page(self, *, page: int, per_page: int, **kwargs):
        del kwargs
        if page != 1:
            return [], {"next": None}
        return self._locations[:per_page], {"next": None}
