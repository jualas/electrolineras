#!/usr/bin/env python3
"""Diagnóstico REVE (no imprime la clave)."""
from __future__ import annotations

import os
import sys

import httpx

from ingest.config import settings
from ingest.reve_client import ReveClient


def main() -> int:
    key = (os.environ.get("REVE_API_KEY") or settings.reve_api_key or "").strip()
    print(f"reve_api_key_len={len(key)}")
    print(f"resolved_base_url={settings.resolved_reve_base_url()}")
    if not key:
        print("ERROR: REVE_API_KEY vacía")
        return 1

    headers = {
        "User-Agent": settings.reve_user_agent,
        "x-api-key": key,
    }
    for path in ("/stats", "/cpos"):
        url = f"{settings.reve_external_base_url.rstrip('/')}{path}"
        try:
            response = httpx.get(url, headers=headers, timeout=30)
        except httpx.HTTPError as exc:
            print(f"GET {path}: transport_error={exc}")
            continue
        print(f"GET {path}: status={response.status_code} body={response.text[:140]!r}")

    client = ReveClient()
    try:
        result = client.test_connection()
    except Exception as exc:
        print(f"ReveClient.test_connection: ERROR {exc}")
        return 1
    print(f"test_connection={result}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
