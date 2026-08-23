from __future__ import annotations

import pyotp

# Secreto inválido fijo: se usa para verificar un código igualmente cuando el
# usuario no existe, así el tiempo de respuesta no delata qué usuarios hay.
_DUMMY_SECRET = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def verify_totp_code(secret: str | None, code: str) -> bool:
    normalized = code.strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    totp = pyotp.TOTP(secret or _DUMMY_SECRET)
    result = totp.verify(normalized, valid_window=2)
    return result if secret else False


def build_provisioning_uri(secret: str, account_name: str) -> str:
    if not secret.strip():
        raise ValueError("Secreto TOTP vacío")
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name="Electrolineras")
