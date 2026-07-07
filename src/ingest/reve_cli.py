from __future__ import annotations

import argparse
import json
import logging
import sys

from db.repository import StationRepository
from ingest.pipeline import export_geojson
from ingest.reve_client import ReveClient, ReveClientError
from ingest.reve_sync import sync_reve_locations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sincroniza emplazamientos REVE (mapareve.es) con SQLite",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Limitar páginas (útil en desarrollo)",
    )
    parser.add_argument(
        "--per-page",
        type=int,
        default=None,
        help="Tamaño de página REVE (default settings.reve_sync_per_page)",
    )
    parser.add_argument(
        "--geojson",
        action="store_true",
        help="Regenerar data/processed/stations.geojson tras sync",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="Imprimir solo JSON de resultado",
    )
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Probar REVE_API_KEY / conectividad (GET /stats) y salir",
    )
    args = parser.parse_args(argv)

    if args.test_connection:
        try:
            payload = ReveClient().test_connection()
        except ReveClientError as exc:
            print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    try:
        with StationRepository() as repo:
            result = sync_reve_locations(
                repo,
                per_page=args.per_page,
                max_pages=args.max_pages,
            )
            total_stations = repo.count_stations()
            geojson_path = None
            geojson_features = None
            if args.geojson:
                path, features = export_geojson(repo)
                geojson_path = str(path)
                geojson_features = features
    except Exception:
        logging.exception("Sync REVE fallido")
        return 1

    payload: dict[str, object] = {
        "reve_sync": result.to_dict(),
        "total_stations": total_stations,
    }
    if geojson_path:
        payload["geojson_path"] = geojson_path
        payload["geojson_features"] = geojson_features

    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not args.summary:
        print(f"reve_enriched={result.enriched} reve_inserted={result.inserted}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
