#!/usr/bin/env python3
"""Añade/reemplaza un usuario TOTP (Microsoft Authenticator) en .env. Soporta varios usuarios."""

from __future__ import annotations

import argparse
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

from apply_auth_env import apply_auth_to_env, parse_auth_users, read_env_value, serialize_auth_users
from totp_qr import render_totp_qr


def _list_users(env_file: Path) -> None:
    raw = read_env_value(env_file, "PRIVATE_AUTH_USERS") or ""
    users = parse_auth_users(raw)
    if not users:
        legacy = read_env_value(env_file, "PRIVATE_AUTH_USERNAME")
        if legacy:
            print(f"{legacy}  (formato antiguo, un solo usuario)")
        else:
            print("No hay usuarios configurados.")
        return
    for username, _secret in users:
        print(username)


def main() -> None:
    parser = argparse.ArgumentParser(description="Añadir un usuario a la auth privada: usuario + TOTP")
    parser.add_argument(
        "--username",
        help="Usuario para entrar en la web (requerido salvo con --list)",
    )
    parser.add_argument(
        "--account",
        help="Nombre mostrado en Authenticator (por defecto, el propio --username)",
    )
    parser.add_argument(
        "--qr-output",
        help="Ruta PNG del QR (por defecto img/totp-setup-qr-<usuario>.png; vacío = no generar)",
    )
    parser.add_argument(
        "--apply",
        metavar="ENV_FILE",
        help="Ruta al .env (p. ej. /mnt/datos/docker/electrolineras/.env)",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Si el usuario ya existe, regenera su secreto en vez de fallar",
    )
    parser.add_argument(
        "--print-secrets",
        action="store_true",
        help="Muestra en pantalla los valores secretos (sin --apply, o si no se genera el QR)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Lista los usuarios ya configurados en --apply ENV_FILE y sale",
    )
    args = parser.parse_args()

    if args.list:
        if not args.apply:
            print("ERROR: --list requiere --apply ENV_FILE", file=sys.stderr)
            sys.exit(1)
        _list_users(Path(args.apply))
        return

    if not args.username:
        print("ERROR: falta --username", file=sys.stderr)
        sys.exit(1)

    username = args.username.strip()
    if len(username) < 2:
        print("ERROR: el usuario debe tener al menos 2 caracteres", file=sys.stderr)
        sys.exit(1)
    account = (args.account or username).strip()

    existing_users: list[tuple[str, str]] = []
    if args.apply:
        raw = read_env_value(Path(args.apply), "PRIVATE_AUTH_USERS") or ""
        existing_users = parse_auth_users(raw)
        if any(existing.lower() == username.lower() for existing, _ in existing_users) and not args.replace:
            print(
                f"ERROR: el usuario «{username}» ya existe en {args.apply}. Usa --replace para regenerar su código.",
                file=sys.stderr,
            )
            sys.exit(1)

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=account, issuer_name="Electrolineras")

    updated_users = [(u, s) for u, s in existing_users if u.lower() != username.lower()]
    updated_users.append((username, secret))

    env_values = {
        "PRIVATE_STACK_ENABLED": "true",
        "CHARGING_AGENT_ENABLED": "true",
        "PRIVATE_AUTH_USERS": serialize_auth_users(updated_users),
    }
    # Solo se generan si aún no existen en el .env de destino (no pisar sesiones/tokens de otros usuarios).
    if args.apply:
        if not read_env_value(Path(args.apply), "SESSION_SECRET"):
            env_values["SESSION_SECRET"] = secrets.token_hex(32)
            env_values["SESSION_COOKIE_SECURE"] = "true"
        if not read_env_value(Path(args.apply), "PRIVATE_API_TOKEN"):
            env_values["PRIVATE_API_TOKEN"] = secrets.token_hex(32)
    else:
        env_values["SESSION_SECRET"] = secrets.token_hex(32)
        env_values["SESSION_COOKIE_SECURE"] = "true"
        env_values["PRIVATE_API_TOKEN"] = secrets.token_hex(32)

    qr_output = args.qr_output if args.qr_output is not None else f"img/totp-setup-qr-{username}.png"
    qr_path: Path | None = None
    if qr_output.strip():
        try:
            qr_path = render_totp_qr(uri, Path(qr_output))
        except RuntimeError as exc:
            print(f"AVISO: no se pudo generar QR ({exc})", file=sys.stderr)

    if args.apply:
        apply_auth_to_env(Path(args.apply), env_values)
        print(f"Usuario «{username}» escrito en {args.apply} (usuarios totales: {len(updated_users)})")
        print("Reinicia la API:")
        print("  cd /mnt/datos/docker/electrolineras && docker compose up -d --force-recreate electrolineras-api")
    else:
        print("\n# Copia SOLO las líneas KEY=valor (sin comentarios) a tu .env")
        print("# Mejor: vuelve a ejecutar con --apply /ruta/al/.env\n")
        if args.print_secrets:
            for key, val in env_values.items():
                print(f"{key}={val}")
        else:
            for key in env_values:
                print(f"{key}=<oculto: añade --print-secrets para verlo>")

    print("\n--- Microsoft Authenticator ---")
    print(f"1. Agregar cuenta → Otra cuenta → escanear QR o clave manual (cuenta «{account}»).")
    if args.print_secrets:
        print(f"   Clave: {secret}")
    elif not qr_path:
        print("   Clave: oculta; vuelve a ejecutar con --print-secrets para la clave manual")
    if qr_path:
        print(f"   QR: {qr_path}")
    print(f"\nUsuario web: {username}")
    print("Código: el de 6 dígitos que muestra Authenticator (cambia cada 30 s).")


if __name__ == "__main__":
    main()
