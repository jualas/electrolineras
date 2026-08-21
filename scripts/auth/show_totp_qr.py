#!/usr/bin/env python3
"""Genera QR TOTP para Microsoft Authenticator desde el .env de producción."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from apply_auth_env import parse_auth_users, read_env_value  # noqa: E402
from totp_qr import build_provisioning_uri, render_totp_qr  # noqa: E402


def load_totp_secret(env_file: Path, username: str | None) -> tuple[str, str]:
    """Devuelve (usuario, secreto). Si hay varios usuarios, --username es obligatorio."""
    if not env_file.is_file():
        raise FileNotFoundError(f"No existe {env_file}")

    users = parse_auth_users(read_env_value(env_file, "PRIVATE_AUTH_USERS") or "")
    if not users:
        legacy_username = read_env_value(env_file, "PRIVATE_AUTH_USERNAME")
        legacy_secret = read_env_value(env_file, "PRIVATE_TOTP_SECRET")
        if legacy_username and legacy_secret:
            users = [(legacy_username, legacy_secret)]

    if not users:
        raise ValueError(f"No hay ningún usuario TOTP configurado en {env_file}")

    if username:
        for candidate, secret in users:
            if candidate.lower() == username.strip().lower():
                return candidate, secret
        raise ValueError(f"Usuario «{username}» no encontrado en {env_file}")

    if len(users) > 1:
        nombres = ", ".join(u for u, _ in users)
        raise ValueError(f"Hay varios usuarios configurados ({nombres}); pasa --username")

    return users[0]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera PNG con QR otpauth para Microsoft Authenticator",
    )
    parser.add_argument(
        "--env-file",
        default="/mnt/datos/docker/electrolineras/.env",
        help="Ruta al .env con PRIVATE_AUTH_USERS",
    )
    parser.add_argument(
        "--username",
        help="Usuario cuyo QR regenerar (obligatorio si hay más de uno configurado)",
    )
    parser.add_argument(
        "--account",
        help="Nombre mostrado en Authenticator (por defecto, el propio usuario)",
    )
    parser.add_argument(
        "--output",
        help="Ruta del PNG de salida (por defecto img/totp-authenticator-qr-<usuario>.png)",
    )
    args = parser.parse_args()

    try:
        username, secret = load_totp_secret(Path(args.env_file), args.username)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    account = args.account or username
    output_path = args.output or f"img/totp-authenticator-qr-{username}.png"
    uri = build_provisioning_uri(secret, account=account)
    output = render_totp_qr(uri, Path(output_path))

    print(f"QR guardado en: {output}")
    print(f"Usuario: {username}  |  Cuenta Authenticator: {account}")
    print("Microsoft Authenticator → Agregar cuenta → Otra cuenta → Escanear código QR")
    print(f"URI (referencia): {uri}")


if __name__ == "__main__":
    main()
