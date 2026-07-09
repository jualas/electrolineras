from __future__ import annotations

import secrets

from api.config import settings


def verify_login_username(username: str) -> bool:
    expected = settings.private_auth_username.strip()
    if not expected or not username:
        return False
    return secrets.compare_digest(username.strip().lower(), expected.lower())
