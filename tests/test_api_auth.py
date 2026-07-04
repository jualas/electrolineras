from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from api.auth.password import hash_password
from api.config import settings
from api.main import app


@pytest.fixture
def auth_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_settings():
    original = {
        "enabled": settings.private_stack_enabled,
        "hash": settings.private_auth_password_hash,
        "totp": settings.private_totp_secret,
        "secret": settings.session_secret,
        "secure": settings.session_cookie_secure,
    }
    secret = pyotp.random_base32()
    settings.private_stack_enabled = True
    settings.private_auth_password_hash = hash_password("test-password-123")
    settings.private_totp_secret = secret
    settings.session_secret = "test-session-secret-min-32-characters-long"
    settings.session_cookie_secure = False
    totp = pyotp.TOTP(secret)
    yield {"password": "test-password-123", "totp": totp}
    for key, value in original.items():
        attr = {
            "enabled": "private_stack_enabled",
            "hash": "private_auth_password_hash",
            "totp": "private_totp_secret",
            "secret": "session_secret",
            "secure": "session_cookie_secure",
        }[key]
        setattr(settings, attr, value)


def test_auth_login_and_session(auth_client: TestClient, auth_settings) -> None:
    bad = auth_client.post(
        "/api/v1/auth/login",
        json={"password": "wrong", "totp_code": "000000"},
    )
    assert bad.status_code == 401

    code = auth_settings["totp"].now()
    ok = auth_client.post(
        "/api/v1/auth/login",
        json={"password": auth_settings["password"], "totp_code": code},
    )
    assert ok.status_code == 200
    assert auth_client.get("/api/v1/auth/session").json()["authenticated"] is True

    protected = auth_client.get("/api/v1/private/status")
    assert protected.status_code == 200

    logout = auth_client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert auth_client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_private_status_requires_auth_when_enabled(auth_client: TestClient, auth_settings) -> None:
    response = auth_client.get("/api/v1/private/status")
    assert response.status_code == 401
