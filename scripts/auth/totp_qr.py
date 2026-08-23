from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pyotp


def build_provisioning_uri(secret: str, account: str = "electrolineras") -> str:
    return pyotp.TOTP(secret.strip()).provisioning_uri(
        name=account,
        issuer_name="Electrolineras",
    )


def render_totp_qr(uri: str, output_path: Path, *, module_size: int = 10) -> Path:
    """Genera PNG escaneable con qrencode (debe estar instalado en el sistema).

    Nivel de corrección de errores alto (-l H) y PNG32 (color de verdad, no
    indexado a 1 bit) para que sobreviva a recompresiones/redimensionados de
    apps de mensajería sin dejar de ser legible por la cámara.
    """
    qrencode = shutil.which("qrencode")
    if not qrencode:
        raise RuntimeError(
            "No se encontró qrencode. Instala el paquete del sistema, p. ej.: sudo apt install qrencode"
        )

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            qrencode,
            "-o", str(output_path),
            "-s", str(module_size),
            "-m", "6",
            "-l", "H",
            "-t", "PNG32",
            uri,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path
