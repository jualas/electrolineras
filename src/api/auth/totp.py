from __future__ import annotations

import pyotp

from api.config import settings


def verify_totp_code(code: str) -> bool:
    secret = settings.private_totp_secret.strip()
    if not secret or not code:
        return False
    normalized = code.strip().replace(" ", "")
    if not normalized.isdigit() or len(normalized) != 6:
        return False
    totp = pyotp.TOTP(secret)
    return totp.verify(normalized, valid_window=2)


def build_provisioning_uri(account_name: str = "electrolineras") -> str:
    secret = settings.private_totp_secret.strip()
    if not secret:
        raise ValueError("PRIVATE_TOTP_SECRET no configurado")
    return pyotp.TOTP(secret).provisioning_uri(name=account_name, issuer_name="Electrolineras")
