#!/usr/bin/env python3
"""Comprobaciones post-ingest para cron de producción (#6040)."""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from db.connection import database_path_from_url  # noqa: E402

JOB_SOURCES = {
    "es": "es-nap-dgt",
    "pt": "pt-nap-mobie",
    "reve": "es-reve-public",
}

JOB_MAX_AGE = {
    "es": timedelta(hours=26),
    "pt": timedelta(hours=7),
    "reve": timedelta(hours=5),
}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def _parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def verify_job(connection: sqlite3.Connection, job: str) -> list[str]:
    errors: list[str] = []
    source = JOB_SOURCES[job]
    max_age = JOB_MAX_AGE[job]

    row = connection.execute(
        """
        SELECT id, status, finished_at, records_upserted, source_version
        FROM ingest_run
        WHERE source = ? AND status = 'ok'
        ORDER BY id DESC
        LIMIT 1
        """,
        (source,),
    ).fetchone()
    if row is None:
        _fail(f"Sin ingest_run ok para source={source}", errors)
    else:
        finished_at = _parse_iso(row["finished_at"])
        if finished_at is None:
            _fail(f"ingest_run {source} sin finished_at", errors)
        elif datetime.now(UTC) - finished_at > max_age:
            _fail(
                f"Último ingest_run ok de {source} demasiado antiguo ({finished_at.isoformat()})",
                errors,
            )
        if row["records_upserted"] is None or int(row["records_upserted"]) <= 0:
            _fail(f"ingest_run {source} sin records_upserted", errors)

    total = connection.execute("SELECT COUNT(*) FROM station").fetchone()[0]
    min_total = _env_int("MIN_TOTAL_STATIONS", 18_000)
    if total < min_total:
        _fail(f"total_stations={total} < MIN_TOTAL_STATIONS={min_total}", errors)

    es_count = connection.execute(
        "SELECT COUNT(*) FROM station WHERE country = 'ES'"
    ).fetchone()[0]
    pt_count = connection.execute(
        "SELECT COUNT(*) FROM station WHERE country = 'PT'"
    ).fetchone()[0]

    if job in {"es", "reve"}:
        min_es = _env_int("MIN_ES_STATIONS", 10_000)
        if es_count < min_es:
            _fail(f"estaciones ES={es_count} < MIN_ES_STATIONS={min_es}", errors)

    if job == "pt":
        min_pt = _env_int("MIN_PT_STATIONS", 7_000)
        if pt_count < min_pt:
            _fail(f"estaciones PT={pt_count} < MIN_PT_STATIONS={min_pt}", errors)

    if job == "reve":
        with_price = connection.execute(
            "SELECT COUNT(*) FROM station WHERE country = 'ES' AND dynamic_price IS NOT NULL"
        ).fetchone()[0]
        min_price = _env_int("MIN_REVE_WITH_PRICE", 5_000)
        if with_price < min_price:
            _fail(
                f"ES con precio dinámico={with_price} < MIN_REVE_WITH_PRICE={min_price}",
                errors,
            )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verificación post-ingest (#6040)")
    parser.add_argument(
        "job",
        choices=sorted(JOB_SOURCES),
        help="Tipo de job ejecutado (es, pt, reve)",
    )
    args = parser.parse_args(argv)

    db_path = database_path_from_url(os.environ.get("DATABASE_URL"))
    if not db_path.exists():
        print(f"ERROR: base de datos no encontrada: {db_path}", file=sys.stderr)
        return 1

    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        errors = verify_job(connection, args.job)
    finally:
        connection.close()

    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1

    print(f"OK verify job={args.job}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
