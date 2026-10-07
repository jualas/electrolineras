#!/usr/bin/env python3
"""Valida un fichero .env de producción antes de desplegar (#6043)."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REQUIRED_KEYS = (
    "DATABASE_URL",
    "API_CORS_ORIGINS",
    "OSRM_BASE_URL",
    "NOMINATIM_USER_AGENT",
    "API_ENVIRONMENT",
    "API_RELOAD",
)

WARN_IF_EMPTY = (
    "CLOUDFLARED_TOKEN",
    "SESSION_SECRET",
    "PRIVATE_AUTH_PASSWORD_HASH",
    "PRIVATE_TOTP_SECRET",
)

PLACEHOLDER_PATTERNS = (
    re.compile(r"example\.com", re.I),
    re.compile(r"changeme", re.I),
    re.compile(r"your[-_]?", re.I),
    re.compile(r"<[^>]+>"),
    re.compile(r"TODO", re.I),
)


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"Línea {line_no}: sin '='")
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_falsey(value: str) -> bool:
    return value.strip().lower() in {"0", "false", "no", "off", ""}


def looks_like_placeholder(value: str) -> bool:
    return any(pattern.search(value) for pattern in PLACEHOLDER_PATTERNS)


def validate(values: dict[str, str], *, strict_secrets: bool) -> list[str]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_KEYS:
        if key not in values or not values[key]:
            errors.append(f"Falta variable obligatoria: {key}")

    if values.get("API_ENVIRONMENT", "").lower() != "production":
        errors.append("API_ENVIRONMENT debe ser 'production'")

    if values.get("API_RELOAD", "").lower() not in {"false", "0", "no", "off"}:
        errors.append("API_RELOAD debe ser false en producción")

    cors = values.get("API_CORS_ORIGINS", "")
    if "*" in cors:
        errors.append("API_CORS_ORIGINS no debe incluir '*' en producción")

    db_url = values.get("DATABASE_URL", "")
    if db_url and not db_url.startswith("sqlite:"):
        warnings.append(f"DATABASE_URL no es SQLite: {db_url[:40]}…")

    ua = values.get("NOMINATIM_USER_AGENT", "")
    if "contact: local" in ua.lower() or ua.endswith("(dev; contact: local)"):
        errors.append("NOMINATIM_USER_AGENT sigue siendo el valor de desarrollo")

    nominatim_url = values.get("NOMINATIM_BASE_URL", "")
    if values.get("API_ENVIRONMENT", "").lower() == "production":
        if "openstreetmap.org" in nominatim_url.lower():
            errors.append(
                "NOMINATIM_BASE_URL no debe ser el servicio público en producción (#6046)"
            )

    if is_truthy(values.get("PRIVATE_STACK_ENABLED", "false")):
        for key in ("SESSION_SECRET", "PRIVATE_AUTH_PASSWORD_HASH", "PRIVATE_TOTP_SECRET"):
            if not values.get(key):
                errors.append(f"{key} obligatorio con PRIVATE_STACK_ENABLED=true")
        session_secret = values.get("SESSION_SECRET", "")
        if session_secret and len(session_secret) < 32:
            errors.append("SESSION_SECRET demasiado corto (mínimo 32 caracteres)")
        pwd_hash = values.get("PRIVATE_AUTH_PASSWORD_HASH", "")
        if pwd_hash.startswith("$2") and "$$" not in pwd_hash and "\\" not in pwd_hash:
            warnings.append(
                "PRIVATE_AUTH_PASSWORD_HASH: en .env de docker-compose duplica cada $ ($$)"
            )

    for key in WARN_IF_EMPTY:
        if not values.get(key):
            warnings.append(f"{key} vacío (ok si no usas esa integración)")

    if strict_secrets:
        for key, value in values.items():
            if not value:
                continue
            if key.endswith(("_TOKEN", "_SECRET", "_KEY", "_PASSWORD", "_PASSWORD_HASH")):
                if looks_like_placeholder(value):
                    errors.append(f"{key} parece un placeholder, no un secreto real")

    dify_url = values.get("DIFY_API_BASE_URL", "")
    if dify_url and not values.get("DIFY_TRIP_WORKFLOW_API_KEY"):
        warnings.append("DIFY_API_BASE_URL definido pero falta DIFY_TRIP_WORKFLOW_API_KEY")

    return errors + [f"AVISO: {item}" for item in warnings]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Valida .env de producción Electrolineras")
    parser.add_argument(
        "env_file",
        nargs="?",
        default=".env",
        help="Ruta al fichero .env (default: .env)",
    )
    parser.add_argument(
        "--strict-secrets",
        action="store_true",
        help="Fallar si secretos parecen placeholders",
    )
    args = parser.parse_args(argv)

    path = Path(args.env_file)
    if not path.is_file():
        print(f"ERROR: no existe {path}", file=sys.stderr)
        return 1

    try:
        values = parse_env_file(path)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    messages = validate(values, strict_secrets=args.strict_secrets)
    errors = [msg for msg in messages if not msg.startswith("AVISO:")]
    warnings = [msg.removeprefix("AVISO: ") for msg in messages if msg.startswith("AVISO:")]

    for warning in warnings:
        print(f"WARN: {warning}")
    for error in errors:
        print(f"ERROR: {error}", file=sys.stderr)

    if errors:
        print(f"\n{len(errors)} error(es), {len(warnings)} aviso(s).", file=sys.stderr)
        return 1

    print(f"OK: {path} ({len(values)} variables, {len(warnings)} aviso(s))")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
