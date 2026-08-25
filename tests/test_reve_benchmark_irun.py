from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_repository
from api.main import app
from api.routing.charging_plan import VehicleEnergyProfile
from api.routing.osrm import OsrmRoute, RouteAlternativesSummary
from api.routing.trip_metrics import build_route_trip_summary
from test_api_charging_plan import memory_repo, sample_station


IRUN_LONG_ROUTE = OsrmRoute(
    coordinates=[(-0.996, 37.625), (-2.0, 40.0), (-1.79, 43.34)],
    distance_m=834_000.0,
    duration_s=38_400.0,
    route_preference="fastest",
)

IRUN_ALTERNATIVES = RouteAlternativesSummary(
    geodesic_distance_km=780.0,
    shortest_distance_km=834.0,
    shortest_duration_minutes=640.0,
    fastest_distance_km=834.0,
    fastest_duration_minutes=640.0,
    conventional_distance_km=900.0,
    conventional_duration_minutes=700.0,
    shortest_excess_km=54.0,
    conventional_excess_km=66.0,
    variants_approximate=False,
)

IRUN_OSRM = (IRUN_LONG_ROUTE, IRUN_ALTERNATIVES, [], {"fastest": IRUN_LONG_ROUTE})


@pytest.fixture
def irun_api_client() -> TestClient:
    repo = memory_repo()
    # Red más densa en el corredor (target 135 min / min progress 0.90 en fastest)
    # para que el planificador no se quede sin candidatos entre min_leg y alcance SOC.
    repo.upsert_stations(
        [
            sample_station("s1", 38.5, -1.5, kw=200.0, price=0.42),
            sample_station("m1", 39.0, -1.7, kw=200.0, price=0.42),
            sample_station("m2", 39.5, -1.85, kw=200.0, price=0.42),
            sample_station("s2", 40.0, -2.01, kw=250.0, price=0.45),
            sample_station("m3", 40.5, -1.95, kw=200.0, price=0.42),
            sample_station("m4", 41.0, -1.9, kw=200.0, price=0.42),
            sample_station("s3", 41.2, -1.85, kw=200.0, price=0.40),
            sample_station("m5", 41.8, -1.82, kw=200.0, price=0.42),
            sample_station("m6", 42.0, -1.8, kw=200.0, price=0.42),
            sample_station("s4", 42.5, -1.79, kw=300.0, price=0.48),
            sample_station("dest-dc", 43.32, -1.78, kw=150.0, price=0.39),
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=IRUN_OSRM)
def test_charging_plan_preserves_planned_stops_with_destination_stay(
    mock_fetch,
    irun_api_client: TestClient,
) -> None:
    response = irun_api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 37.625,
            "origin_lon": -0.996,
            "dest_lat": 43.34,
            "dest_lon": -1.79,
            "min_kw": 50,
            "corridor_km": 30,
            "soc_percent": 100,
            "usable_capacity_kwh": 60,
            "consumption_wh_per_km": 170,
            "min_destination_soc_pct": 10,
            "min_stop_arrival_soc_pct": 10,
            "max_charge_soc_pct": 80,
            "exclude_slow_chargers": True,
            "route_preference": "fastest",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["destination_stay"] is not None
    assert len(payload["planned_stops"]) >= 1
    assert payload["projected_soc_at_destination_with_plan"] is not None
    summary = payload["route_trip_summary"]
    assert summary is not None
    assert summary["stop_count"] == len(payload["planned_stops"])
    assert summary["total_energy_kwh"] == pytest.approx(141.8, abs=2.0)


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=IRUN_OSRM)
def test_reve_irun_benchmark_tolerance(mock_fetch, irun_api_client: TestClient) -> None:
    """Regresión Cartagena→Irun con parámetros REVE (optimizador global #6087)."""
    response = irun_api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 37.625,
            "origin_lon": -0.996,
            "dest_lat": 43.34,
            "dest_lon": -1.79,
            "min_kw": 50,
            "corridor_km": 30,
            "soc_percent": 100,
            "usable_capacity_kwh": 60,
            "consumption_wh_per_km": 170,
            "consumption_kwh_per_100km": 17,
            "max_charge_power_kw": 100,
            "min_destination_soc_pct": 10,
            "min_stop_arrival_soc_pct": 10,
            "max_charge_soc_pct": 80,
            "exclude_slow_chargers": True,
            "route_preference": "fastest",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    stops = payload["planned_stops"]
    summary = payload["route_trip_summary"]
    assert summary is not None
    assert 2 <= len(stops) <= 5
    kms = [s["distance_from_origin_km"] for s in stops]
    assert all(kms[i] < kms[i + 1] for i in range(len(kms) - 1)), f"km not monotonic: {kms}"
    assert 8 <= payload["projected_soc_at_destination_with_plan"] <= 20
    assert 120 <= summary["total_energy_kwh"] <= 160
    if stops:
        assert stops[0]["distance_from_origin_km"] >= 120
    for stop in stops[:-1]:
        assert stop["soc_departure_pct"] <= 72.0, stop
    assert summary["total_charge_minutes"] <= 100


def test_route_trip_summary_totals() -> None:
    profile = VehicleEnergyProfile(
        soc_percent=100,
        usable_capacity_kwh=60,
        consumption_wh_per_km=170,
    )
    summary = build_route_trip_summary(
        profile=profile,
        planned_stops=[],
        route_distance_km=834.0,
        route_duration_minutes=640.0,
        projected_destination_soc_pct=12.0,
    )
    assert summary is not None
    assert summary.total_energy_kwh == pytest.approx(141.8, abs=0.2)
    assert summary.driving_duration_minutes == 640.0
    assert summary.stop_count == 0
