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


def render_totp_qr(uri: str, output_path: Path, *, module_size: int = 8) -> Path:
    """Genera PNG escaneable con qrencode (debe estar instalado en el sistema)."""
    qrencode = shutil.which("qrencode")
    if not qrencode:
        raise RuntimeError(
            "No se encontró qrencode. Instala el paquete del sistema, p. ej.: sudo apt install qrencode"
        )

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [qrencode, "-o", str(output_path), "-s", str(module_size), uri],
        check=True,
        capture_output=True,
        text=True,
    )
    return output_path
