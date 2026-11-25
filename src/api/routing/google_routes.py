from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

import httpx

from api.config import settings
from api.routing.osrm import (
    LatLon,
    OsrmRoute,
    RouteAlternativesSummary,
    RoutePreference,
    RoutingError,
    _excess_km_vs_geodesic,
    geodesic_path_km,
    normalize_waypoints,
)

logger = logging.getLogger(__name__)

_GOOGLE_FIELD_MASK = (
    "routes.distanceMeters,"
    "routes.duration,"
    "routes.routeLabels,"
    "routes.polyline.encodedPolyline"
)

_VALID_ROUTING_PREFERENCES = frozenset(
    {"TRAFFIC_UNAWARE", "TRAFFIC_AWARE", "TRAFFIC_AWARE_OPTIMAL"}
)


@dataclass(frozen=True)
class _GoogleRouteEntry:
    distance_m: float
    duration_s: float
    coordinates: list[tuple[float, float]]
    labels: tuple[str, ...]
    approximate: bool = False


@dataclass(frozen=True)
class _CachedGoogleVariants:
    expires_at: float
    variants: dict[RoutePreference, _GoogleRouteEntry]
    warnings: list[str]


class _GoogleRouteCache:
    """Caché efímera en memoria para evitar llamadas duplicadas al cambiar filtros."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[tuple[Any, ...], _CachedGoogleVariants] = OrderedDict()

    def get(self, key: tuple[Any, ...]) -> _CachedGoogleVariants | None:
        now = time.monotonic()
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return entry

    def set(
        self,
        key: tuple[Any, ...],
        *,
        variants: dict[RoutePreference, _GoogleRouteEntry],
        warnings: list[str],
        ttl_seconds: float,
        max_entries: int,
    ) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            return
        expires_at = time.monotonic() + ttl_seconds
        with self._lock:
            self._items[key] = _CachedGoogleVariants(
                expires_at=expires_at,
                variants=variants,
                warnings=list(warnings),
            )
            self._items.move_to_end(key)
            while len(self._items) > max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_route_cache = _GoogleRouteCache()


def clear_google_routes_cache() -> None:
    """Vacía la caché en memoria (útil para tests)."""
    _route_cache.clear()


def decode_google_polyline(encoded: str) -> list[tuple[float, float]]:
    """Decodifica una polyline de Google (precisión 1e-5) a ``[(lon, lat), ...]``."""
    if not encoded:
        return []
    coords: list[tuple[float, float]] = []
    index = 0
    length = len(encoded)
    lat = 0
    lon = 0

    while index < length:
        shift = 0
        result = 0
        while True:
            if index >= length:
                raise RoutingError("Google Routes devolvió una polyline truncada")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lat = ~(result >> 1) if (result & 1) else (result >> 1)
        lat += delta_lat

        shift = 0
        result = 0
        while True:
            if index >= length:
                raise RoutingError("Google Routes devolvió una polyline truncada")
            byte = ord(encoded[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if byte < 0x20:
                break
        delta_lon = ~(result >> 1) if (result & 1) else (result >> 1)
        lon += delta_lon

        coords.append((lon / 1e5, lat / 1e5))

    return coords


def parse_google_duration_seconds(raw: Any) -> float:
    """Convierte duración Protobuf (p. ej. ``'3612s'`` o ``'3612.5s'``) a segundos."""
    if isinstance(raw, int | float):
        return float(raw)
    if not isinstance(raw, str):
        return 0.0
    text = raw.strip()
    if text.endswith("s"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return 0.0


def _lat_lng_waypoint(lat: float, lon: float) -> dict[str, Any]:
    return {"location": {"latLng": {"latitude": lat, "longitude": lon}}}


def _resolved_routing_preference() -> str:
    raw = settings.google_routes_routing_preference.strip().upper()
    if raw in _VALID_ROUTING_PREFERENCES:
        return raw
    return "TRAFFIC_AWARE_OPTIMAL"


def _build_compute_routes_body(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    waypoints: Sequence[LatLon],
    avoid_tolls: bool,
    avoid_highways_flag: bool,
    routing_preference: str,
    reference_routes: Sequence[str] = (),
    compute_alternatives: bool = False,
    electric_vehicle: bool = False,
) -> dict[str, Any]:
    route_modifiers: dict[str, Any] = {
        "avoidTolls": avoid_tolls,
        "avoidHighways": avoid_highways_flag,
    }
    if electric_vehicle:
        route_modifiers["vehicleInfo"] = {"emissionType": "ELECTRIC"}

    body: dict[str, Any] = {
        "origin": _lat_lng_waypoint(origin_lat, origin_lon),
        "destination": _lat_lng_waypoint(dest_lat, dest_lon),
        "travelMode": "DRIVE",
        "routingPreference": routing_preference,
        "polylineQuality": "OVERVIEW",
        "polylineEncoding": "ENCODED_POLYLINE",
        "routeModifiers": route_modifiers,
    }
    if waypoints:
        body["intermediates"] = [_lat_lng_waypoint(lat, lon) for lat, lon in waypoints]
    if reference_routes:
        body["requestedReferenceRoutes"] = list(reference_routes)
    if compute_alternatives:
        body["computeAlternativeRoutes"] = True
    return body


def _google_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text[:200] or "sin detalle"
    error = payload.get("error")
    if isinstance(error, dict):
        message = error.get("message")
        if isinstance(message, str) and message.strip():
            return message.strip()
    return response.text[:200] or "sin detalle"


def _post_compute_routes(
    body: dict[str, Any],
    *,
    api_key: str,
    base_url: str,
    timeout_s: float,
) -> list[dict[str, Any]]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": _GOOGLE_FIELD_MASK,
    }
    try:
        response = httpx.post(base_url, json=body, headers=headers, timeout=timeout_s)
    except httpx.TimeoutException as exc:
        raise RoutingError(f"Google Routes timeout ({timeout_s}s)") from exc
    except httpx.HTTPError as exc:
        raise RoutingError(f"Error conectando a Google Routes: {exc}") from exc

    if response.status_code != 200:
        detail = _google_error_detail(response)
        raise RoutingError(
            f"Google Routes devolvió HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise RoutingError("Respuesta no JSON de Google Routes") from exc

    routes = data.get("routes") or []
    if not routes:
        raise RoutingError("Google Routes no encontró ruta entre origen y destino")
    return routes


def _parse_google_route_entry(
    raw: dict[str, Any],
    *,
    approximate: bool = False,
) -> _GoogleRouteEntry:
    polyline_obj = raw.get("polyline") or {}
    encoded = polyline_obj.get("encodedPolyline") or ""
    coordinates = decode_google_polyline(encoded)
    if len(coordinates) < 2:
        raise RoutingError("Google Routes devolvió una geometría de ruta inválida")
    distance_m = float(raw.get("distanceMeters", 0) or 0)
    duration_s = parse_google_duration_seconds(raw.get("duration"))
    raw_labels = raw.get("routeLabels") or []
    labels = tuple(str(label) for label in raw_labels if isinstance(label, str))
    return _GoogleRouteEntry(
        distance_m=distance_m,
        duration_s=duration_s,
        coordinates=coordinates,
        labels=labels,
        approximate=approximate,
    )


def _select_primary_variants(
    entries: Sequence[_GoogleRouteEntry],
    *,
    has_waypoints: bool,
) -> tuple[dict[RoutePreference, _GoogleRouteEntry], list[str]]:
    if not entries:
        raise RoutingError("Google Routes no devolvió rutas")

    warnings: list[str] = []
    fastest = next((e for e in entries if "DEFAULT_ROUTE" in e.labels), None)
    if fastest is None:
        fastest = min(entries, key=lambda e: (e.duration_s, e.distance_m))

    shortest = next((e for e in entries if "SHORTER_DISTANCE" in e.labels), None)
    if shortest is None:
        shortest_candidate = min(entries, key=lambda e: (e.distance_m, e.duration_s))
        shortest = _GoogleRouteEntry(
            distance_m=shortest_candidate.distance_m,
            duration_s=shortest_candidate.duration_s,
            coordinates=shortest_candidate.coordinates,
            labels=shortest_candidate.labels,
            approximate=has_waypoints or len(entries) == 1,
        )
        if has_waypoints:
            warnings.append(
                "Ruta más directa calculada entre alternativas (Google no admite SHORTER_DISTANCE con paradas intermedias)."
            )

    eco = next((e for e in entries if "FUEL_EFFICIENT" in e.labels), None)

    variants: dict[RoutePreference, _GoogleRouteEntry] = {
        "fastest": fastest,
        "shortest": shortest,
    }
    if eco is not None:
        variants["eco"] = eco
    return variants, warnings


def _entry_to_osrm_route(
    entry: _GoogleRouteEntry,
    *,
    route_preference: RoutePreference,
    avoid_highways: bool,
) -> OsrmRoute:
    return OsrmRoute(
        coordinates=list(entry.coordinates),
        distance_m=entry.distance_m,
        duration_s=entry.duration_s,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
    )


def _summarize_google_variants(
    variants: dict[RoutePreference, _GoogleRouteEntry],
    *,
    geodesic_km: float,
) -> RouteAlternativesSummary:
    fastest = variants["fastest"]
    shortest = variants["shortest"]
    conventional = variants.get("conventional")
    eco = variants.get("eco")

    f_dist = round(fastest.distance_m / 1000.0, 2)
    f_dur = round(fastest.duration_s / 60.0, 1)
    s_dist = round(shortest.distance_m / 1000.0, 2)
    s_dur = round(shortest.duration_s / 60.0, 1)
    s_excess = _excess_km_vs_geodesic(s_dist, geodesic_km)

    c_dist = round(conventional.distance_m / 1000.0, 2) if conventional else None
    c_dur = round(conventional.duration_s / 60.0, 1) if conventional else None
    c_excess = _excess_km_vs_geodesic(c_dist, geodesic_km) if c_dist is not None else None

    e_dist = round(eco.distance_m / 1000.0, 2) if eco else None
    e_dur = round(eco.duration_s / 60.0, 1) if eco else None

    approximate = any(entry.approximate for entry in variants.values())
    return RouteAlternativesSummary(
        geodesic_distance_km=geodesic_km,
        shortest_distance_km=s_dist,
        shortest_duration_minutes=s_dur,
        fastest_distance_km=f_dist,
        fastest_duration_minutes=f_dur,
        conventional_distance_km=c_dist,
        conventional_duration_minutes=c_dur,
        eco_distance_km=e_dist,
        eco_duration_minutes=e_dur,
        shortest_excess_km=s_excess,
        conventional_excess_km=c_excess,
        variants_approximate=approximate,
    )


def _cache_key(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    waypoints: Sequence[LatLon],
    avoid_highways: bool,
    routing_pref: str,
    enable_eco: bool,
) -> tuple[Any, ...]:
    rounded_wp = tuple((round(lat, 5), round(lon, 5)) for lat, lon in waypoints)
    return (
        round(origin_lat, 5),
        round(origin_lon, 5),
        round(dest_lat, 5),
        round(dest_lon, 5),
        rounded_wp,
        bool(avoid_highways),
        routing_pref,
        bool(enable_eco),
    )


def fetch_google_route_with_alternatives(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_s: float | None = None,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = True,
    waypoints: Sequence[LatLon] | None = None,
) -> tuple[OsrmRoute, RouteAlternativesSummary, list[str], dict[RoutePreference, OsrmRoute]]:
    """Calcula rutas con Google Routes API (``computeRoutes``) y devuelve el mismo contrato que OSRM."""
    resolved_key = (api_key if api_key is not None else settings.google_maps_api_key).strip()
    if not resolved_key:
        raise RoutingError("GOOGLE_MAPS_API_KEY no configurada")

    resolved_url = (base_url or settings.google_routes_base_url).strip()
    resolved_timeout = timeout_s or settings.google_routes_timeout_seconds
    resolved_waypoints = normalize_waypoints(waypoints)
    has_waypoints = bool(resolved_waypoints)
    geodesic_km = geodesic_path_km(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        resolved_waypoints,
    )

    routing_pref = _resolved_routing_preference()
    # FUEL_EFFICIENT requiere TRAFFIC_AWARE_OPTIMAL en Google Routes API.
    use_eco = bool(settings.google_routes_enable_eco and routing_pref == "TRAFFIC_AWARE_OPTIMAL")

    key = _cache_key(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        resolved_waypoints,
        avoid_highways,
        routing_pref,
        use_eco,
    )
    cached = _route_cache.get(key) if settings.google_routes_cache_enabled else None

    if cached is not None:
        variants = dict(cached.variants)
        warnings = list(cached.warnings)
    else:
        warnings = []

        def fetch_primary() -> tuple[dict[RoutePreference, _GoogleRouteEntry], list[str]]:
            ref_routes: list[str] = []
            if not has_waypoints:
                ref_routes.append("SHORTER_DISTANCE")
            if use_eco:
                ref_routes.append("FUEL_EFFICIENT")

            body = _build_compute_routes_body(
                origin_lat,
                origin_lon,
                dest_lat,
                dest_lon,
                waypoints=resolved_waypoints,
                avoid_tolls=avoid_highways,
                avoid_highways_flag=False,
                routing_preference=routing_pref,
                reference_routes=ref_routes,
                compute_alternatives=has_waypoints,
                electric_vehicle=use_eco,
            )
            local_warnings: list[str] = []
            try:
                raw_routes = _post_compute_routes(
                    body,
                    api_key=resolved_key,
                    base_url=resolved_url,
                    timeout_s=resolved_timeout,
                )
            except RoutingError as exc:
                # Si alguna referencia experimental (FUEL_EFFICIENT o SHORTER_DISTANCE)
                # da HTTP 400, reintentamos sin referencias para no bloquear el viaje.
                if exc.status_code == 400 and ref_routes:
                    logger.warning(
                        "Google Routes rechazó requestedReferenceRoutes=%s (%s); reintentando con alternativas",
                        ref_routes,
                        exc,
                    )
                    fallback_body = _build_compute_routes_body(
                        origin_lat,
                        origin_lon,
                        dest_lat,
                        dest_lon,
                        waypoints=resolved_waypoints,
                        avoid_tolls=avoid_highways,
                        avoid_highways_flag=False,
                        routing_preference=routing_pref,
                        reference_routes=(),
                        compute_alternatives=True,
                        electric_vehicle=False,
                    )
                    raw_routes = _post_compute_routes(
                        fallback_body,
                        api_key=resolved_key,
                        base_url=resolved_url,
                        timeout_s=resolved_timeout,
                    )
                    local_warnings.append(
                        "Google Routes no devolvió rutas de referencia para este trayecto; se usan alternativas estándar."
                    )
                else:
                    raise

            entries = [_parse_google_route_entry(raw) for raw in raw_routes]
            parsed_variants, parse_warnings = _select_primary_variants(
                entries,
                has_waypoints=has_waypoints,
            )
            local_warnings.extend(parse_warnings)
            return parsed_variants, local_warnings

        def fetch_conventional() -> tuple[_GoogleRouteEntry | None, list[str]]:
            # Para la variante secundaria usamos TRAFFIC_UNAWARE salvo que el usuario
            # la pida explícitamente: mantiene la llamada en SKU Essentials (10k/mes gratis).
            conv_routing_pref = (
                routing_pref if route_preference == "conventional" else "TRAFFIC_UNAWARE"
            )
            body = _build_compute_routes_body(
                origin_lat,
                origin_lon,
                dest_lat,
                dest_lon,
                waypoints=resolved_waypoints,
                avoid_tolls=avoid_highways,
                avoid_highways_flag=True,
                routing_preference=conv_routing_pref,
            )
            try:
                raw_routes = _post_compute_routes(
                    body,
                    api_key=resolved_key,
                    base_url=resolved_url,
                    timeout_s=resolved_timeout,
                )
            except RoutingError as exc:
                if route_preference == "conventional":
                    raise
                logger.warning("No se pudo obtener variante convencional en Google Routes: %s", exc)
                return None, ["No se pudo calcular la alternativa por carreteras convencionales."]
            return _parse_google_route_entry(raw_routes[0]), []

        with ThreadPoolExecutor(max_workers=2) as executor:
            primary_future = executor.submit(fetch_primary)
            conventional_future = executor.submit(fetch_conventional)
            variants, primary_warnings = primary_future.result()
            conv_entry, conv_warnings = conventional_future.result()

        warnings.extend(primary_warnings)
        warnings.extend(conv_warnings)
        if conv_entry is not None:
            variants["conventional"] = conv_entry

        if settings.google_routes_cache_enabled:
            _route_cache.set(
                key,
                variants=variants,
                warnings=warnings,
                ttl_seconds=settings.google_routes_cache_ttl_seconds,
                max_entries=settings.google_routes_cache_max_entries,
            )

    summary = _summarize_google_variants(variants, geodesic_km=geodesic_km)
    variant_routes: dict[RoutePreference, OsrmRoute] = {
        pref: _entry_to_osrm_route(
            entry,
            route_preference=pref,
            avoid_highways=avoid_highways,
        )
        for pref, entry in variants.items()
    }

    active_pref = route_preference
    if active_pref not in variant_routes:
        if active_pref == "eco":
            warnings.append(
                "Ruta eco eléctrica no disponible para este trayecto; se utiliza la ruta más directa."
            )
            active_pref = "shortest"
        else:
            active_pref = "fastest"

    active_route = variant_routes[active_pref]
    return active_route, summary, warnings, variant_routes


def fetch_google_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    timeout_s: float | None = None,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = True,
    waypoints: Sequence[LatLon] | None = None,
) -> OsrmRoute:
    route, _summary, _warnings, _variant_routes = fetch_google_route_with_alternatives(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        api_key=api_key,
        base_url=base_url,
        timeout_s=timeout_s,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        waypoints=waypoints,
    )
    return route
