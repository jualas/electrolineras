from __future__ import annotations

import pyotp
import pytest
from fastapi.testclient import TestClient

from api.config import settings
from api.main import app


@pytest.fixture
def auth_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def auth_settings():
    original = {
        "enabled": settings.private_stack_enabled,
        "users": settings.private_auth_users,
        "username": settings.private_auth_username,
        "totp": settings.private_totp_secret,
        "secret": settings.session_secret,
        "secure": settings.session_cookie_secure,
    }
    secret = pyotp.random_base32()
    settings.private_stack_enabled = True
    settings.private_auth_users = f"electrolineras:{secret}"
    settings.private_auth_username = ""
    settings.private_totp_secret = ""
    settings.session_secret = "test-session-secret-min-32-characters-long"
    settings.session_cookie_secure = False
    totp = pyotp.TOTP(secret)
    yield {"username": "electrolineras", "totp": totp}
    settings.private_stack_enabled = original["enabled"]
    settings.private_auth_users = original["users"]
    settings.private_auth_username = original["username"]
    settings.private_totp_secret = original["totp"]
    settings.session_secret = original["secret"]
    settings.session_cookie_secure = original["secure"]


@pytest.fixture
def two_user_auth_settings():
    original = {
        "enabled": settings.private_stack_enabled,
        "users": settings.private_auth_users,
        "secret": settings.session_secret,
        "secure": settings.session_cookie_secure,
    }
    secret_a = pyotp.random_base32()
    secret_b = pyotp.random_base32()
    settings.private_stack_enabled = True
    settings.private_auth_users = f"juan:{secret_a},maria:{secret_b}"
    settings.session_secret = "test-session-secret-min-32-characters-long"
    settings.session_cookie_secure = False
    yield {
        "juan": pyotp.TOTP(secret_a),
        "maria": pyotp.TOTP(secret_b),
    }
    settings.private_stack_enabled = original["enabled"]
    settings.private_auth_users = original["users"]
    settings.session_secret = original["secret"]
    settings.session_cookie_secure = original["secure"]


def test_auth_login_and_session(auth_client: TestClient, auth_settings) -> None:
    bad = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "wrong", "totp_code": "000000"},
    )
    assert bad.status_code == 401

    code = auth_settings["totp"].now()
    ok = auth_client.post(
        "/api/v1/auth/login",
        json={"username": auth_settings["username"], "totp_code": code},
    )
    assert ok.status_code == 200
    session = auth_client.get("/api/v1/auth/session").json()
    assert session["authenticated"] is True
    assert session["username"] == "electrolineras"

    protected = auth_client.get("/api/v1/private/status")
    assert protected.status_code == 200

    logout = auth_client.post("/api/v1/auth/logout")
    assert logout.status_code == 200
    assert auth_client.get("/api/v1/auth/session").json()["authenticated"] is False


def test_auth_config_does_not_expose_username(auth_client: TestClient, auth_settings) -> None:
    response = auth_client.get("/api/v1/auth/config")
    assert response.status_code == 200
    assert "login_username" not in response.json()
    assert response.json()["login_enabled"] is True


def test_private_status_requires_auth_when_enabled(auth_client: TestClient, auth_settings) -> None:
    response = auth_client.get("/api/v1/private/status")
    assert response.status_code == 401


def test_multi_user_totp_is_not_interchangeable(auth_client: TestClient, two_user_auth_settings) -> None:
    juan_code = two_user_auth_settings["juan"].now()
    maria_code = two_user_auth_settings["maria"].now()

    cross = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "maria", "totp_code": juan_code},
    )
    assert cross.status_code in (401, 200)
    # El código de juan casi nunca coincide con el de maria (secretos distintos);
    # si por azar coincidiera, TOTP tendría una colisión, así que forzamos el caso normal.
    if juan_code != maria_code:
        assert cross.status_code == 401

    ok_juan = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "juan", "totp_code": juan_code},
    )
    assert ok_juan.status_code == 200
    assert auth_client.get("/api/v1/auth/session").json()["username"] == "juan"
    auth_client.post("/api/v1/auth/logout")

    ok_maria = auth_client.post(
        "/api/v1/auth/login",
        json={"username": "maria", "totp_code": maria_code},
    )
    assert ok_maria.status_code == 200
    assert auth_client.get("/api/v1/auth/session").json()["username"] == "maria"


def test_legacy_single_user_fields_still_work(auth_client: TestClient) -> None:
    original = {
        "enabled": settings.private_stack_enabled,
        "users": settings.private_auth_users,
        "username": settings.private_auth_username,
        "totp": settings.private_totp_secret,
        "secret": settings.session_secret,
    }
    secret = pyotp.random_base32()
    settings.private_stack_enabled = True
    settings.private_auth_users = ""
    settings.private_auth_username = "legacy-user"
    settings.private_totp_secret = secret
    settings.session_secret = "test-session-secret-min-32-characters-long"
    try:
        code = pyotp.TOTP(secret).now()
        ok = auth_client.post(
            "/api/v1/auth/login",
            json={"username": "legacy-user", "totp_code": code},
        )
        assert ok.status_code == 200
    finally:
        settings.private_stack_enabled = original["enabled"]
        settings.private_auth_users = original["users"]
        settings.private_auth_username = original["username"]
        settings.private_totp_secret = original["totp"]
        settings.session_secret = original["secret"]
