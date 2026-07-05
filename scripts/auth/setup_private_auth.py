#!/usr/bin/env python3
"""Genera hash de contraseña y secreto TOTP para .env (Microsoft Authenticator)."""

from __future__ import annotations

import argparse
import getpass
import secrets
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

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
from apply_auth_env import apply_auth_to_env
from totp_qr import render_totp_qr


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
    parser.add_argument(
        "--qr-output",
        default="img/totp-setup-qr.png",
        help="Ruta PNG del QR para Microsoft Authenticator (vacío = no generar)",
    )
    parser.add_argument(
        "--apply",
        metavar="ENV_FILE",
        help="Escribe variables en .env (p. ej. /mnt/datos/docker/electrolineras/.env)",
    )
    args = parser.parse_args()

    if not args.password and not sys.stdin.isatty():
        print(
            "ERROR: sin TTY usa --password o --apply con contraseña explícita",
            file=sys.stderr,
        )
        sys.exit(1)

    if args.password:
        password = args.password
    else:
        print(
            "NOTA: esto NO comprueba tu contraseña actual; define una NUEVA para la zona privada.\n"
            "Usa --apply para guardar en .env sin copiar/pegar.\n",
            file=sys.stderr,
        )
        password = getpass.getpass("Contraseña para zona privada: ")
    if len(password) < 8:
        print("ERROR: usa al menos 8 caracteres", file=sys.stderr)
        sys.exit(1)

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=args.account, issuer_name="Electrolineras")

    session_secret = secrets.token_hex(32)
    api_token = secrets.token_hex(32)
    pwd_hash = hash_password(password)

    env_values = {
        "PRIVATE_STACK_ENABLED": "true",
        "CHARGING_AGENT_ENABLED": "true",
        "SESSION_SECRET": session_secret,
        "SESSION_COOKIE_SECURE": "true",
        "PRIVATE_AUTH_PASSWORD_HASH": _escape_docker_compose_env(pwd_hash),
        "PRIVATE_TOTP_SECRET": secret,
        "PRIVATE_API_TOKEN": api_token,
    }

    qr_path: Path | None = None
    if args.qr_output.strip():
        try:
            qr_path = render_totp_qr(uri, Path(args.qr_output))
        except RuntimeError as exc:
            print(f"AVISO: no se pudo generar QR ({exc})", file=sys.stderr)

    if args.apply:
        apply_auth_to_env(Path(args.apply), env_values)
        print(f"Variables de auth escritas en {args.apply}")
        print("Reinicia la API:")
        print("  cd /mnt/datos/docker/electrolineras && docker compose up -d --force-recreate electrolineras-api")
    else:
        print("\n# Copia SOLO las líneas KEY=valor (sin comentarios) a tu .env")
        print("# Mejor: vuelve a ejecutar con --apply /ruta/al/.env\n")
        for key, val in env_values.items():
            print(f"{key}={val}")

    print("\n--- Microsoft Authenticator ---")
    print("1. Borra la entrada antigua de «Electrolineras» en la app.")
    print("2. Agregar cuenta → Otra cuenta → escanear QR o clave manual:")
    print(f"   Clave: {secret}")
    if qr_path:
        print(f"   QR: {qr_path}")
    print("\nContraseña de la web (la que acabas de definir): [la que escribiste]")
    print("Código: el de 6 dígitos que muestra Authenticator (cambia cada 30 s).")


if __name__ == "__main__":
    main()
