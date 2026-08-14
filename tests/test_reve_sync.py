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
    assert all(connector.status == "AVAILABLE" for connector in station.connectors)
    assert station.connectors[0].evse_id == "ES*ZUN*E1807ER01"
    assert station.connectors[0].physical_reference == "001730"
    assert station.connectors[0].connector_format == "CABLE"


def test_location_price_prefers_dc_over_slower_ac() -> None:
    payload = {
        "id": "price-dc-test",
        "name": "Consum test",
        "address": "Test",
        "postal_code": "00000",
        "owner": {"name": "Eranovum E-Mobility"},
        "coordinates": {"latitude": "37.4", "longitude": "-1.5"},
        "opening_times": {"twentyfourseven": True},
        "evses": [
            {
                "evse_id": "ES*ERA*E1",
                "status": "CHARGING",
                "connectors": [
                    {
                        "standard": "IEC_62196_T2_COMBO",
                        "max_electric_power": 49000,
                        "tariffs": [
                            {
                                "human": ["0.44 EUR/kWh"],
                                "tariff": {
                                    "elements": [
                                        {
                                            "price_components": [
                                                {"type": "ENERGY", "price": 0.44, "vat": 21.0}
                                            ]
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
            {
                "evse_id": "ES*ERA*E2",
                "status": "AVAILABLE",
                "connectors": [
                    {
                        "standard": "IEC_62196_T2",
                        "max_electric_power": 22000,
                        "tariffs": [
                            {
                                "human": ["0.35 EUR/kWh"],
                                "tariff": {
                                    "elements": [
                                        {
                                            "price_components": [
                                                {"type": "ENERGY", "price": 0.35, "vat": 21.0}
                                            ]
                                        }
                                    ]
                                },
                            }
                        ],
                    }
                ],
            },
        ],
    }
    station = location_to_station(payload)
    assert station.dynamic_price_eur_kwh == pytest.approx(0.44)
    assert station.dynamic_status == "CHARGING"


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
        assert station.max_power_kw == 360.0
        assert len(station.connectors) == 4


def test_sync_reve_matches_nap_by_name_when_coords_differ(tmp_path) -> None:
    """NAP y REVE a ~250 m con el mismo site_name: enriquecer NAP y borrar duplicado REVE."""
    db_path = tmp_path / "stations.db"
    reve_location = load_baza_fixture()
    reve_location["id"] = "reve-endesa-dup"
    reve_location["name"] = "62052045780012"
    reve_location["coordinates"] = {"latitude": "38.296397", "longitude": "-2.65099"}
    for evse in reve_location.get("evses") or []:
        evse["status"] = "AVAILABLE"

    with StationRepository(connection=_connect(db_path)) as repo:
        repo.upsert_stations(
            [
                Station(
                    id="es-dgt-segura",
                    source="es-nap-dgt",
                    country="ES",
                    site_name="62052045780012",
                    operator="ENDESA X WAY, S.L.",
                    location=StationLocation(lat=38.298702, lon=-2.651178, address="Segura"),
                    connectors=[
                        Connector(connector_type="iec62196T2", power_kw=11.0),
                        Connector(connector_type="iec62196T2", power_kw=11.0),
                    ],
                    max_power_kw=11.0,
                    access="public",
                    payment_methods=[],
                    opening_hours=None,
                    raw_ref="segura-nap",
                    fetched_at=datetime.now(UTC),
                    source_version="test",
                ),
                Station(
                    id="es-reve-orphan",
                    source="es-reve-public",
                    country="ES",
                    site_name="62052045780012",
                    operator="ENDESA X WAY, S.L.",
                    location=StationLocation(lat=38.296397, lon=-2.65099, address="Segura"),
                    connectors=[Connector(connector_type="Type2", power_kw=11.0)],
                    max_power_kw=11.0,
                    access="public",
                    payment_methods=[],
                    opening_hours=None,
                    raw_ref="orphan",
                    fetched_at=datetime.now(UTC),
                    source_version="test",
                    dynamic_status="AVAILABLE",
                ),
            ]
        )

        result = sync_reve_locations(
            repo,
            client=_FakeReveClient([reve_location]),
            per_page=10,
            max_pages=1,
            match_radius_m=150.0,  # coords > 150 m; debe caer en match por nombre
        )

        assert result.enriched == 1
        assert result.inserted == 0
        nap = repo.get_by_id("es-dgt-segura")
        assert nap is not None
        assert nap.dynamic_status == "AVAILABLE"
        assert repo.get_by_id("es-reve-orphan") is None


def _connect(db_path: Path):
    import sqlite3

    from db.schema import init_schema

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    init_schema(connection)
    return connection


class _FakeReveClient:
    uses_authenticated_api = False

    def __init__(self, locations: list[dict]) -> None:
        self._locations = locations

    def fetch_locations_page(self, *, page: int, per_page: int, **kwargs):
        del kwargs
        if page != 1:
            return [], {"next": None}
        return self._locations[:per_page], {"next": None}
