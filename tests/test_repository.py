from __future__ import annotations

import sqlite3

import pytest

from db.repository import StationRepository
from models.station import Connector, Station, StationLocation


def memory_repo() -> StationRepository:
    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return StationRepository(connection)


def sample_station(station_id: str = "es-dgt-S1", raw_ref: str = "S1") -> Station:
    return Station(
        id=station_id,
        source="es-nap-dgt",
        country="ES",
        site_name="Estación prueba",
        operator="Operador Test",
        location=StationLocation(lat=40.4, lon=-3.7, address="Calle Test 1"),
        connectors=[
            Connector(connector_type="iec62196T2COMBO", power_kw=150.0, voltage_v=800.0),
            Connector(connector_type="iec62196T2", power_kw=22.0),
        ],
        max_power_kw=150.0,
        access="public",
        payment_methods=["card", "app"],
        opening_hours="24/7",
        raw_ref=raw_ref,
        source_version="2026-06-23T10:00:00+02:00",
    )


def test_upsert_and_get_by_id() -> None:
    repo = memory_repo()
    station = sample_station()
    assert repo.upsert_stations([station]) == 1

    loaded = repo.get_by_id(station.id)
    assert loaded is not None
    assert loaded.site_name == "Estación prueba"
    assert len(loaded.connectors) == 2
    assert loaded.max_power_kw == 150.0


def test_upsert_updates_connectors() -> None:
    repo = memory_repo()
    station = sample_station()
    repo.upsert_stations([station])

    updated = sample_station()
    updated.connectors = [Connector(connector_type="chademo", power_kw=50.0)]
    updated.max_power_kw = 50.0
    repo.upsert_stations([updated])

    loaded = repo.get_by_id(station.id)
    assert loaded is not None
    assert len(loaded.connectors) == 1
    assert loaded.connectors[0].connector_type == "chademo"


def test_search_bbox_and_min_kw() -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("es-dgt-A", "A"),
            Station(
                id="es-dgt-B",
                source="es-nap-dgt",
                country="ES",
                location=StationLocation(lat=41.0, lon=-3.0),
                connectors=[Connector(connector_type="iec62196T2", power_kw=22.0)],
                max_power_kw=22.0,
                raw_ref="B",
            ),
        ]
    )

    results = repo.search(
        west=-4.0,
        south=40.0,
        east=-3.0,
        north=41.0,
        min_kw=100.0,
        countries=["ES"],
    )
    assert len(results) == 1
    assert results[0].id == "es-dgt-A"


def test_nearby_orders_by_distance() -> None:
    repo = memory_repo()
    repo.upsert_stations(
        [
            Station(
                id="es-dgt-near",
                source="es-nap-dgt",
                country="ES",
                location=StationLocation(lat=40.4169, lon=-3.7038),
                connectors=[Connector(connector_type="iec62196T2", power_kw=22.0)],
                max_power_kw=22.0,
                raw_ref="near",
            ),
            Station(
                id="es-dgt-far",
                source="es-nap-dgt",
                country="ES",
                location=StationLocation(lat=41.5, lon=-3.0),
                connectors=[Connector(connector_type="iec62196T2", power_kw=22.0)],
                max_power_kw=22.0,
                raw_ref="far",
            ),
        ]
    )

    results = repo.nearby(lat=40.4168, lon=-3.7038, radius_m=5000)
    assert len(results) == 1
    assert results[0].id == "es-dgt-near"


def test_export_geojson() -> None:
    repo = memory_repo()
    repo.upsert_stations([sample_station()])
    payload = repo.export_geojson()
    assert payload["type"] == "FeatureCollection"
    assert len(payload["features"]) == 1
    feature = payload["features"][0]
    assert feature["geometry"]["coordinates"] == pytest.approx([-3.7, 40.4])
    assert feature["properties"]["max_power_kw"] == 150.0


def test_delete_by_source() -> None:
    repo = memory_repo()
    repo.upsert_stations([sample_station()])
    deleted = repo.delete_by_source("es-nap-dgt")
    assert deleted == 1
    assert repo.count_stations() == 0


@pytest.mark.integration
def test_load_latest_feeds_to_db(tmp_path, monkeypatch) -> None:
    db_path = tmp_path / "stations.db"
    monkeypatch.setattr("api.config.settings.database_url", f"sqlite:///{db_path}")

    from db.load_cli import load_latest_feeds_to_db

    counts = load_latest_feeds_to_db(export_geojson=False)
    assert counts["ES"] > 10_000
    assert counts["PT"] > 5_000

    with StationRepository() as repo:
        assert repo.count_stations() == counts["ES"] + counts["PT"]
        stats = repo.stats_by_country()
        countries = {row["country"]: row["count"] for row in stats}
        assert countries["ES"] == counts["ES"]
        assert countries["PT"] == counts["PT"]
