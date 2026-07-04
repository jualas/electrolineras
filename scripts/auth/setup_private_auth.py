#!/usr/bin/env python3
"""Genera hash de contraseña y secreto TOTP para .env (Microsoft Authenticator)."""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys

try:
    import pyotp
except ImportError:
    print(
        "ERROR: falta pyotp. Usa el venv del proyecto:\n"
        "  ./scripts/auth/setup_private_auth.sh\n"
        "  o: .venv/bin/pip install -e . && PYTHONPATH=src .venv/bin/python scripts/auth/setup_private_auth.py",
        file=sys.stderr,
    )
    sys.exit(1)

from api.auth.password import hash_password


def _escape_docker_compose_env(value: str) -> str:
    """docker-compose .env interpreta $VAR; bcrypt usa $ → duplicar como $$."""
    return value.replace("$", "$$")


def main() -> None:
    parser = argparse.ArgumentParser(description="Configurar auth privada TOTP + contraseña")
    parser.add_argument(
        "--account",
        default="electrolineras",
        help="Nombre mostrado en Authenticator",
    )
    parser.add_argument(
        "--password",
        help="Contraseña (si no se pasa, se pide por terminal)",
    )
    args = parser.parse_args()

    password = args.password or getpass.getpass("Contraseña para zona privada: ")
    if len(password) < 8:
        print("ERROR: usa al menos 8 caracteres", file=sys.stderr)
        sys.exit(1)

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=args.account, issuer_name="Electrolineras")

    session_secret = secrets.token_hex(32)

    print("\n# Añade a /mnt/datos/docker/electrolineras/.env (NO commitear)")
    print("# Si ya existen PRIVATE_* / SESSION_*, sustitúyelas (no duplicar líneas).")
    print("# IMPORTANTE: el hash bcrypt lleva $; en .env de docker-compose duplícalos ($$)\n")
    print("PRIVATE_STACK_ENABLED=true")
    print("CHARGING_AGENT_ENABLED=true")
    print(f"SESSION_SECRET={session_secret}")
    print("SESSION_COOKIE_SECURE=true")
    pwd_hash = hash_password(password)
    print(f"PRIVATE_AUTH_PASSWORD_HASH={_escape_docker_compose_env(pwd_hash)}")
    print(f"PRIVATE_TOTP_SECRET={secret}")
    print("\n# Microsoft Authenticator → Cuenta → Otro → escanear QR o introducir clave:")
    print(f"# Clave manual: {secret}")
    print(f"# URI otpauth: {uri}")
    print("\n# Opcional automatización (Dify / scripts):")
    print(f"PRIVATE_API_TOKEN={secrets.token_hex(32)}")


if __name__ == "__main__":
    main()
