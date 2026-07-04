from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from api.config import settings
from api.routing.nominatim import GeocodingError, _fetch_nominatim_search, geocode_address
from api.routing.nominatim_cache import geocode_cache


@pytest.fixture(autouse=True)
def reset_cache():
    geocode_cache.reset()
    yield
    geocode_cache.reset()


def test_geocode_address_parses_first_hit():
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = [
        {"lat": "37.1773", "lon": "-3.5986", "display_name": "Granada, España"},
    ]

    with patch("api.routing.nominatim.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.return_value = response
        lat, lon, label = geocode_address("Granada", base_url="http://nominatim.test")

    assert lat == pytest.approx(37.1773)
    assert lon == pytest.approx(-3.5986)
    assert label.startswith("Granada")


def test_cache_avoids_second_http_call():
    response = MagicMock()
    response.status_code = 200
    response.headers = {"content-type": "application/json"}
    response.json.return_value = [
        {"lat": "40.4168", "lon": "-3.7038", "display_name": "Madrid, España"},
    ]

    with patch("api.routing.nominatim.httpx.Client") as client_cls:
        client = client_cls.return_value.__enter__.return_value
        client.get.return_value = response
        first = _fetch_nominatim_search("Madrid", 1, base_url="http://nominatim.test")
        second = _fetch_nominatim_search("Madrid", 1, base_url="http://nominatim.test")

    assert first == second
    assert client.get.call_count == 1


def test_fallback_used_on_primary_503():
    blocked = MagicMock()
    blocked.status_code = 503
    ok = MagicMock()
    ok.status_code = 200
    ok.headers = {"content-type": "application/json"}
    ok.json.return_value = [
        {"lat": "41.3874", "lon": "2.1686", "display_name": "Barcelona, España"},
    ]

    original_primary = settings.nominatim_base_url
    original_fallback = settings.nominatim_fallback_base_url
    settings.nominatim_base_url = "http://primary.test"
    settings.nominatim_fallback_base_url = "http://fallback.test"
    try:
        with patch("api.routing.nominatim.httpx.Client") as client_cls:
            client = client_cls.return_value.__enter__.return_value
            client.get.side_effect = [blocked, ok]
            results = _fetch_nominatim_search("Barcelona", 1)

        assert results[0]["display_name"].startswith("Barcelona")
        assert client.get.call_count == 2
    finally:
        settings.nominatim_base_url = original_primary
        settings.nominatim_fallback_base_url = original_fallback


def test_no_fallback_without_configuration():
    blocked = MagicMock()
    blocked.status_code = 503

    original_fallback = settings.nominatim_fallback_base_url
    settings.nominatim_fallback_base_url = ""
    try:
        with patch("api.routing.nominatim.httpx.Client") as client_cls:
            client_cls.return_value.__enter__.return_value.get.return_value = blocked
            with pytest.raises(GeocodingError) as exc:
                _fetch_nominatim_search("Valencia", 1, base_url="http://primary.test")
        assert exc.value.status_code == 503
    finally:
        settings.nominatim_fallback_base_url = original_fallback


def test_fallback_on_non_json_primary_response():
    html = MagicMock()
    html.status_code = 200
    html.headers = {"content-type": "text/html"}
    html.json.side_effect = ValueError("not json")

    ok = MagicMock()
    ok.status_code = 200
    ok.headers = {"content-type": "application/json"}
    ok.json.return_value = [
        {"lat": "37.1773", "lon": "-3.5986", "display_name": "Granada, España"},
    ]

    original_primary = settings.nominatim_base_url
    original_fallback = settings.nominatim_fallback_base_url
    settings.nominatim_base_url = "http://wrong-service.test"
    settings.nominatim_fallback_base_url = "http://fallback.test"
    try:
        with patch("api.routing.nominatim.httpx.Client") as client_cls:
            client = client_cls.return_value.__enter__.return_value
            client.get.side_effect = [html, ok]
            results = _fetch_nominatim_search("Granada", 1)
        assert results[0]["display_name"].startswith("Granada")
        assert client.get.call_count == 2
    finally:
        settings.nominatim_base_url = original_primary
        settings.nominatim_fallback_base_url = original_fallback

    with patch("api.routing.nominatim.httpx.Client") as client_cls:
        client_cls.return_value.__enter__.return_value.get.side_effect = httpx.TimeoutException(
            "timeout"
        )
        with pytest.raises(GeocodingError, match="tiempo"):
            geocode_address("Sevilla", base_url="http://nominatim.test")
