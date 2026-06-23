#!/usr/bin/env python3
"""Pipeline de ingestión (stub). Implementación completa en tarea #6027."""

from __future__ import annotations

import sys


def main() -> int:
    from ingest.fetch_portugal import fetch_portugal_nap
    from ingest.fetch_spain import fetch_spain_nap

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

    print("\ningest_all: parse y persistencia pendientes (#6025, #6026, #6027)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
