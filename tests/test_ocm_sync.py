from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from db.repository import StationRepository
from ingest.ocm_sync import sync_ocm_reviews
from models.station import Connector, Station, StationLocation

FIXTURES = Path(__file__).parent / "fixtures"


def load_sample_poi() -> dict:
    return json.loads((FIXTURES / "ocm_poi_sample.json").read_text(encoding="utf-8"))


def test_sync_ocm_enriches_nearby_station(tmp_path) -> None:
    db_path = tmp_path / "stations.db"
    import sqlite3

    from db.schema import init_schema

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    init_schema(connection)

    with StationRepository(connection=connection) as repo:
        repo.upsert_stations(
            [
                Station(
                    id="es-dgt-huescar",
                    source="es-nap-dgt",
                    country="ES",
                    site_name="GR-Huescar-002",
                    operator="IBERDROLA",
                    location=StationLocation(lat=37.80401, lon=-2.54443),
                    connectors=[Connector(connector_type="Type2", power_kw=22.0)],
                    max_power_kw=22.0,
                    access="public",
                    payment_methods=[],
                    opening_hours=None,
                    raw_ref="huescar",
                    fetched_at=datetime.now(UTC),
                    source_version="test",
                )
            ]
        )

        result = sync_ocm_reviews(
            repo,
            client=_FakeOcmClient([load_sample_poi()]),
            countries=["ES"],
            max_batches_per_country=1,
        )

        assert result.enriched == 1
        station = repo.get_by_id("es-dgt-huescar")
        assert station is not None
        assert station.external_rating_count == 2
        assert station.external_rating_avg == pytest.approx(4.5)
        assert len(station.external_comments) == 3
        assert station.ocm_poi_id == 123456


class _FakeOcmClient:
    def __init__(self, pois: list[dict]) -> None:
        self._pois = pois

    def iter_pois(self, *, country_code: str, include_comments: bool = True, max_batches: int | None = None):
        del country_code, include_comments
        if max_batches == 0:
            return
        yield self._pois
