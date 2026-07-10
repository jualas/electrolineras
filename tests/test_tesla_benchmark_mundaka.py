from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from api.dependencies import get_repository
from api.main import app
from api.routing.charging_plan import HIGH_ARRIVAL_MICRO_STOP_SOC_PCT
from api.routing.osrm import OsrmRoute, RouteAlternativesSummary
from test_api_charging_plan import memory_repo, sample_station

# Cartagena → Mundaka (~868 km, referencia Tesla jul-2026: 3 paradas, ~74 min recarga)
MUNDAKA_ROUTE = OsrmRoute(
    coordinates=[(-0.996, 37.625), (-1.5, 39.0), (-3.0, 41.5), (-2.698, 43.407)],
    distance_m=867_740.0,
    duration_s=34_680.0,
    route_preference="fastest",
)

MUNDAKA_ALTERNATIVES = RouteAlternativesSummary(
    geodesic_distance_km=720.0,
    shortest_distance_km=868.0,
    shortest_duration_minutes=578.0,
    fastest_distance_km=868.0,
    fastest_duration_minutes=578.0,
    conventional_distance_km=900.0,
    conventional_duration_minutes=620.0,
    shortest_excess_km=148.0,
    conventional_excess_km=32.0,
    variants_approximate=False,
)

MUNDAKA_OSRM = (MUNDAKA_ROUTE, MUNDAKA_ALTERNATIVES, [], {"fastest": MUNDAKA_ROUTE})

# Estaciones sobre la polilínea mock (Cartagena → Mundaka) + candidato micro-parada
MUNDAKA_STATION_POSITIONS = [
    ("early-albacete", 38.34, -1.15, 360.0),
    ("atalaya-corridor", 39.00, -1.50, 250.0),
    ("cuenca-corridor", 39.75, -2.00, 300.0),
    ("madrid-corridor", 40.25, -2.25, 400.0),
    ("segovia-corridor", 40.90, -2.70, 350.0),
    ("burgos-corridor", 41.75, -2.95, 350.0),
    ("vitoria-corridor", 42.45, -2.85, 300.0),
    ("dest-dc", 43.25, -2.75, 150.0),
]


@pytest.fixture
def mundaka_api_client() -> TestClient:
    repo = memory_repo()
    repo.upsert_stations(
        [
            sample_station(station_id, lat, lon, kw=kw, price=0.42)
            for station_id, lat, lon, kw in MUNDAKA_STATION_POSITIONS
        ]
    )

    def override_repo():
        yield repo

    app.dependency_overrides[get_repository] = override_repo
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@patch("api.charging_plan_service.fetch_osrm_route_with_alternatives", return_value=MUNDAKA_OSRM)
def test_tesla_mundaka_benchmark_tolerance(mock_fetch, mundaka_api_client: TestClient) -> None:
    """Regresión Cartagena→Mundaka (#6098) vs plan Tesla (3 paradas, sin micro-paradas)."""
    response = mundaka_api_client.get(
        "/api/v1/stations/charging-plan",
        params={
            "origin_lat": 37.625,
            "origin_lon": -0.996,
            "dest_lat": 43.407,
            "dest_lon": -2.698,
            "min_kw": 50,
            "corridor_km": 30,
            "soc_percent": 100,
            "usable_capacity_kwh": 57,
            "consumption_wh_per_km": 136,
            "max_charge_power_kw": 170,
            "min_destination_soc_pct": 10,
            "min_stop_arrival_soc_pct": 10,
            "max_charge_soc_pct": 80,
            "exclude_slow_chargers": True,
            "route_preference": "fastest",
            "vehicle_preset_id": "tesla-model3-sr-2023",
        },
    )
    assert response.status_code == 200
    payload = response.json()
    stops = payload["planned_stops"]
    summary = payload["route_trip_summary"]
    assert summary is not None
    assert 2 <= len(stops) <= 4
    kms = [s["distance_from_origin_km"] for s in stops]
    assert all(kms[i] < kms[i + 1] for i in range(len(kms) - 1)), f"km not monotonic: {kms}"
    assert 8 <= payload["projected_soc_at_destination_with_plan"] <= 20
    if stops:
        assert stops[0]["distance_from_origin_km"] >= 150
    for stop in stops:
        arr = stop["soc_arrival_pct"]
        dep = stop["soc_departure_pct"]
        charge = stop["charge_minutes"]
        assert not (
            arr > HIGH_ARRIVAL_MICRO_STOP_SOC_PCT
            and charge < 12
            and dep - arr < 10
        ), stop
    # Tesla: ~74 min recarga; tolerancia amplia por red multi-operador
    assert summary["total_charge_minutes"] <= 95
    assert summary["total_duration_minutes"] <= 652  # Tesla 580 min + 30 min margen + carga
