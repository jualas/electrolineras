#!/usr/bin/env python3
"""Comprobaciones de salud para producción (#6045)."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from db.connection import database_path_from_url  # noqa: E402

# Reutilizar reglas de ingest (#6040)
sys.path.insert(0, str(REPO_ROOT / "scripts" / "cron"))
from verify_ingest import verify_job  # noqa: E402


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return int(raw)


def check_http(name: str, url: str, timeout_s: float) -> str | None:
    if not url:
        return None
    request = urllib.request.Request(url, headers={"User-Agent": "Electrolineras-monitor/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = response.read(4096)
    except urllib.error.URLError as exc:
        return f"{name}: no responde ({exc})"
    if name == "api" and b'"status"' not in body and b"ok" not in body.lower():
        return f"{name}: respuesta inesperada"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        payload = None
    if name.startswith("osrm") and isinstance(payload, dict) and payload.get("code") != "Ok":
        return f"{name}: OSRM code={payload.get('code')}"
    if name == "nominatim" and isinstance(payload, list) and not payload:
        return f"{name}: sin resultados"
    return None


def check_disk(path: str, warn_pct: int) -> str | None:
    target = Path(path)
    if not target.exists():
        return f"disk: ruta inexistente {path}"
    usage = os.statvfs(target)
    total = usage.f_blocks * usage.f_frsize
    free = usage.f_bavail * usage.f_frsize
    if total <= 0:
        return f"disk: no se pudo calcular uso en {path}"
    used_pct = int((1 - free / total) * 100)
    if used_pct >= warn_pct:
        return f"disk: {path} al {used_pct}% (umbral {warn_pct}%)"
    return None


def check_database(db_path: Path) -> list[str]:
    errors: list[str] = []
    if not db_path.exists():
        return [f"db: no existe {db_path}"]
    try:
        connection = sqlite3.connect(db_path)
        connection.row_factory = sqlite3.Row
    except sqlite3.Error as exc:
        return [f"db: no se pudo abrir ({exc})"]

    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            errors.append(f"db: integrity_check={integrity}")
        for job in ("es", "pt", "reve"):
            errors.extend(verify_job(connection, job))
    except sqlite3.Error as exc:
        errors.append(f"db: error consultando ({exc})")
    finally:
        connection.close()
    return errors


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(path: Path, state: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")


def should_alert(state: dict, check_id: str, failed: bool, cooldown_min: int) -> bool:
    entry = state.get(check_id, {})
    was_failed = bool(entry.get("failed"))
    if not failed:
        state[check_id] = {"failed": False, "last_alert": entry.get("last_alert")}
        return False
    now = datetime.now(UTC)
    if not was_failed:
        state[check_id] = {"failed": True, "last_alert": now.isoformat()}
        return True
    last_raw = entry.get("last_alert")
    if last_raw:
        try:
            last = datetime.fromisoformat(last_raw)
            if last.tzinfo is None:
                last = last.replace(tzinfo=UTC)
            if (now - last).total_seconds() < cooldown_min * 60:
                state[check_id] = {"failed": True, "last_alert": last_raw}
                return False
        except ValueError:
            pass
    state[check_id] = {"failed": True, "last_alert": now.isoformat()}
    return True


def run_checks() -> list[tuple[str, str]]:
    failures: list[tuple[str, str]] = []
    timeout = float(os.environ.get("MONITOR_HTTP_TIMEOUT_SECONDS", "10"))
    api_url = os.environ.get("MONITOR_API_URL", "http://127.0.0.1:8015/health")
    osrm_car = os.environ.get(
        "MONITOR_OSRM_CAR_URL",
        "http://127.0.0.1:5000/route/v1/car/-3.7038,40.4168;-3.6883,40.4178?overview=false",
    )
    osrm_shortest = os.environ.get(
        "MONITOR_OSRM_SHORTEST_URL",
        "http://127.0.0.1:5001/route/v1/shortest/-3.7038,40.4168;-3.6883,40.4178?overview=false",
    )
    nominatim_url = os.environ.get("MONITOR_NOMINATIM_URL", "").strip()
    data_path = os.environ.get(
        "ELECTROLINERAS_DATA",
        "/mnt/datos/docker/volumes/electrolineras-data",
    )
    backup_root = os.environ.get(
        "BACKUP_ROOT",
        "/mnt/datos/docker/backups/electrolineras",
    )
    disk_warn = _env_int("MONITOR_DISK_WARN_PCT", 85)

    for check_id, url in (
        ("api", api_url),
        ("osrm_car", osrm_car),
        ("osrm_shortest", osrm_shortest),
    ):
        err = check_http(check_id, url, timeout)
        if err:
            failures.append((check_id, err))

    if nominatim_url:
        err = check_http("nominatim", nominatim_url, timeout)
        if err:
            failures.append(("nominatim", err))

    for check_id, path in (
        ("disk_data", data_path),
        ("disk_backup", backup_root),
    ):
        err = check_disk(path, disk_warn)
        if err:
            failures.append((check_id, err))

    db_path = database_path_from_url(os.environ.get("DATABASE_URL"))
    for idx, err in enumerate(check_database(db_path)):
        failures.append((f"db_{idx}", err))

    return failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Health checks Electrolineras (#6045)")
    parser.add_argument(
        "--notify",
        action="store_true",
        help="Enviar alertas con cooldown vía INGEST_WEBHOOK_URL",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida JSON (para logs)",
    )
    args = parser.parse_args(argv)

    failures = run_checks()
    if args.json:
        print(json.dumps({"ok": not failures, "failures": [{"id": i, "message": m} for i, m in failures]}))
    else:
        for check_id, message in failures:
            print(f"FAIL [{check_id}] {message}", file=sys.stderr)

    if not args.notify:
        return 1 if failures else 0

    state_path = Path(
        os.environ.get(
            "MONITOR_STATE_FILE",
            "/mnt/datos/docker/volumes/electrolineras-data/logs/monitor/state.json",
        )
    )
    state = load_state(state_path)
    cooldown = _env_int("MONITOR_ALERT_COOLDOWN_MINUTES", 180)
    summary = "; ".join(message for _, message in failures) if failures else "ok"
    failed = bool(failures)
    if failed and should_alert(state, "health_summary", True, cooldown):
        notify_script = REPO_ROOT / "scripts" / "cron" / "notify_ingest_failure.sh"
        if notify_script.exists():
            import subprocess

            subprocess.run(
                ["bash", str(notify_script), "monitor", summary[:900]],
                check=False,
                env=os.environ.copy(),
            )
    if not failed:
        should_alert(state, "health_summary", False, cooldown)
    save_state(state_path, state)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
