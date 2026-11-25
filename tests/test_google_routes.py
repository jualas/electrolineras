from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from api.config import settings
from api.routing.google_routes import (
    clear_google_routes_cache,
    decode_google_polyline,
    fetch_google_route_with_alternatives,
    parse_google_duration_seconds,
)
from api.routing.osrm import RoutingError
from api.routing.provider import fetch_route_with_alternatives, resolved_routing_provider


def _encode_polyline(coords_lat_lon: list[tuple[float, float]]) -> str:
    """Codificador simple de Google Polyline (solo para fixtures de tests)."""

    def _encode_value(value: int) -> str:
        value = ~(value << 1) if value < 0 else (value << 1)
        chunks: list[str] = []
        while value >= 0x20:
            chunks.append(chr((0x20 | (value & 0x1F)) + 63))
            value >>= 5
        chunks.append(chr(value + 63))
        return "".join(chunks)

    out: list[str] = []
    prev_lat = 0
    prev_lon = 0
    for lat, lon in coords_lat_lon:
        ilat = round(lat * 1e5)
        ilon = round(lon * 1e5)
        out.append(_encode_value(ilat - prev_lat))
        out.append(_encode_value(ilon - prev_lon))
        prev_lat = ilat
        prev_lon = ilon
    return "".join(out)


def _mock_response(status_code: int, payload: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = payload
    resp.text = str(payload)
    return resp


def test_decode_google_polyline_roundtrip() -> None:
    points_lat_lon = [(37.1773, -3.5986), (37.4012, -2.5103), (37.6057, -0.9913)]
    encoded = _encode_polyline(points_lat_lon)
    decoded = decode_google_polyline(encoded)
    assert len(decoded) == 3
    # Formato interno es (lon, lat)
    for (lon, lat), (exp_lat, exp_lon) in zip(decoded, points_lat_lon, strict=True):
        assert abs(lat - exp_lat) < 1e-4
        assert abs(lon - exp_lon) < 1e-4


def test_parse_google_duration_seconds() -> None:
    assert parse_google_duration_seconds("3600s") == 3600.0
    assert parse_google_duration_seconds("1845.5s") == 1845.5
    assert parse_google_duration_seconds(1200) == 1200.0
    assert parse_google_duration_seconds("invalid") == 0.0


def test_fetch_google_routes_returns_all_four_variants_and_caches() -> None:
    clear_google_routes_cache()
    poly_fast = _encode_polyline([(37.18, -3.60), (37.60, -0.99)])
    poly_short = _encode_polyline([(37.18, -3.60), (37.35, -2.10), (37.60, -0.99)])
    poly_eco = _encode_polyline([(37.18, -3.60), (37.42, -2.25), (37.60, -0.99)])
    poly_conv = _encode_polyline([(37.18, -3.60), (37.50, -2.00), (37.60, -0.99)])

    calls: list[dict] = []

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float):
        assert headers["X-Goog-Api-Key"] == "test-key"
        assert "routes.polyline.encodedPolyline" in headers["X-Goog-FieldMask"]
        calls.append(json)
        if json["routeModifiers"]["avoidHighways"]:
            return _mock_response(
                200,
                {
                    "routes": [
                        {
                            "distanceMeters": 310_000,
                            "duration": "14400s",
                            "routeLabels": ["DEFAULT_ROUTE"],
                            "polyline": {"encodedPolyline": poly_conv},
                        }
                    ]
                },
            )
        assert json["requestedReferenceRoutes"] == ["SHORTER_DISTANCE", "FUEL_EFFICIENT"]
        assert json["routeModifiers"]["vehicleInfo"]["emissionType"] == "ELECTRIC"
        return _mock_response(
            200,
            {
                "routes": [
                    {
                        "distanceMeters": 285_000,
                        "duration": "10200s",
                        "routeLabels": ["DEFAULT_ROUTE"],
                        "polyline": {"encodedPolyline": poly_fast},
                    },
                    {
                        "distanceMeters": 268_000,
                        "duration": "11400s",
                        "routeLabels": ["SHORTER_DISTANCE"],
                        "polyline": {"encodedPolyline": poly_short},
                    },
                    {
                        "distanceMeters": 274_000,
                        "duration": "10800s",
                        "routeLabels": ["FUEL_EFFICIENT"],
                        "polyline": {"encodedPolyline": poly_eco},
                    },
                ]
            },
        )

    with patch("api.routing.google_routes.httpx.post", side_effect=fake_post):
        route, summary, warnings, variant_routes = fetch_google_route_with_alternatives(
            37.18,
            -3.60,
            37.60,
            -0.99,
            api_key="test-key",
            route_preference="eco",
            avoid_highways=True,
        )
        assert len(calls) == 2
        assert route.route_preference == "eco"
        assert route.distance_m == 274_000
        assert summary.fastest_distance_km == 285.0
        assert summary.shortest_distance_km == 268.0
        assert summary.eco_distance_km == 274.0
        assert summary.eco_duration_minutes == 180.0
        assert summary.conventional_distance_km == 310.0
        assert set(variant_routes.keys()) == {"fastest", "shortest", "eco", "conventional"}
        assert warnings == []

        # Segunda llamada cambiando a shortest usa la caché en memoria (0 llamadas HTTP extra)
        route_short, _sum2, _w2, _v2 = fetch_google_route_with_alternatives(
            37.18,
            -3.60,
            37.60,
            -0.99,
            api_key="test-key",
            route_preference="shortest",
            avoid_highways=True,
        )
        assert len(calls) == 2
        assert route_short.distance_m == 268_000


def test_fetch_google_routes_with_waypoints_omits_shorter_distance_reference() -> None:
    clear_google_routes_cache()
    poly_a = _encode_polyline([(37.18, -3.60), (37.40, -2.50), (37.60, -0.99)])
    poly_b = _encode_polyline([(37.18, -3.60), (37.38, -2.45), (37.60, -0.99)])

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float):
        if json["routeModifiers"]["avoidHighways"]:
            return _mock_response(
                200,
                {
                    "routes": [
                        {
                            "distanceMeters": 330_000,
                            "duration": "15000s",
                            "routeLabels": ["DEFAULT_ROUTE"],
                            "polyline": {"encodedPolyline": poly_a},
                        }
                    ]
                },
            )
        assert "SHORTER_DISTANCE" not in json.get("requestedReferenceRoutes", [])
        assert json.get("computeAlternativeRoutes") is True
        assert len(json["intermediates"]) == 1
        return _mock_response(
            200,
            {
                "routes": [
                    {
                        "distanceMeters": 300_000,
                        "duration": "10800s",
                        "routeLabels": ["DEFAULT_ROUTE"],
                        "polyline": {"encodedPolyline": poly_a},
                    },
                    {
                        "distanceMeters": 288_000,
                        "duration": "11700s",
                        "routeLabels": ["DEFAULT_ROUTE_ALTERNATE"],
                        "polyline": {"encodedPolyline": poly_b},
                    },
                ]
            },
        )

    with patch("api.routing.google_routes.httpx.post", side_effect=fake_post):
        route, summary, warnings, _variants = fetch_google_route_with_alternatives(
            37.18,
            -3.60,
            37.60,
            -0.99,
            api_key="test-key",
            route_preference="shortest",
            waypoints=[(37.40, -2.50)],
        )
    assert route.distance_m == 288_000
    assert summary.shortest_distance_km == 288.0
    assert summary.variants_approximate is True
    assert any("SHORTER_DISTANCE" in w for w in warnings)


def test_fetch_google_routes_retries_without_reference_routes_on_400() -> None:
    clear_google_routes_cache()
    poly = _encode_polyline([(37.18, -3.60), (37.60, -0.99)])
    primary_attempts = 0

    def fake_post(url: str, *, json: dict, headers: dict, timeout: float):
        nonlocal primary_attempts
        if json["routeModifiers"]["avoidHighways"]:
            return _mock_response(
                200,
                {
                    "routes": [
                        {
                            "distanceMeters": 310_000,
                            "duration": "14400s",
                            "routeLabels": ["DEFAULT_ROUTE"],
                            "polyline": {"encodedPolyline": poly},
                        }
                    ]
                },
            )
        primary_attempts += 1
        if primary_attempts == 1:
            return _mock_response(400, {"error": {"message": "reference routes unsupported"}})
        return _mock_response(
            200,
            {
                "routes": [
                    {
                        "distanceMeters": 280_000,
                        "duration": "10200s",
                        "routeLabels": ["DEFAULT_ROUTE"],
                        "polyline": {"encodedPolyline": poly},
                    }
                ]
            },
        )

    with patch("api.routing.google_routes.httpx.post", side_effect=fake_post):
        route, _summary, warnings, _variants = fetch_google_route_with_alternatives(
            37.18,
            -3.60,
            37.60,
            -0.99,
            api_key="test-key",
            route_preference="eco",
        )
    assert primary_attempts == 2
    assert route.distance_m == 280_000
    assert any("eco eléctrica no disponible" in w for w in warnings)


def test_fetch_google_routes_missing_key_raises() -> None:
    with pytest.raises(RoutingError, match="GOOGLE_MAPS_API_KEY"):
        fetch_google_route_with_alternatives(
            37.18,
            -3.60,
            37.60,
            -0.99,
            api_key="",
        )


def test_provider_resolution_and_dispatch() -> None:
    orig_provider = settings.routing_provider
    orig_key = settings.google_maps_api_key
    try:
        settings.routing_provider = "osrm"
        settings.google_maps_api_key = "key"
        assert resolved_routing_provider() == "osrm"

        settings.routing_provider = "auto"
        assert resolved_routing_provider() == "google"

        settings.google_maps_api_key = ""
        assert resolved_routing_provider() == "osrm"

        settings.routing_provider = "google"
        assert resolved_routing_provider() == "google"

        with patch("api.routing.provider.fetch_google_route_with_alternatives") as mock_google:
            mock_google.return_value = ("route", "summary", [], {})
            result = fetch_route_with_alternatives(37.18, -3.60, 37.60, -0.99)
            assert result[0] == "route"
            mock_google.assert_called_once()
    finally:
        settings.routing_provider = orig_provider
        settings.google_maps_api_key = orig_key
