from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from db.repository import StationRepository
from ingest.config import settings
from ingest.ocm_client import OcmClient
from ingest.ocm_export import iter_pois_from_export
from ingest.ocm_parser import OCM_SOURCE, comments_to_json, poi_to_review_profile

logger = logging.getLogger(__name__)

OCM_COUNTRY_CODES = ("ES", "PT")


@dataclass
class OcmSyncResult:
    batches_fetched: int = 0
    pois_seen: int = 0
    enriched: int = 0
    skipped_no_reviews: int = 0
    skipped_no_match: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "batches_fetched": self.batches_fetched,
            "pois_seen": self.pois_seen,
            "enriched": self.enriched,
            "skipped_no_reviews": self.skipped_no_reviews,
            "skipped_no_match": self.skipped_no_match,
            "errors": self.errors,
        }


def _iter_api_poi_batches(
    client: OcmClient,
    countries: list[str],
    max_batches_per_country: int | None,
) -> Iterator[tuple[str, list[dict]]]:
    for country in countries:
        country_code = country.upper()
        for pois in client.iter_pois(
            country_code=country_code,
            max_batches=max_batches_per_country,
        ):
            yield country_code, pois


def _process_poi_batch(
    repo: StationRepository,
    result: OcmSyncResult,
    country_code: str,
    pois: list[dict],
    *,
    radius_m: float,
    max_comments: int,
    fetched_at: datetime,
) -> None:
    result.batches_fetched += 1
    logger.info(
        "OCM %s lote %d: %d POIs",
        country_code,
        result.batches_fetched,
        len(pois),
    )
    for poi in pois:
        result.pois_seen += 1
        try:
            profile = poi_to_review_profile(poi, max_comments=max_comments)
        except (KeyError, TypeError, ValueError) as exc:
            result.errors.append(str(exc))
            continue
        if profile is None or not profile.has_reviews:
            result.skipped_no_reviews += 1
            continue
        match_country = profile.country or country_code
        existing_id = repo.find_nearby_station_id(
            profile.lat,
            profile.lon,
            radius_m=radius_m,
            country=match_country,
        )
        if not existing_id:
            result.skipped_no_match += 1
            continue
        repo.enrich_from_ocm(
            existing_id,
            ocm_poi_id=profile.ocm_poi_id,
            rating_avg=profile.rating_avg,
            rating_count=profile.rating_count,
            comments_json=json.dumps(
                comments_to_json(profile.comments),
                ensure_ascii=False,
            ),
            updated_at=fetched_at,
        )
        result.enriched += 1


def sync_ocm_reviews(
    repo: StationRepository,
    *,
    client: OcmClient | None = None,
    export_dir: Path | None = None,
    countries: list[str] | None = None,
    max_batches_per_country: int | None = None,
    match_radius_m: float | None = None,
) -> OcmSyncResult:
    result = OcmSyncResult()
    radius_m = match_radius_m if match_radius_m is not None else settings.ocm_match_radius_m
    max_comments = settings.ocm_max_comments_stored
    fetched_at = datetime.now(UTC)
    run_id = repo.start_ingest_run(OCM_SOURCE)

    target_countries = countries or list(OCM_COUNTRY_CODES)
    source_version = "open-charge-map-export" if export_dir is not None else "open-charge-map-api"

    if export_dir is not None:
        poi_batches = iter_pois_from_export(
            export_dir,
            countries=target_countries,
            max_batches_per_country=max_batches_per_country,
        )
    else:
        ocm = client or OcmClient()
        poi_batches = _iter_api_poi_batches(ocm, target_countries, max_batches_per_country)

    try:
        for country_code, pois in poi_batches:
            country_upper = country_code.upper()
            if country_upper not in OCM_COUNTRY_CODES:
                result.errors.append(f"unsupported_country:{country_upper}")
                continue
            _process_poi_batch(
                repo,
                result,
                country_code,
                pois,
                radius_m=radius_m,
                max_comments=max_comments,
                fetched_at=fetched_at,
            )

        repo.finish_ingest_run(
            run_id,
            status="ok",
            records_upserted=result.enriched,
            source_version=source_version,
        )
    except Exception as exc:
        repo.finish_ingest_run(run_id, status="error", records_upserted=0, source_version=None)
        raise exc

    logger.info(
        "OCM sync: %d POIs, %d enriquecidos, %d sin reseñas, %d sin match",
        result.pois_seen,
        result.enriched,
        result.skipped_no_reviews,
        result.skipped_no_match,
    )
    return result
