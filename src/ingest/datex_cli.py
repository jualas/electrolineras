from __future__ import annotations

import argparse
import json
import logging
import sys

from ingest.datex_parser import parse_datex_file, parse_latest_raw_feed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Parsear feed DATEX II (ES/PT) a estaciones normalizadas",
    )
    parser.add_argument("xml_path", nargs="?", help="Ruta al XML DATEX")
    parser.add_argument("--country", choices=["ES", "PT"], help="País si no se detecta del XML")
    parser.add_argument(
        "--latest",
        choices=["ES", "PT"],
        help="Usar último XML del manifest en data/raw/",
    )
    parser.add_argument("--summary", action="store_true", help="Imprimir solo resumen JSON")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s — %(message)s",
    )

    if args.latest:
        result = parse_latest_raw_feed(args.latest)
    elif args.xml_path:
        result = parse_datex_file(args.xml_path, country=args.country)
    else:
        parser.error("Indica xml_path o --latest ES|PT")

    payload = {
        "country": result.country,
        "source": result.source,
        "source_version": result.source_version,
        "stats": result.stats.model_dump(),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    if not args.summary:
        print(f"estaciones={len(result.stations)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
