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


def create_session_value(username: str) -> str:
    return _serializer().dumps({"private": True, "username": username})


def decode_session(value: str) -> dict | None:
    if not value or not settings.session_secret.strip():
        return None
    try:
        data = _serializer().loads(value, max_age=settings.auth_session_max_age_seconds)
    except (BadSignature, SignatureExpired):
        return None
    if isinstance(data, dict) and data.get("private") is True:
        return data
    return None


def verify_session_value(value: str) -> bool:
    return decode_session(value) is not None
