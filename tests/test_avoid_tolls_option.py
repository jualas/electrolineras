"""Opción explícita de peajes (avoid_highways) — #6150.

Cuando el usuario marca «Permitir autopistas de peaje», el cliente envía
`avoid_highways=false` y el backend NO debe aplicar `exclude=toll`.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_repository
from api.main import app
from api.routing.osrm import OsrmRoute, RouteAlternativesSummary, build_osrm_exclude_param
from test_api_charging_plan import memory_repo, sample_station


SHORT_ROUTE = OsrmRoute(
    coordinates=[(2.17, 41.39), (-0.38, 39.47)],
    distance_m=350_000.0,
    duration_s=12_000.0,
    route_preference="fastest",
    avoid_highways=False,
)

SHORT_ALTERNATIVES = RouteAlternativesSummary(
    geodesic_distance_km=300.0,
    shortest_distance_km=340.0,
    shortest_duration_minutes=220.0,
    fastest_distance_km=350.0,
    fastest_duration_minutes=200.0,
    conventional_distance_km=380.0,
    conventional_duration_minutes=280.0,
    shortest_excess_km=40.0,
    conventional_excess_km=80.0,
    variants_approximate=False,
)

MOCK_OSRM = (SHORT_ROUTE, SHORT_ALTERNATIVES, [], {"fastest": SHORT_ROUTE})


def test_exclude_param_allows_tolls_when_explicitly_disabled() -> None:
    assert build_osrm_exclude_param("fastest", False) is None
    assert build_osrm_exclude_param("shortest", False) is None
    assert build_osrm_exclude_param("fastest", True) == "toll"
    assert build_osrm_exclude_param("shortest", True) == "toll"


def test_multi_profile_allow_tolls_does_not_pass_exclude_toll() -> None:
    from api.config import settings
    from api.routing.osrm import _fetch_multi_profile_variants

    calls: list[tuple[str, str | None]] = []

    def fake_request(
        *_args: object,
        profile: str,
        exclude: str | None = None,
        **_kwargs: object,
    ) -> list[dict[str, float]]:
        calls.append((profile, exclude))
        if profile == settings.osrm_profile_shortest:
            return [{"distance": 298_000, "duration": 22_800}]
        if exclude == "motorway":
            return [{"distance": 354_000, "duration": 20_200}]
        return [{"distance": 348_000, "duration": 15_100}]

    original = settings.osrm_use_multi_profile
    settings.osrm_use_multi_profile = True
    try:
        with patch("api.routing.osrm._request_osrm_profile_route", side_effect=fake_request):
            _fetch_multi_profile_variants(
                41.39,
                2.17,
                39.47,
                -0.38,
                base_url="http://osrm-car",
                timeout_s=5.0,
                avoid_highways=False,
            )
    finally:
        settings.osrm_use_multi_profile = original

    assert all(excl != "toll" for _prof, excl in calls)
    assert any(excl is None for _prof, excl in calls)


@pytest.fixture
def toll_api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station("a1", 41.2, 1.5, kw=150.0, price=0.40),
            sample_station("a2", 40.5, 0.5, kw=150.0, price=0.40),
            sample_station("a3", 39.8, -0.1, kw=150.0, price=0.40),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_charging_plan_echoes_avoid_highways_false(mock_fetch, toll_api_client: TestClient) -> None:
    response = toll_api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 41.387,
            "origin_lon": 2.170,
            "dest_lat": 39.470,
            "dest_lon": -0.376,
            "soc_percent": 80,
            "usable_capacity_kwh": 60,
            "consumption_wh_per_km": 170,
            "terrain_factor": 1,
            "route_preference": "fastest",
            "avoid_highways": "false",
            "min_kw": 100,
            "include_route": "true",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["avoid_highways"] is False
    # El mock debe recibir avoid_highways=False (peajes permitidos).
    assert mock_fetch.call_args.kwargs.get("avoid_highways") is False


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MOCK_OSRM)
def test_charging_plan_echoes_avoid_highways_true(mock_fetch, toll_api_client: TestClient) -> None:
    response = toll_api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 41.387,
            "origin_lon": 2.170,
            "dest_lat": 39.470,
            "dest_lon": -0.376,
            "soc_percent": 80,
            "usable_capacity_kwh": 60,
            "consumption_wh_per_km": 170,
            "terrain_factor": 1,
            "route_preference": "fastest",
            "avoid_highways": "true",
            "min_kw": 100,
            "include_route": "true",
        },
    )
    assert response.status_code == 200
    assert response.json()["avoid_highways"] is True
    assert mock_fetch.call_args.kwargs.get("avoid_highways") is True
