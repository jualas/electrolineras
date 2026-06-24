from __future__ import annotations

from typing import Any

import httpx

from api.config import settings


class RoutingError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class OsrmRoute:
    def __init__(
        self,
        coordinates: list[tuple[float, float]],
        distance_m: float,
        duration_s: float,
    ) -> None:
        self.coordinates = coordinates  # (lon, lat)
        self.distance_m = distance_m
        self.duration_s = duration_s

    @property
    def geojson_geometry(self) -> dict[str, Any]:
        return {
            "type": "LineString",
            "coordinates": [[lon, lat] for lon, lat in self.coordinates],
        }

    @property
    def average_speed_mps(self) -> float:
        if self.duration_s <= 0:
            return 22.0  # ~80 km/h fallback
        return self.distance_m / self.duration_s


def fetch_osrm_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> OsrmRoute:
    url = (base_url or settings.osrm_base_url).rstrip("/")
    path = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    request_url = f"{url}/route/v1/driving/{path}"
    params = {"overview": "full", "geometries": "geojson", "steps": "false"}

    with httpx.Client(timeout=timeout_s or settings.osrm_timeout_seconds) as client:
        response = client.get(request_url, params=params)

    if response.status_code != 200:
        raise RoutingError(
            f"OSRM respondió con HTTP {response.status_code}",
            status_code=response.status_code,
        )

    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("routes"):
        message = payload.get("message", "sin rutas")
        raise RoutingError(f"OSRM no encontró ruta: {message}")

    route = payload["routes"][0]
    geometry = route.get("geometry") or {}
    raw_coords = geometry.get("coordinates") or []
    if len(raw_coords) < 2:
        raise RoutingError("OSRM devolvió una geometría de ruta inválida")

    coordinates = [(float(lon), float(lat)) for lon, lat in raw_coords]
    return OsrmRoute(
        coordinates=coordinates,
        distance_m=float(route.get("distance", 0)),
        duration_s=float(route.get("duration", 0)),
    )
