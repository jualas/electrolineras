#!/usr/bin/env python3
"""Actualiza variables PRIVATE_/SESSION_ en .env de docker-compose sin pegar a mano."""

from __future__ import annotations

import re
import sys
from pathlib import Path

AUTH_KEYS = frozenset(
    {
        "PRIVATE_STACK_ENABLED",
        "CHARGING_AGENT_ENABLED",
        "SESSION_SECRET",
        "SESSION_COOKIE_SECURE",
        "PRIVATE_AUTH_USERS",
        "PRIVATE_AUTH_USERNAME",
        "PRIVATE_AUTH_PASSWORD_HASH",
        "PRIVATE_TOTP_SECRET",
        "PRIVATE_API_TOKEN",
    }
)

# Comentarios sueltos que a veces se pegan tras ejecutar setup_private_auth.py
_AUTH_COMMENT_MARKERS = (
    "Microsoft Authenticator",
    "Clave manual:",
    "URI otpauth:",
    "QR escaneable:",
    "Opcional automatización",
)


def _is_auth_setup_comment(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("#"):
        return False
    return any(marker in stripped for marker in _AUTH_COMMENT_MARKERS)


def parse_auth_users(raw: str) -> list[tuple[str, str]]:
    """Parsea "usuario1:SECRETO1,usuario2:SECRETO2" -> [(usuario1, SECRETO1), ...]."""
    pairs: list[tuple[str, str]] = []
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if not chunk or ":" not in chunk:
            continue
        username, secret = chunk.split(":", 1)
        username = username.strip()
        secret = secret.strip()
        if username and secret:
            pairs.append((username, secret))
    return pairs


def serialize_auth_users(pairs: list[tuple[str, str]]) -> str:
    return ",".join(f"{username}:{secret}" for username, secret in pairs)


def read_env_value(env_path: Path, key: str) -> str | None:
    if not env_path.is_file():
        return None
    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        found_key, value = line.split("=", 1)
        if found_key.strip() == key:
            return value.strip()
    return None


def apply_auth_to_env(env_path: Path, values: dict[str, str]) -> None:
    """Sustituye o añade claves de auth; elimina comentarios huérfanos del setup."""
    if not env_path.is_file():
        raise FileNotFoundError(env_path)

    lines = env_path.read_text().splitlines()
    seen: set[str] = set()
    out: list[str] = []

    for line in lines:
        if _is_auth_setup_comment(line):
            continue

        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in line:
            key, raw_val = line.split("=", 1)
            if key in AUTH_KEYS:
                if key in values:
                    if key in seen:
                        continue
                    out.append(f"{key}={values[key]}")
                    seen.add(key)
                    continue
                if key in seen:
                    continue
                # Mantener valor existente pero quitar comentario inline accidental
                val = raw_val.split("#", 1)[0].rstrip()
                if not re.fullmatch(r"[A-Za-z0-9+/=_$,:-]+", val) and key in (
                    "PRIVATE_TOTP_SECRET",
                    "PRIVATE_AUTH_USERS",
                ):
                    continue
                out.append(f"{key}={val}")
                seen.add(key)
                continue

        out.append(line)

    for key in AUTH_KEYS:
        if key in values and key not in seen:
            out.append(f"{key}={values[key]}")

    env_path.write_text("\n".join(out).rstrip() + "\n")


def main() -> None:
    print("Usa setup_private_auth.py --apply", file=sys.stderr)
    sys.exit(1)


if __name__ == "__main__":
    main()
