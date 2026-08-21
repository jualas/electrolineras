from __future__ import annotations

import secrets

from api.config import settings


def find_user_secret(username: str) -> str | None:
    """Busca el secreto TOTP del usuario dado (comparación case-insensitive)."""
    normalized = username.strip().lower()
    if not normalized:
        return None
    for candidate_username, secret in settings.auth_users():
        if secrets.compare_digest(candidate_username.strip().lower(), normalized):
            return secret
    return None
