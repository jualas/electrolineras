from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from db.repository import StationRepository
from ingest.config import settings
from ingest.reve_client import ReveClient, ReveClientError
from ingest.reve_parser import REVE_SOURCE, location_to_station

logger = logging.getLogger(__name__)


@dataclass
class ReveSyncResult:
    pages_fetched: int = 0
    locations_seen: int = 0
    enriched: int = 0
    inserted: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pages_fetched": self.pages_fetched,
            "locations_seen": self.locations_seen,
            "enriched": self.enriched,
            "inserted": self.inserted,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def sync_reve_locations(
    repo: StationRepository,
    *,
    client: ReveClient | None = None,
    per_page: int | None = None,
    max_pages: int | None = None,
    match_radius_m: float | None = None,
) -> ReveSyncResult:
    reve = client or ReveClient()
    result = ReveSyncResult()
    page_size = per_page or (
        settings.reve_external_page_limit
        if reve.uses_authenticated_api
        else settings.reve_sync_per_page
    )
    radius_m = match_radius_m if match_radius_m is not None else settings.reve_match_radius_m
    fetched_at = datetime.now(UTC)
    run_id = repo.start_ingest_run(REVE_SOURCE)
    source_version = "reve-external-api" if reve.uses_authenticated_api else "reve-public-api"

    try:
        page = 1
        while True:
            try:
                data, pagination = reve.fetch_locations_page(page=page, per_page=page_size)
            except ReveClientError as exc:
                if page == 1 and reve.uses_authenticated_api and "429" in str(exc):
                    logger.warning(
                        "API external REVE en rate limit; este sync continúa con la API pública",
                    )
                    reve = ReveClient(api_key="", base_url=settings.reve_public_base_url)
                    page_size = per_page or settings.reve_sync_per_page
                    source_version = "reve-public-api-fallback"
                    data, pagination = reve.fetch_locations_page(page=page, per_page=page_size)
                else:
                    raise
            result.pages_fetched += 1
            logger.info(
                "REVE página %d: %d emplazamientos (total vistos %d)",
                page,
                len(data),
                result.locations_seen + len(data),
            )
            for raw_location in data:
                result.locations_seen += 1
                try:
                    station = location_to_station(raw_location, fetched_at=fetched_at)
                except (KeyError, TypeError, ValueError) as exc:
                    result.skipped += 1
                    result.errors.append(str(exc))
                    continue

                existing_id = repo.find_nearby_station_id(
                    station.location.lat,
                    station.location.lon,
                    radius_m=radius_m,
                    country="ES",
                )
                if existing_id:
                    repo.enrich_from_reve(existing_id, station)
                    result.enriched += 1
                else:
                    repo.upsert_stations([station])
                    result.inserted += 1

            next_page = pagination.get("next")
            if next_page is None:
                break
            if max_pages is not None and result.pages_fetched >= max_pages:
                break
            page = int(next_page)
            if reve.uses_authenticated_api and settings.reve_sync_page_delay_seconds > 0:
                time.sleep(settings.reve_sync_page_delay_seconds)

        repo.finish_ingest_run(
            run_id,
            status="ok",
            records_upserted=result.enriched + result.inserted,
            source_version=source_version,
        )
    except Exception as exc:
        repo.finish_ingest_run(run_id, status="error", records_upserted=0, source_version=None)
        raise exc

    logger.info(
        "REVE sync: %d vistos, %d enriquecidos, %d insertados, %d omitidos",
        result.locations_seen,
        result.enriched,
        result.inserted,
        result.skipped,
    )
    return result
