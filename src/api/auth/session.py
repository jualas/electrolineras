from __future__ import annotations

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from api.config import settings

SESSION_COOKIE_NAME = "electrolineras_session"
SESSION_SALT = "electrolineras-private-auth"


def _serializer() -> URLSafeTimedSerializer:
    secret = settings.session_secret.strip()
    if not secret:
        raise ValueError("SESSION_SECRET no configurado")
    return URLSafeTimedSerializer(secret, salt=SESSION_SALT)


def create_session_value() -> str:
    return _serializer().dumps({"private": True})


def verify_session_value(value: str) -> bool:
    if not value or not settings.session_secret.strip():
        return False
    try:
        data = _serializer().loads(value, max_age=settings.auth_session_max_age_seconds)
        return isinstance(data, dict) and data.get("private") is True
    except (BadSignature, SignatureExpired):
        return False
