from __future__ import annotations

import logging
from collections.abc import Sequence

from api.config import settings
from api.routing.google_routes import fetch_google_route_with_alternatives
from api.routing.osrm import (
    LatLon,
    OsrmRoute,
    RouteAlternativesSummary,
    RoutePreference,
    RoutingError,
    fetch_osrm_route_with_alternatives,
)

logger = logging.getLogger(__name__)


def resolved_routing_provider() -> str:
    """Devuelve ``'google'`` o ``'osrm'`` según configuración activa."""
    raw = settings.routing_provider.strip().lower()
    if raw == "google":
        return "google"
    if raw == "auto":
        return "google" if settings.google_maps_api_key.strip() else "osrm"
    return "osrm"


def fetch_route_with_alternatives(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = True,
    waypoints: Sequence[LatLon] | None = None,
) -> tuple[OsrmRoute, RouteAlternativesSummary, list[str], dict[RoutePreference, OsrmRoute]]:
    """Despacha el cálculo de rutas al proveedor configurado (Google Routes API u OSRM)."""
    provider = resolved_routing_provider()
    if provider == "google":
        try:
            return fetch_google_route_with_alternatives(
                origin_lat,
                origin_lon,
                dest_lat,
                dest_lon,
                route_preference=route_preference,
                avoid_highways=avoid_highways,
                waypoints=waypoints,
            )
        except RoutingError as exc:
            if not settings.google_routes_fallback_to_osrm:
                raise
            logger.warning("Google Routes falló (%s); fallback automático a OSRM", exc)
            route, summary, warnings, variant_routes = fetch_osrm_route_with_alternatives(
                origin_lat,
                origin_lon,
                dest_lat,
                dest_lon,
                route_preference=route_preference,
                avoid_highways=avoid_highways,
                waypoints=waypoints,
            )
            return (
                route,
                summary,
                [
                    "Google Routes no respondió temporalmente; calculado con OSRM de respaldo.",
                    *warnings,
                ],
                variant_routes,
            )

    return fetch_osrm_route_with_alternatives(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        waypoints=waypoints,
    )


def fetch_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = True,
    waypoints: Sequence[LatLon] | None = None,
) -> OsrmRoute:
    route, _summary, _warnings, _variant_routes = fetch_route_with_alternatives(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        waypoints=waypoints,
    )
    return route
