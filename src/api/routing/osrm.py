from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from api.config import settings
from db.spatial import haversine_m

RoutePreference = Literal["fastest", "shortest", "conventional"]


class RoutingError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class RouteAlternativesSummary:
    geodesic_distance_km: float
    shortest_distance_km: float
    shortest_duration_minutes: float
    fastest_distance_km: float
    fastest_duration_minutes: float
    conventional_distance_km: float | None = None
    conventional_duration_minutes: float | None = None
    shortest_excess_km: float | None = None
    conventional_excess_km: float | None = None
    variants_approximate: bool = False


class OsrmRoute:
    def __init__(
        self,
        coordinates: list[tuple[float, float]],
        distance_m: float,
        duration_s: float,
        *,
        route_preference: RoutePreference = "fastest",
        avoid_highways: bool = False,
    ) -> None:
        self.coordinates = coordinates  # (lon, lat)
        self.distance_m = distance_m
        self.duration_s = duration_s
        self.route_preference = route_preference
        self.avoid_tolls = avoid_highways
        self.avoid_highways = avoid_highways

    @property
    def geojson_geometry(self) -> dict[str, Any]:
        return {
            "type": "LineString",
            "coordinates": [[lon, lat] for lon, lat in self.coordinates],
        }

    @property
    def average_speed_mps(self) -> float:
        if self.duration_s <= 0:
            return 22.0
        return self.distance_m / self.duration_s


@dataclass(frozen=True)
class _RoutePayload:
    preference: RoutePreference
    route: dict[str, Any]
    approximate: bool = False


def geodesic_distance_km(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
) -> float:
    return round(haversine_m(origin_lat, origin_lon, dest_lat, dest_lon) / 1000.0, 2)


def build_osrm_exclude_param(route_preference: RoutePreference, avoid_highways: bool) -> str | None:
    excludes: list[str] = []
    if route_preference == "conventional" and not settings.osrm_use_multi_profile:
        excludes.append("motorway")
    if avoid_highways:
        excludes.append("toll")
    if not excludes:
        return None
    return ",".join(dict.fromkeys(excludes))


def osrm_exclude_unsupported(response: httpx.Response) -> bool:
    if response.status_code not in {400, 501}:
        return False
    try:
        payload = response.json()
    except Exception:
        return False
    code = str(payload.get("code", ""))
    message = str(payload.get("message", "")).lower()
    return code == "InvalidValue" and "exclude" in message


def routing_warning_exclude_unavailable(
    *,
    route_preference: RoutePreference,
    avoid_highways: bool,
) -> str | None:
    if route_preference == "conventional" and not settings.osrm_use_multi_profile:
        return (
            "Convencionales aproximadas: el OSRM público no excluye autovías. "
            "Activa OSRM propio (perfil conventional) para rutas solo nacionales/locales."
        )
    if avoid_highways:
        return "El servidor OSRM no admite excluir peajes; la ruta puede incluir autopistas de peaje."
    return None


def _excess_km_vs_geodesic(distance_km: float, geodesic_km: float) -> float:
    return round(max(0.0, distance_km - geodesic_km), 2)


def _shortest_directness_score(distance_m: float, geodesic_km: float) -> float:
    distance_km = distance_m / 1000.0
    excess_km = max(0.0, distance_km - geodesic_km)
    penalty = settings.osrm_shortest_directness_penalty
    return distance_km + penalty * excess_km


def select_fastest_route_payload(routes: list[dict[str, Any]]) -> dict[str, Any]:
    """Elige la ruta más rápida; si hay alternativas casi empate, prefiere mayor velocidad media.

    Ventana: duration ≤ min_duration × (1 + OSRM_FASTEST_ALTERNATIVE_TOLERANCE), default 8 %.
    Caso típico ES: Cartagena→Zaragoza — OSRM marca ~3 min menos por N-330/Teruel, pero Google
    (y muchos conductores) van por A-7 + A-23 Mudéjar vía Valencia con tiempos similares.
    """
    if not routes:
        raise RoutingError("OSRM no devolvió rutas")
    if len(routes) == 1:
        return routes[0]
    min_duration = min(float(route.get("duration", 0)) for route in routes)
    tolerance = max(0.0, settings.osrm_fastest_alternative_tolerance)
    max_duration = min_duration * (1.0 + tolerance)
    candidates = [
        route
        for route in routes
        if float(route.get("duration", 0)) <= max_duration + 1e-6
    ]
    if not candidates:
        candidates = routes
    return max(
        candidates,
        key=lambda route: float(route.get("distance", 0)) / max(float(route.get("duration", 1)), 1.0),
    )


def select_osrm_route_payload(
    routes: list[dict[str, Any]],
    *,
    route_preference: RoutePreference,
    exclude_applied: bool = True,
    geodesic_km: float | None = None,
) -> dict[str, Any]:
    if not routes:
        raise RoutingError("OSRM no devolvió rutas")
    geodesic = geodesic_km if geodesic_km is not None else 0.0
    if route_preference == "fastest":
        return select_fastest_route_payload(routes)
    if route_preference == "shortest":
        return min(
            routes,
            key=lambda route: _shortest_directness_score(float(route.get("distance", 0)), geodesic),
        )
    if route_preference == "conventional":
        if exclude_applied:
            return min(routes, key=lambda route: float(route.get("distance", 0)))
        if len(routes) >= 2:
            return max(routes, key=lambda route: float(route.get("distance", 0)))
        return routes[0]
    return min(routes, key=lambda route: float(route.get("distance", 0)))


def _metrics_from_payload(
    route: dict[str, Any],
    *,
    geodesic_km: float,
) -> tuple[float, float, float]:
    distance_km = round(float(route.get("distance", 0)) / 1000.0, 2)
    duration_minutes = round(float(route.get("duration", 0)) / 60.0, 1)
    excess_km = _excess_km_vs_geodesic(distance_km, geodesic_km)
    return distance_km, duration_minutes, excess_km


def summarize_route_variants(
    variants: dict[RoutePreference, _RoutePayload],
    *,
    geodesic_km: float,
) -> RouteAlternativesSummary:
    fastest = variants["fastest"]
    shortest = variants["shortest"]
    conventional = variants["conventional"]
    f_dist, f_dur, _ = _metrics_from_payload(fastest.route, geodesic_km=geodesic_km)
    s_dist, s_dur, s_excess = _metrics_from_payload(shortest.route, geodesic_km=geodesic_km)
    c_dist, c_dur, c_excess = _metrics_from_payload(conventional.route, geodesic_km=geodesic_km)
    approximate = any(item.approximate for item in variants.values())
    return RouteAlternativesSummary(
        geodesic_distance_km=geodesic_km,
        shortest_distance_km=s_dist,
        shortest_duration_minutes=s_dur,
        fastest_distance_km=f_dist,
        fastest_duration_minutes=f_dur,
        conventional_distance_km=c_dist,
        conventional_duration_minutes=c_dur,
        shortest_excess_km=s_excess,
        conventional_excess_km=c_excess,
        variants_approximate=approximate,
    )


def summarize_osrm_alternatives(
    routes: list[dict[str, Any]],
    *,
    geodesic_km: float,
) -> RouteAlternativesSummary:
    fastest_route = select_fastest_route_payload(routes)
    shortest_route = min(
        routes,
        key=lambda route: _shortest_directness_score(float(route.get("distance", 0)), geodesic_km),
    )
    conventional_route = max(routes, key=lambda route: float(route.get("distance", 0)))
    variants = {
        "fastest": _RoutePayload("fastest", fastest_route, approximate=True),
        "shortest": _RoutePayload("shortest", shortest_route, approximate=True),
        "conventional": _RoutePayload("conventional", conventional_route, approximate=True),
    }
    return summarize_route_variants(variants, geodesic_km=geodesic_km)


def osrm_route_from_payload(
    route: dict[str, Any],
    *,
    route_preference: RoutePreference,
    avoid_highways: bool,
) -> OsrmRoute:
    geometry = route.get("geometry") or {}
    raw_coords = geometry.get("coordinates") or []
    if len(raw_coords) < 2:
        raise RoutingError("OSRM devolvió una geometría de ruta inválida")
    coordinates = [(float(lon), float(lat)) for lon, lat in raw_coords]
    return OsrmRoute(
        coordinates=coordinates,
        distance_m=float(route.get("distance", 0)),
        duration_s=float(route.get("duration", 0)),
        route_preference=route_preference,
        avoid_highways=avoid_highways,
    )


def _osrm_http_error_detail(response: httpx.Response) -> str:
    try:
        payload = response.json()
    except Exception:
        return response.text[:200] or "sin detalle"
    message = payload.get("message")
    if isinstance(message, str) and message.strip():
        return message.strip()
    return response.text[:200] or "sin detalle"


def _osrm_alternatives_param(enabled: bool, *, count: int | None = None) -> str:
    if not enabled:
        return "false"
    resolved = count if count is not None else settings.osrm_fastest_alternatives_count
    if resolved <= 0:
        return "false"
    if resolved == 1:
        return "true"
    return str(resolved)


def _request_osrm_profile_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    profile: str,
    base_url: str,
    timeout_s: float,
    exclude: str | None = None,
    alternatives: bool = False,
) -> list[dict[str, Any]]:
    path = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    request_url = f"{base_url.rstrip('/')}/route/v1/{profile}/{path}"
    params: dict[str, str] = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": _osrm_alternatives_param(alternatives),
    }
    if exclude:
        params["exclude"] = exclude

    with httpx.Client(timeout=timeout_s) as client:
        response = client.get(request_url, params=params)

    if response.status_code != 200:
        detail = _osrm_http_error_detail(response)
        raise RoutingError(
            f"OSRM ({profile}) respondió HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("routes"):
        message = payload.get("message", "sin rutas")
        raise RoutingError(f"OSRM ({profile}) no encontró ruta: {message}")

    return payload["routes"]


def _request_osrm_routes(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    base_url: str,
    timeout_s: float,
    profile: str,
    route_preference: RoutePreference,
    avoid_highways: bool,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    path = f"{origin_lon},{origin_lat};{dest_lon},{dest_lat}"
    request_url = f"{base_url.rstrip('/')}/route/v1/{profile}/{path}"
    request_alternatives = (
        route_preference == "fastest" and settings.osrm_fastest_request_alternatives
    )
    params: dict[str, str] = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "false",
        "alternatives": _osrm_alternatives_param(request_alternatives),
    }
    exclude = build_osrm_exclude_param(route_preference, avoid_highways)
    routing_warnings: list[str] = []
    exclude_applied = False
    if exclude:
        params["exclude"] = exclude

    with httpx.Client(timeout=timeout_s) as client:
        response = client.get(request_url, params=params)

    if response.status_code == 200 and exclude:
        exclude_applied = True

    if response.status_code != 200 and exclude:
        if osrm_exclude_unsupported(response):
            warning = routing_warning_exclude_unavailable(
                route_preference=route_preference,
                avoid_highways=avoid_highways,
            )
            if warning:
                routing_warnings.append(warning)
            params.pop("exclude", None)
            exclude_applied = False
            with httpx.Client(timeout=timeout_s) as client:
                response = client.get(request_url, params=params)
        elif route_preference == "conventional":
            raise RoutingError(
                "No se encontró ruta solo por carreteras convencionales.",
                status_code=response.status_code,
            )
        else:
            params.pop("exclude", None)
            with httpx.Client(timeout=timeout_s) as client:
                response = client.get(request_url, params=params)

    if response.status_code != 200:
        detail = _osrm_http_error_detail(response)
        raise RoutingError(
            f"OSRM respondió con HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    payload = response.json()
    if payload.get("code") != "Ok" or not payload.get("routes"):
        message = payload.get("message", "sin rutas")
        raise RoutingError(f"OSRM no encontró ruta: {message}")

    return payload["routes"], routing_warnings, exclude_applied


def _fetch_multi_profile_variants(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    base_url: str,
    timeout_s: float,
    avoid_highways: bool,
) -> tuple[dict[RoutePreference, _RoutePayload], list[str]]:
    profiles = {
        "fastest": (settings.osrm_base_url, settings.osrm_profile_fastest),
        "shortest": (settings.osrm_shortest_url(), settings.osrm_profile_shortest),
        "conventional": (settings.osrm_base_url, settings.osrm_profile_conventional),
    }
    toll_exclude = "toll" if avoid_highways else None
    conv_exclude_parts = ["motorway"]
    if avoid_highways:
        conv_exclude_parts.append("toll")
    conventional_exclude = ",".join(dict.fromkeys(conv_exclude_parts))
    results: dict[RoutePreference, _RoutePayload] = {}
    warnings: list[str] = []

    def fetch_one(preference: RoutePreference, base_url: str, profile: str) -> tuple[RoutePreference, _RoutePayload]:
        exclude = conventional_exclude if preference == "conventional" else toll_exclude
        request_alternatives = preference == "fastest" and settings.osrm_fastest_request_alternatives
        routes = _request_osrm_profile_route(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            profile=profile,
            base_url=base_url,
            timeout_s=timeout_s,
            exclude=exclude,
            alternatives=request_alternatives,
        )
        if preference == "fastest":
            route = select_fastest_route_payload(routes)
        else:
            route = routes[0]
        return preference, _RoutePayload(preference, route, approximate=False)

    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {
            executor.submit(fetch_one, preference, base_url, profile): preference
            for preference, (base_url, profile) in profiles.items()
        }
        for future in as_completed(futures):
            preference, payload = future.result()
            results[preference] = payload

    if avoid_highways and not settings.osrm_use_multi_profile:
        warnings.append(
            "Exclusión de peajes no verificada en OSRM propio; revisa perfil si incluye autopistas de peaje."
        )

    return results, warnings


def _route_payload_from_osrm_routes(
    routes: list[dict[str, Any]],
    *,
    preference: RoutePreference,
    exclude_applied: bool,
    geodesic_km: float,
    approximate: bool,
) -> _RoutePayload:
    selected = select_osrm_route_payload(
        routes,
        route_preference=preference,
        exclude_applied=exclude_applied,
        geodesic_km=geodesic_km,
    )
    return _RoutePayload(preference, selected, approximate=approximate)


def _fetch_fallback_variants(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    base_url: str,
    timeout_s: float,
    profile: str,
    avoid_highways: bool,
    geodesic_km: float,
) -> tuple[dict[RoutePreference, _RoutePayload], list[str], bool]:
    """Rápida/directa y convencional requieren peticiones OSRM distintas.

    Una sola petición con la preferencia del usuario mezclaba exclude=motorway con
    alternativas de autovía y hacía que rápida y convencionales mostraran los mismos km.
    """
    warnings: list[str] = []

    def fetch_highway_variants() -> tuple[dict[RoutePreference, _RoutePayload], list[str]]:
        routes, request_warnings, exclude_applied = _request_osrm_routes(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            base_url=base_url,
            timeout_s=timeout_s,
            profile=profile,
            route_preference="fastest",
            avoid_highways=avoid_highways,
        )
        return {
            "fastest": _route_payload_from_osrm_routes(
                routes,
                preference="fastest",
                exclude_applied=exclude_applied,
                geodesic_km=geodesic_km,
                approximate=False,
            ),
            "shortest": _route_payload_from_osrm_routes(
                routes,
                preference="shortest",
                exclude_applied=exclude_applied,
                geodesic_km=geodesic_km,
                approximate=True,
            ),
        }, request_warnings

    def fetch_conventional_variant() -> tuple[_RoutePayload, list[str], bool]:
        routes, request_warnings, exclude_applied = _request_osrm_routes(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            base_url=base_url,
            timeout_s=timeout_s,
            profile=profile,
            route_preference="conventional",
            avoid_highways=avoid_highways,
        )
        payload = _route_payload_from_osrm_routes(
            routes,
            preference="conventional",
            exclude_applied=exclude_applied,
            geodesic_km=geodesic_km,
            approximate=not exclude_applied,
        )
        return payload, request_warnings, exclude_applied

    with ThreadPoolExecutor(max_workers=2) as executor:
        highway_future = executor.submit(fetch_highway_variants)
        conventional_future = executor.submit(fetch_conventional_variant)
        highway_variants, highway_warnings = highway_future.result()
        conventional_payload, conventional_warnings, exclude_applied = conventional_future.result()

    warnings.extend(highway_warnings)
    warnings.extend(conventional_warnings)
    if not conventional_warnings and conventional_payload.approximate:
        warning = routing_warning_exclude_unavailable(
            route_preference="conventional",
            avoid_highways=avoid_highways,
        )
        if warning:
            warnings.append(warning)

    variants = {**highway_variants, "conventional": conventional_payload}
    return variants, warnings, exclude_applied


def fetch_osrm_route_with_alternatives(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = False,
) -> tuple[OsrmRoute, RouteAlternativesSummary, list[str], dict[RoutePreference, OsrmRoute]]:
    resolved_base = base_url or settings.osrm_base_url
    resolved_timeout = timeout_s or settings.osrm_timeout_seconds
    geodesic_km = geodesic_distance_km(origin_lat, origin_lon, dest_lat, dest_lon)
    warnings: list[str] = []

    if settings.osrm_use_multi_profile:
        try:
            variants, profile_warnings = _fetch_multi_profile_variants(
                origin_lat,
                origin_lon,
                dest_lat,
                dest_lon,
                base_url=resolved_base,
                timeout_s=resolved_timeout,
                avoid_highways=avoid_highways,
            )
            warnings.extend(profile_warnings)
        except RoutingError:
            variants, fallback_warnings, _exclude_applied = _fetch_fallback_variants(
                origin_lat,
                origin_lon,
                dest_lat,
                dest_lon,
                base_url=resolved_base,
                timeout_s=resolved_timeout,
                profile=settings.osrm_profile_fastest,
                avoid_highways=avoid_highways,
                geodesic_km=geodesic_km,
            )
            warnings.extend(fallback_warnings)
            warnings.append(
                "OSRM multi-perfil no disponible; convencionales con petición aparte (exclude=motorway)."
            )
    else:
        variants, fallback_warnings, _exclude_applied = _fetch_fallback_variants(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            base_url=resolved_base,
            timeout_s=resolved_timeout,
            profile=settings.osrm_profile_fastest,
            avoid_highways=avoid_highways,
            geodesic_km=geodesic_km,
        )
        warnings.extend(fallback_warnings)

    summary = summarize_route_variants(variants, geodesic_km=geodesic_km)
    variant_routes: dict[RoutePreference, OsrmRoute] = {}
    for preference, payload in variants.items():
        try:
            variant_routes[preference] = osrm_route_from_payload(
                payload.route,
                route_preference=preference,
                avoid_highways=avoid_highways,
            )
        except RoutingError:
            continue
    active_payload = variants[route_preference].route
    route = osrm_route_from_payload(
        active_payload,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
    )
    return route, summary, warnings, variant_routes


def fetch_osrm_route(
    origin_lat: float,
    origin_lon: float,
    dest_lat: float,
    dest_lon: float,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = False,
) -> OsrmRoute:
    route, _alternatives, _warnings, _variant_routes = fetch_osrm_route_with_alternatives(
        origin_lat,
        origin_lon,
        dest_lat,
        dest_lon,
        base_url=base_url,
        timeout_s=timeout_s,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
    )
    return route
