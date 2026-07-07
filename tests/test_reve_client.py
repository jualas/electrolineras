from __future__ import annotations

from ingest.config import IngestSettings
from ingest.reve_client import ReveClient


def test_resolved_reve_base_url_defaults_to_public() -> None:
    settings = IngestSettings(reve_api_key="", reve_base_url="")
    assert settings.resolved_reve_base_url() == "https://www.mapareve.es/api/public/v1"


def test_resolved_reve_base_url_uses_external_when_key_set() -> None:
    settings = IngestSettings(reve_api_key="secret-key", reve_base_url="")
    assert settings.resolved_reve_base_url() == "https://www.mapareve.es/api/external/v1"


def test_resolved_reve_base_url_honors_explicit_override() -> None:
    settings = IngestSettings(
        reve_api_key="secret-key",
        reve_base_url="https://example.test/reve",
    )
    assert settings.resolved_reve_base_url() == "https://example.test/reve"


def test_reve_client_sends_api_key_header(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.reve_client.settings",
        IngestSettings(reve_api_key="test-key-123", reve_base_url=""),
    )
    client = ReveClient()
    assert client.uses_authenticated_api is True
    assert client.base_url == "https://www.mapareve.es/api/external/v1"
    assert client.headers["x-api-key"] == "test-key-123"


def test_fetch_locations_page_external_uses_get_pagination(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.reve_client.settings",
        IngestSettings(reve_api_key="test-key", reve_external_page_limit=100),
    )
    client = ReveClient()
    calls: list[tuple[str, str]] = []

    def fake_request(method: str, path: str, **kwargs: object) -> list[dict[str, str]]:
        del kwargs
        calls.append((method, path))
        if path.endswith("page=1&limit=25"):
            return [{"id": "a"}, {"id": "b"}]
        raise AssertionError(f"unexpected path {path}")

    monkeypatch.setattr(client, "_request", fake_request)
    data, pagination = client.fetch_locations_page(page=1, per_page=25)
    assert len(data) == 2
    assert pagination["next"] is None
    assert calls == [("GET", "/locations?page=1&limit=25")]


def test_reve_client_public_mode_without_key(monkeypatch) -> None:
    monkeypatch.setattr(
        "ingest.reve_client.settings",
        IngestSettings(reve_api_key="", reve_base_url=""),
    )
    client = ReveClient()
    assert client.uses_authenticated_api is False
    assert client.base_url == "https://www.mapareve.es/api/public/v1"
    assert "x-api-key" not in client.headers
