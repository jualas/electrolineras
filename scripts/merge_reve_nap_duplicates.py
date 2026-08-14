#!/usr/bin/env python3
"""Fusiona duplicados REVE → NAP (mismo emplazamiento con coords distintas).

Uso:
  DATABASE_URL=sqlite:////path/to/stations.db \\
    PYTHONPATH=src .venv/bin/python scripts/merge_reve_nap_duplicates.py
"""
from __future__ import annotations

import argparse
import logging

from db.repository import StationRepository
from ingest.config import settings

logger = logging.getLogger(__name__)


def merge_duplicates(*, dry_run: bool = False) -> dict[str, int]:
    stats = {"candidates": 0, "enriched": 0, "deleted": 0, "skipped": 0}
    with StationRepository() as repo:
        reve_rows = repo.connection.execute(
            """
            SELECT id FROM station
            WHERE source = 'es-reve-public'
            ORDER BY id
            """
        ).fetchall()
        for row in reve_rows:
            reve = repo.get_by_id(row["id"])
            if reve is None:
                continue
            stats["candidates"] += 1
            nap_id = repo.find_nap_match_for_reve(
                reve.location.lat,
                reve.location.lon,
                site_name=reve.site_name,
                country=reve.country or "ES",
                radius_m=settings.reve_match_radius_m,
                name_radius_m=settings.reve_match_name_radius_m,
            )
            if not nap_id:
                stats["skipped"] += 1
                continue
            logger.info(
                "Merge %s → %s (%s)",
                reve.id,
                nap_id,
                reve.site_name,
            )
            if dry_run:
                stats["enriched"] += 1
                stats["deleted"] += 1
                continue
            repo.enrich_from_reve(nap_id, reve)
            stats["enriched"] += 1
            # Borrar el duplicado REVE (puede ser este u otro con el mismo nombre).
            orphan_id = repo.find_reve_duplicate(
                site_name=reve.site_name,
                lat=reve.location.lat,
                lon=reve.location.lon,
                radius_m=settings.reve_match_name_radius_m,
            )
            to_delete = orphan_id or reve.id
            if to_delete:
                repo.delete_station(to_delete)
                stats["deleted"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Solo listar merges")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    stats = merge_duplicates(dry_run=args.dry_run)
    print(stats)


if __name__ == "__main__":
    main()
