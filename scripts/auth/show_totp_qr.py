#!/usr/bin/env python3
"""Genera QR TOTP para Microsoft Authenticator desde el .env de producción."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from totp_qr import build_provisioning_uri, render_totp_qr  # noqa: E402


def load_totp_secret(env_file: Path) -> str:
    if not env_file.is_file():
        raise FileNotFoundError(f"No existe {env_file}")

    for line in env_file.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key == "PRIVATE_TOTP_SECRET":
            secret = value.strip()
            if secret:
                return secret
            break

    raise ValueError(f"PRIVATE_TOTP_SECRET vacío o ausente en {env_file}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Genera PNG con QR otpauth para Microsoft Authenticator",
    )
    parser.add_argument(
        "--env-file",
        default="/mnt/datos/docker/electrolineras/.env",
        help="Ruta al .env con PRIVATE_TOTP_SECRET",
    )
    parser.add_argument(
        "--account",
        default="electrolineras",
        help="Nombre mostrado en Authenticator",
    )
    parser.add_argument(
        "--output",
        default="img/totp-authenticator-qr.png",
        help="Ruta del PNG de salida",
    )
    args = parser.parse_args()

    secret = load_totp_secret(Path(args.env_file))
    uri = build_provisioning_uri(secret, account=args.account)
    output = render_totp_qr(uri, Path(args.output))

    print(f"QR guardado en: {output}")
    print(f"Cuenta Authenticator: {args.account}")
    print("Microsoft Authenticator → Agregar cuenta → Otra cuenta → Escanear código QR")
    print(f"URI (referencia): {uri}")


if __name__ == "__main__":
    main()
