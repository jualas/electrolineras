from __future__ import annotations

import argparse
import json
import logging
import sys

from ingest.pipeline import pipeline_result_to_dict, run_pipeline


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Pipeline completo: descarga DATEX → parse → SQLite → GeoJSON",
    )
    country = parser.add_mutually_exclusive_group()
    country.add_argument("--es-only", action="store_true", help="Solo España (NAP DGT)")
    country.add_argument("--pt-only", action="store_true", help="Solo Portugal (MOBI.E)")
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help="Omitir descarga; usar último XML en data/raw/",
    )
    parser.add_argument(
        "--no-geojson",
        action="store_true",
        help="No regenerar data/processed/stations.geojson",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Imprimir solo resumen JSON (sin línea extra estaciones=)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    if args.es_only:
        countries = ["ES"]
    elif args.pt_only:
        countries = ["PT"]
    else:
        countries = None

    try:
        result = run_pipeline(
            countries=countries,
            fetch=not args.skip_fetch,
            export_geojson_file=not args.no_geojson,
        )
    except Exception:
        logging.exception("Pipeline de ingestión fallido")
        return 1

    payload = pipeline_result_to_dict(result)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not args.summary:
        total = payload["summary"]["total_stations"]
        print(f"total_estaciones={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
