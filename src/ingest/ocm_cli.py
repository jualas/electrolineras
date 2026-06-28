from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from db.repository import StationRepository
from ingest.config import settings
from ingest.ocm_client import OcmClientError
from ingest.ocm_export import OcmExportError
from ingest.ocm_sync import sync_ocm_reviews


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Sincroniza valoraciones Open Charge Map")
    parser.add_argument("--summary", action="store_true", help="Imprime JSON resumen")
    parser.add_argument(
        "--countries",
        default="ES,PT",
        help="Países a sincronizar (default ES,PT)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=None,
        help="Límite de lotes por país (debug)",
    )
    parser.add_argument(
        "--from-export",
        action="store_true",
        help="Lee datos locales de ocm-export (GitHub) sin API key",
    )
    parser.add_argument(
        "--export-dir",
        type=Path,
        default=None,
        help="Ruta a data/ del export (default: data/raw/ocm-export/data)",
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s — %(message)s")

    countries = [token.strip().upper() for token in args.countries.split(",") if token.strip()]
    export_dir = args.export_dir or settings.ocm_export_dir if args.from_export else None

    try:
        with StationRepository() as repo:
            result = sync_ocm_reviews(
                repo,
                max_batches_per_country=args.max_pages,
                countries=countries,
                export_dir=export_dir,
            )
            total_stations = repo.count_stations()
    except OcmClientError as exc:
        logging.exception("Sync OCM fallido")
        if "OCM_API_KEY" in str(exc):
            print(
                "ERROR: falta OCM_API_KEY. Opciones:\n"
                "  1) Registrar app en https://openchargemap.io cuando vuelva la web\n"
                "  2) Usar export GitHub: scripts/fetch_ocm_export.sh && "
                "electrolineras-sync-ocm --from-export --summary",
                file=sys.stderr,
            )
        return 1
    except OcmExportError as exc:
        logging.exception("Sync OCM export fallido")
        print(
            f"ERROR: {exc}\n"
            "Descarga el export con: scripts/fetch_ocm_export.sh",
            file=sys.stderr,
        )
        return 1

    payload = {
        "ocm_sync": result.to_dict(),
        "total_stations": total_stations,
        "source": "export" if export_dir is not None else "api",
    }

    if args.summary:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"ocm_enriched={result.enriched} pois_seen={result.pois_seen}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
