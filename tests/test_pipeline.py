from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from db.repository import StationRepository
from ingest.datex_parser import SOURCE_BY_COUNTRY
from ingest.pipeline import (
    ingest_country,
    pipeline_result_to_dict,
    run_pipeline,
)
from models.station import Connector, ParseResult, ParseStats, Station, StationLocation


@pytest.fixture
def memory_repo() -> StationRepository:
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return StationRepository(connection)


def sample_parse_result(country: str, count: int = 2) -> ParseResult:
    source = SOURCE_BY_COUNTRY[country]
    stations = [
        Station(
            id=f"{country.lower()}-test-S{i}",
            source=source,
            country=country,
            location=StationLocation(lat=40.0 + i * 0.1, lon=-3.0),
            connectors=[Connector(connector_type="iec62196T2", power_kw=22.0 + i * 50)],
            max_power_kw=22.0 + i * 50,
            raw_ref=f"S{i}",
        )
        for i in range(count)
    ]
    return ParseResult(
        stations=stations,
        stats=ParseStats(sites_seen=count, sites_parsed=count),
        source=source,
        country=country,
        source_version="2026-06-23T00:00:00Z",
    )


def test_ingest_country_without_fetch(memory_repo: StationRepository) -> None:
    with patch("ingest.pipeline.parse_latest_raw_feed", return_value=sample_parse_result("ES", 1)):
        result = ingest_country("ES", memory_repo, fetch=False)

    assert result.stations_upserted == 1
    assert result.fetched is False
    assert memory_repo.count_stations(countries=["ES"]) == 1


def test_run_pipeline_es_only(memory_repo: StationRepository) -> None:
    def parse_side_effect(country: str) -> ParseResult:
        return sample_parse_result(country, 2)

    with (
        patch("ingest.pipeline.StationRepository", return_value=memory_repo),
        patch("ingest.pipeline.parse_latest_raw_feed", side_effect=parse_side_effect),
        patch("ingest.pipeline.export_geojson", return_value=(Path("/tmp/stations.geojson"), 2)),
    ):
        pipeline_result = run_pipeline(countries=["ES"], fetch=False, export_geojson_file=True)

    assert len(pipeline_result.countries) == 1
    assert pipeline_result.countries[0].stations_upserted == 2
    assert pipeline_result.geojson_features == 2


def test_pipeline_result_to_dict_includes_summary(memory_repo: StationRepository) -> None:
    with patch("ingest.pipeline.parse_latest_raw_feed", return_value=sample_parse_result("ES", 1)):
        country_result = ingest_country("ES", memory_repo, fetch=False)

    from ingest.pipeline import PipelineResult

    payload = pipeline_result_to_dict(
        PipelineResult(
            countries=[country_result],
            geojson_path="/tmp/stations.geojson",
            geojson_features=1,
            db_path="/tmp/stations.db",
            summary={
                "total_stations": 1,
                "by_country": [{"country": "ES", "count": 1, "max_kw": 22.0}],
                "by_power": [],
                "top_operators": [],
            },
        )
    )
    assert payload["summary"]["total_stations"] == 1
    assert payload["countries"][0]["country"] == "ES"
