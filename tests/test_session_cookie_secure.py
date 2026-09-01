from __future__ import annotations

from fastapi import Request

from api.config import settings
from api.security.cookies import session_cookie_secure


def _request(headers: dict[str, str] | None = None) -> Request:
    scope = {
        "type": "http",
        "headers": [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()],
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
        "server": ("testserver", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_session_cookie_secure_respects_setting() -> None:
    original = settings.session_cookie_secure
    settings.session_cookie_secure = True
    try:
        assert session_cookie_secure(_request()) is True
    finally:
        settings.session_cookie_secure = original


def test_session_cookie_secure_https_behind_proxy() -> None:
    original_secure = settings.session_cookie_secure
    original_trust = settings.api_trust_proxy_headers
    settings.session_cookie_secure = False
    settings.api_trust_proxy_headers = True
    try:
        assert session_cookie_secure(_request({"X-Forwarded-Proto": "https"})) is True
        assert session_cookie_secure(_request({"X-Forwarded-Proto": "http"})) is False
        assert session_cookie_secure(_request()) is False
    finally:
        settings.session_cookie_secure = original_secure
        settings.api_trust_proxy_headers = original_trust
