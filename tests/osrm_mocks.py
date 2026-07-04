"""Fixtures OSRM compartidos en tests de API."""

from __future__ import annotations

from api.routing.osrm import OsrmRoute, RouteAlternativesSummary

MOCK_ROUTE = OsrmRoute(
    coordinates=[(0.0, 40.0), (0.5, 40.0), (1.0, 40.0)],
    distance_m=111_320.0,
    duration_s=3600.0,
    route_preference="fastest",
)

MOCK_SHORTEST_ROUTE = OsrmRoute(
    coordinates=[(0.0, 40.0), (0.35, 40.0), (1.0, 40.0)],
    distance_m=111_320.0,
    duration_s=3900.0,
    route_preference="shortest",
)

MOCK_FASTEST_ROUTE = OsrmRoute(
    coordinates=[(0.0, 40.0), (0.5, 40.05), (1.0, 40.0)],
    distance_m=115_000.0,
    duration_s=3300.0,
    route_preference="fastest",
)

MOCK_CONVENTIONAL_ROUTE = OsrmRoute(
    coordinates=[(0.0, 40.0), (0.2, 40.02), (0.8, 40.01), (1.0, 40.0)],
    distance_m=125_000.0,
    duration_s=4200.0,
    route_preference="conventional",
)

MOCK_ALTERNATIVES = RouteAlternativesSummary(
    geodesic_distance_km=100.0,
    shortest_distance_km=111.32,
    shortest_duration_minutes=60.0,
    fastest_distance_km=115.0,
    fastest_duration_minutes=55.0,
    conventional_distance_km=125.0,
    conventional_duration_minutes=65.0,
    shortest_excess_km=11.32,
    conventional_excess_km=25.0,
    variants_approximate=True,
)

MOCK_VARIANT_ROUTES = {
    "shortest": MOCK_SHORTEST_ROUTE,
    "fastest": MOCK_FASTEST_ROUTE,
    "conventional": MOCK_CONVENTIONAL_ROUTE,
}

MOCK_OSRM = (MOCK_ROUTE, MOCK_ALTERNATIVES, [], MOCK_VARIANT_ROUTES)
