from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.routing.nominatim import GeocodingError


@pytest.fixture
def api_client() -> TestClient:
    from api.main import app

    return TestClient(app)


@patch(
    "api.routes.stations.search_places",
    return_value=[
        (37.1773, -3.5986, "Granada, Andalucía, España"),
        (37.8882, -4.7794, "Granada, Córdoba, España"),
    ],
)
def test_meta_geocode(mock_search, api_client: TestClient) -> None:
    response = api_client.get("/api/v1/meta/geocode", params={"q": "Granada", "limit": 2})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 2
    assert payload[0]["label"].startswith("Granada")
    assert payload[0]["lat"] == 37.1773
    mock_search.assert_called_once_with("Granada", limit=2)


@patch(
    "api.routes.stations.search_places",
    side_effect=GeocodingError("sin resultados"),
)
def test_meta_geocode_not_found(mock_search, api_client: TestClient) -> None:
    response = api_client.get("/api/v1/meta/geocode", params={"q": "xyzxyz"})
    assert response.status_code == 404
    mock_search.assert_called_once()
