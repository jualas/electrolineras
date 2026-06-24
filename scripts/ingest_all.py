#!/usr/bin/env python3
"""Pipeline completo de ingestión (DATEX → SQLite → GeoJSON)."""

from ingest.pipeline_cli import main

if __name__ == "__main__":
    raise SystemExit(main())
