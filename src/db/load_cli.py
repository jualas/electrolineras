from __future__ import annotations

import json
import logging
import sys

from db.connection import database_path_from_url
from db.repository import StationRepository
from ingest.config import repo_root
from ingest.datex_parser import parse_latest_raw_feed

logger = logging.getLogger(__name__)


def load_latest_feeds_to_db(*, export_geojson: bool = True) -> dict[str, int]:
    counts: dict[str, int] = {}
    with StationRepository() as repo:
        for country in ("ES", "PT"):
            result = parse_latest_raw_feed(country)
            counts[country] = repo.upsert_stations(result.stations)
            logger.info("Persistidas %d estaciones %s", counts[country], country)

        if export_geojson:
            geojson_path = repo_root() / "data" / "processed" / "stations.geojson"
            geojson_path.parent.mkdir(parents=True, exist_ok=True)
            payload = repo.export_geojson()
            geojson_path.write_text(
                json.dumps(payload, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            logger.info(
                "GeoJSON exportado: %s (%d features)",
                geojson_path,
                len(payload["features"]),
            )
    return counts


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Persistir feeds DATEX parseados en SQLite")
    parser.add_argument("--no-geojson", action="store_true", help="No exportar stations.geojson")
    parser.add_argument("--db-info", action="store_true", help="Mostrar ruta de la base de datos")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    if args.db_info:
        print(database_path_from_url())
        return 0

    counts = load_latest_feeds_to_db(export_geojson=not args.no_geojson)
    print(json.dumps({"upserted": counts, "db": str(database_path_from_url())}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
