#!/usr/bin/env python3
"""Pipeline de ingestión (stub). Implementación completa en tarea #6027."""

from __future__ import annotations

import sys


def main() -> int:
    from ingest.fetch_spain import fetch_spain_nap

    print("=== NAP España ===")
    try:
        result = fetch_spain_nap()
        print(f"OK: {result.output_path}")
    except Exception as exc:
        print(f"ERROR España: {exc}", file=sys.stderr)
        return 1

    print("\ningest_all: Portugal y parse pendientes (#6024, #6025, #6027)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
