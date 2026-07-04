from __future__ import annotations

import base64

import pytest
from fastapi.testclient import TestClient

from api.config import Settings
from api.main import create_app
from api.security.rate_limit import RateLimitStore


@pytest.fixture
def security_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    test_settings = Settings(
        api_environment="production",
        api_docs_enabled=True,
        api_rate_limit_enabled=True,
        api_rate_limit_window_seconds=60.0,
        api_rate_limit_default_per_minute=120,
        api_rate_limit_api_per_minute=90,
        api_rate_limit_routing_per_minute=2,
        api_rate_limit_geocode_per_minute=45,
        api_rate_limit_auth_per_minute=15,
        api_max_request_body_bytes=1024,
        api_trust_proxy_headers=True,
        api_security_headers_enabled=True,
        serve_web_static=False,
    )
    monkeypatch.setattr("api.main.settings", test_settings)
    return test_settings


@pytest.fixture
def security_client(security_settings: Settings) -> TestClient:
    return TestClient(create_app())


def test_health_exempt_from_rate_limit(security_client: TestClient) -> None:
    for _ in range(5):
        response = security_client.get("/health")
        assert response.status_code == 200


def test_routing_rate_limit_returns_429(security_client: TestClient) -> None:
    path = "/api/v1/stations/along-route"
    params = {
        "origin_lat": 40.4,
        "origin_lon": -3.7,
        "destination_lat": 41.6,
        "destination_lon": -0.9,
    }
    first = security_client.get(path, params=params, headers={"CF-Connecting-IP": "203.0.113.10"})
    second = security_client.get(path, params=params, headers={"CF-Connecting-IP": "203.0.113.10"})
    third = security_client.get(path, params=params, headers={"CF-Connecting-IP": "203.0.113.10"})

    assert first.status_code != 429
    assert second.status_code != 429
    assert third.status_code == 429
    assert third.json()["retry_after_seconds"] >= 1
    assert third.headers["Retry-After"]


def test_max_body_size_rejects_large_payload(security_client: TestClient) -> None:
    response = security_client.post(
        "/api/v1/auth/login",
        content=b"x" * 2048,
        headers={"Content-Type": "application/json", "Content-Length": "2048"},
    )
    assert response.status_code == 413


def test_security_headers_on_api_response(security_client: TestClient) -> None:
    response = security_client.get("/health")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "SAMEORIGIN"
    assert response.headers["Referrer-Policy"] == "strict-origin-when-cross-origin"


def test_docs_disabled_in_production_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    test_settings = Settings(api_environment="production", api_docs_enabled=None, serve_web_static=False)
    monkeypatch.setattr("api.main.settings", test_settings)
    client = TestClient(create_app())
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_docs_basic_auth_protects_openapi(monkeypatch: pytest.MonkeyPatch) -> None:
    test_settings = Settings(
        api_environment="production",
        api_docs_enabled=True,
        api_docs_basic_auth_user="docs-user",
        api_docs_basic_auth_password="docs-pass",
        api_rate_limit_enabled=False,
        serve_web_static=False,
    )
    monkeypatch.setattr("api.main.settings", test_settings)
    client = TestClient(create_app())

    blocked = client.get("/openapi.json")
    assert blocked.status_code == 401

    token = base64.b64encode(b"docs-user:docs-pass").decode("ascii")
    allowed = client.get("/openapi.json", headers={"Authorization": f"Basic {token}"})
    assert allowed.status_code == 200


def test_rate_limit_store_isolated_by_ip() -> None:
    store = RateLimitStore()
    assert store.allow("1.2.3.4:routing", limit=1, window_seconds=60.0)[0] is True
    assert store.allow("1.2.3.4:routing", limit=1, window_seconds=60.0)[0] is False
    assert store.allow("5.6.7.8:routing", limit=1, window_seconds=60.0)[0] is True
