from __future__ import annotations

import json
import logging
import sys

from db.connection import database_path_from_url
from ingest.pipeline import pipeline_result_to_dict, run_pipeline

logger = logging.getLogger(__name__)


def load_latest_feeds_to_db(*, export_geojson: bool = True) -> dict[str, int]:
    """Parse + persist sin descargar (usa último XML en data/raw/)."""
    result = run_pipeline(fetch=False, export_geojson_file=export_geojson)
    return {item.country: item.stations_upserted for item in result.countries}


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

    result = run_pipeline(fetch=False, export_geojson_file=not args.no_geojson)
    payload = pipeline_result_to_dict(result)
    upserted = {item["country"]: item["stations_upserted"] for item in payload["countries"]}
    print(json.dumps({"upserted": upserted, "db": payload["db"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
