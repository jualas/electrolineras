from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from db.connection import database_path_from_url
from db.repository import StationRepository
from ingest.config import repo_root
from ingest.datex_parser import SOURCE_BY_COUNTRY, parse_latest_raw_feed
from ingest.fetch_common import FetchResult
from ingest.fetch_portugal import fetch_portugal_nap
from ingest.fetch_spain import fetch_spain_nap

logger = logging.getLogger(__name__)

CountryCode = Literal["ES", "PT"]
GEOJSON_PATH = repo_root() / "data" / "processed" / "stations.geojson"

FETCHERS = {
    "ES": fetch_spain_nap,
    "PT": fetch_portugal_nap,
}


@dataclass
class CountryIngestResult:
    country: CountryCode
    source: str
    fetched: bool
    raw_file: str | None
    stations_upserted: int
    source_version: str | None
    ingest_run_id: int
    parse_stats: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    countries: list[CountryIngestResult]
    geojson_path: str | None
    geojson_features: int
    db_path: str
    summary: dict[str, Any]


def export_geojson(repo: StationRepository, path: Path | None = None) -> tuple[Path, int]:
    target = path or GEOJSON_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = repo.export_geojson()
    target.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")
    feature_count = len(payload["features"])
    logger.info("GeoJSON exportado: %s (%d features)", target, feature_count)
    return target, feature_count


def build_summary(repo: StationRepository) -> dict[str, Any]:
    return {
        "total_stations": repo.count_stations(),
        "by_country": repo.stats_by_country(),
        "by_power": repo.stats_by_power(),
        "top_operators": repo.top_operators(limit=5),
    }


def ingest_country(
    country: CountryCode,
    repo: StationRepository,
    *,
    fetch: bool = True,
) -> CountryIngestResult:
    source = SOURCE_BY_COUNTRY[country]
    run_id = repo.start_ingest_run(source)
    raw_file: str | None = None

    try:
        if fetch:
            fetch_result: FetchResult = FETCHERS[country]()
            raw_file = fetch_result.output_path.name
            logger.info("Descargado %s: %s", country, raw_file)

        parse_result = parse_latest_raw_feed(country)
        upserted = repo.upsert_stations(parse_result.stations)
        repo.finish_ingest_run(
            run_id,
            status="ok",
            records_upserted=upserted,
            source_version=parse_result.source_version,
        )
        logger.info("Ingestión %s OK: %d estaciones", country, upserted)
        return CountryIngestResult(
            country=country,
            source=source,
            fetched=fetch,
            raw_file=raw_file,
            stations_upserted=upserted,
            source_version=parse_result.source_version,
            ingest_run_id=run_id,
            parse_stats=parse_result.stats.model_dump(),
        )
    except Exception:
        repo.finish_ingest_run(run_id, status="error")
        logger.exception("Ingestión %s fallida", country)
        raise


def run_pipeline(
    *,
    countries: list[CountryCode] | None = None,
    fetch: bool = True,
    export_geojson_file: bool = True,
) -> PipelineResult:
    selected: list[CountryCode] = countries or ["ES", "PT"]
    country_results: list[CountryIngestResult] = []

    with StationRepository() as repo:
        for country in selected:
            country_results.append(ingest_country(country, repo, fetch=fetch))

        geojson_path: str | None = None
        geojson_features = 0
        if export_geojson_file:
            path, geojson_features = export_geojson(repo)
            geojson_path = str(path)

        summary = build_summary(repo)

    return PipelineResult(
        countries=country_results,
        geojson_path=geojson_path,
        geojson_features=geojson_features,
        db_path=str(database_path_from_url()),
        summary=summary,
    )


def pipeline_result_to_dict(result: PipelineResult) -> dict[str, Any]:
    return {
        "db": result.db_path,
        "geojson": result.geojson_path,
        "geojson_features": result.geojson_features,
        "countries": [
            {
                "country": item.country,
                "source": item.source,
                "fetched": item.fetched,
                "raw_file": item.raw_file,
                "stations_upserted": item.stations_upserted,
                "source_version": item.source_version,
                "ingest_run_id": item.ingest_run_id,
                "parse_stats": item.parse_stats,
            }
            for item in result.countries
        ],
        "summary": result.summary,
    }
