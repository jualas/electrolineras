#!/usr/bin/env python3
"""Pipeline de ingestión. Persistencia completa en tareas #6026–#6027."""

from __future__ import annotations

import sys


def main() -> int:
    from ingest.fetch_portugal import fetch_portugal_nap
    from ingest.fetch_spain import fetch_spain_nap
    from db.load_cli import load_latest_feeds_to_db

    print("=== NAP España ===")
    try:
        es = fetch_spain_nap()
        print(f"OK: {es.output_path}")
    except Exception as exc:
        print(f"ERROR España: {exc}", file=sys.stderr)
        return 1

    print("\n=== NAP Portugal ===")
    try:
        pt = fetch_portugal_nap()
        print(f"OK: {pt.output_path} ({pt.bytes_written:,} bytes)")
    except Exception as exc:
        print(f"ERROR Portugal: {exc}", file=sys.stderr)
        return 1

    print("\n=== Persistencia SQLite + GeoJSON ===")
    try:
        counts = load_latest_feeds_to_db(export_geojson=True)
        print(f"OK: ES={counts['ES']}, PT={counts['PT']}")
    except Exception as exc:
        print(f"ERROR persistencia: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
