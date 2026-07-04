from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPO_ROOT / "scripts" / "cron" / "verify_ingest.py"


def _init_db(db_path: Path) -> None:
    sys.path.insert(0, str(REPO_ROOT / "src"))
    from db.schema import init_schema

    connection = sqlite3.connect(db_path)
    init_schema(connection)
    now = datetime.now(UTC).isoformat()
    for idx in range(12_000):
        connection.execute(
            """
            INSERT INTO station (
                id, source, country, site_name, operator, lat, lon, address,
                max_power_kw, access, payment_methods, opening_hours, raw_ref,
                fetched_at, source_version
            ) VALUES (?, 'es-nap-dgt', 'ES', ?, ?, 40.0, -3.7, NULL, 50, 'public',
                      '[]', NULL, ?, ?, 'test')
            """,
            (f"es-{idx}", f"Site {idx}", "Op", f"ref-{idx}", now),
        )
    for idx in range(8_000):
        connection.execute(
            """
            INSERT INTO station (
                id, source, country, site_name, operator, lat, lon, address,
                max_power_kw, access, payment_methods, opening_hours, raw_ref,
                fetched_at, source_version
            ) VALUES (?, 'pt-nap-mobie', 'PT', ?, ?, 38.7, -9.1, NULL, 22, 'public',
                      '[]', NULL, ?, ?, 'test')
            """,
            (f"pt-{idx}", f"Site {idx}", "Op", f"ref-{idx}", now),
        )
    for idx in range(6_000):
        connection.execute(
            """
            UPDATE station SET dynamic_price = 0.5, dynamic_status = 'AVAILABLE'
            WHERE id = ?
            """,
            (f"es-{idx}",),
        )
    connection.execute(
        """
        INSERT INTO ingest_run (source, started_at, finished_at, source_version, records_upserted, status)
        VALUES ('es-nap-dgt', ?, ?, 'v1', 100, 'ok')
        """,
        (now, now),
    )
    connection.execute(
        """
        INSERT INTO ingest_run (source, started_at, finished_at, source_version, records_upserted, status)
        VALUES ('pt-nap-mobie', ?, ?, 'v1', 100, 'ok')
        """,
        (now, now),
    )
    connection.execute(
        """
        INSERT INTO ingest_run (source, started_at, finished_at, source_version, records_upserted, status)
        VALUES ('es-reve-public', ?, ?, 'reve', 500, 'ok')
        """,
        (now, now),
    )
    connection.commit()
    connection.close()


def _run_verify(db_path: Path, job: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path}"
    return subprocess.run(
        [sys.executable, str(VERIFY_SCRIPT), job],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_verify_es_ok(tmp_path: Path) -> None:
    db_path = tmp_path / "stations.db"
    _init_db(db_path)
    result = _run_verify(db_path, "es")
    assert result.returncode == 0, result.stderr
    assert "OK verify job=es" in result.stdout


def test_verify_reve_fails_without_price(tmp_path: Path) -> None:
    db_path = tmp_path / "stations.db"
    _init_db(db_path)
    connection = sqlite3.connect(db_path)
    connection.execute("UPDATE station SET dynamic_price = NULL, dynamic_status = NULL")
    connection.commit()
    connection.close()

    result = _run_verify(db_path, "reve")
    assert result.returncode == 1
    assert "MIN_REVE_WITH_PRICE" in result.stderr
