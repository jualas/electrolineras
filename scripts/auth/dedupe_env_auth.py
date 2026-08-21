#!/usr/bin/env python3
"""Elimina entradas duplicadas de auth en .env de docker-compose (mantiene la primera)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

AUTH_KEYS = frozenset(
    {
        "PRIVATE_STACK_ENABLED",
        "CHARGING_AGENT_ENABLED",
        "SESSION_SECRET",
        "SESSION_COOKIE_SECURE",
        "PRIVATE_AUTH_USERS",
        "PRIVATE_AUTH_PASSWORD_HASH",
        "PRIVATE_TOTP_SECRET",
        "PRIVATE_API_TOKEN",
    }
)


def dedupe_env(path: Path) -> int:
    lines = path.read_text().splitlines()
    seen: set[str] = set()
    removed = 0
    out: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key = line.split("=", 1)[0]
            if key in AUTH_KEYS:
                if key in seen:
                    removed += 1
                    print(f"Eliminada línea duplicada: {key}", file=sys.stderr)
                    continue
                seen.add(key)
        out.append(line)

    path.write_text("\n".join(out) + "\n")
    return removed


def main() -> None:
    parser = argparse.ArgumentParser(description="Quitar duplicados PRIVATE_/SESSION_ en .env")
    parser.add_argument(
        "env_file",
        nargs="?",
        default="/mnt/datos/docker/electrolineras/.env",
        help="Ruta al .env de producción",
    )
    args = parser.parse_args()
    path = Path(args.env_file)
    if not path.is_file():
        print(f"ERROR: no existe {path}", file=sys.stderr)
        sys.exit(1)
    n = dedupe_env(path)
    print(f"Listo: {n} línea(s) duplicada(s) eliminada(s) en {path}")
    if n:
        print("Reinicia: cd /mnt/datos/docker/electrolineras && docker compose up -d --force-recreate electrolineras")


if __name__ == "__main__":
    main()
