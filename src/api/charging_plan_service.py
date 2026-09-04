from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Literal

from fastapi import HTTPException

from api.config import settings
from api.query_params import parse_country_list
from api.routing.charging_preferences import ChargingPreferences, parse_preferred_operators
from api.routing.charging_plan import (
    VehicleEnergyProfile,
    allows_origin_zone_charging,
    build_emergency_charging_plan,
    build_route_charging_plan,
    estimate_charging_reach_km,
    estimate_range_km,
)
from api.routing.corridor import RoutePolyline, rank_stations_for_charging_plan
from api.routing.destination_stay import analyze_destination_stay, append_destination_strategy
from api.routing.osrm import (
    RoutePreference,
    RoutingError,
    fetch_osrm_route,
    fetch_osrm_route_with_alternatives,
    geodesic_path_km,
    normalize_waypoints,
)
from api.schemas import DestinationStayAdviceResult
from db.repository import StationRepository
from db.spatial import haversine_m
from models.station import Station


@dataclass(frozen=True)
class ChargingPlanBuildResult:
    mode: Literal["route", "emergency"]
    vehicle: VehicleEnergyProfile
    origin_lat: float
    origin_lon: float
    destination_lat: float | None
    destination_lon: float | None
    corridor_km: float | None
    route_distance_km: float | None
    route_duration_minutes: float | None
    route_shortest_distance_km: float | None
    route_fastest_distance_km: float | None
    geodesic_distance_km: float | None
    route_conventional_distance_km: float | None
    route_conventional_duration_minutes: float | None
    shortest_excess_km: float | None
    route_variants_approximate: bool
    route_geometry: dict | None
    preview_route_geometry: dict | None
    route_preference: RoutePreference | None
    avoid_highways: bool
    computation: object
    candidates_in_bbox: int
    destination_stay: DestinationStayAdviceResult | None
    route_shortest_geometry: dict | None = None
    route_fastest_geometry: dict | None = None
    route_conventional_geometry: dict | None = None
    preferred_operators: tuple[str, ...] = ()
    max_price_eur_kwh: float | None = None
    exclude_slow_chargers: bool = False
    route_shortest_duration_minutes: float | None = None
    route_fastest_duration_minutes: float | None = None


def charging_preferences_from_inputs(
    preferred_operators: str | None = None,
    max_price_eur_kwh: float | None = None,
) -> ChargingPreferences:
    return ChargingPreferences(
        preferred_operators=parse_preferred_operators(preferred_operators),
        max_price_eur_kwh=max_price_eur_kwh,
    )


def rank_stations_near_point(
    repo: StationRepository,
    *,
    lat: float,
    lon: float,
    min_kw: float | None,
    max_kw: float | None,
    countries: list[str] | None,
    search_radius_m: float,
) -> list[tuple[Station, float]]:
    lat_pad = search_radius_m / 111_320.0
    cos_lat = max(0.1, abs(math.cos(math.radians(lat))))
    lon_pad = search_radius_m / (111_320.0 * cos_lat)
    candidates = repo.search(
        west=lon - lon_pad,
        south=lat - lat_pad,
        east=lon + lon_pad,
        north=lat + lat_pad,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        limit=10_000,
        offset=0,
    )
    return sorted(
        (
            (
                station,
                haversine_m(lat, lon, station.location.lat, station.location.lon) / 1000.0,
            )
            for station in candidates
        ),
        key=lambda item: item[1],
    )


def vehicle_profile_from_inputs(
    soc_percent: float,
    usable_capacity_kwh: float,
    consumption_wh_per_km: float,
    terrain_factor: float,
    reserve_soc_percent: float,
    vehicle_preset_id: str | None = None,
    *,
    max_charge_power_kw: float = 100.0,
    min_destination_soc_pct: float = 10.0,
    min_stop_arrival_soc_pct: float = 10.0,
    max_charge_soc_pct: float = 80.0,
) -> VehicleEnergyProfile:
    if usable_capacity_kwh <= 0:
        raise HTTPException(status_code=422, detail="usable_capacity_kwh debe ser mayor que 0")
    if consumption_wh_per_km <= 0:
        raise HTTPException(status_code=422, detail="consumption_wh_per_km debe ser mayor que 0")
    if terrain_factor <= 0:
        raise HTTPException(status_code=422, detail="terrain_factor debe ser mayor que 0")
    if max_charge_power_kw <= 0:
        raise HTTPException(status_code=422, detail="max_charge_power_kw debe ser mayor que 0")
    preset_id = vehicle_preset_id.strip() if vehicle_preset_id else None
    if preset_id == "":
        preset_id = None
    return VehicleEnergyProfile(
        soc_percent=soc_percent,
        usable_capacity_kwh=usable_capacity_kwh,
        consumption_wh_per_km=consumption_wh_per_km,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        vehicle_preset_id=preset_id,
        max_charge_power_kw=max_charge_power_kw,
        min_destination_soc_pct=min_destination_soc_pct,
        min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
        max_charge_soc_pct=max_charge_soc_pct,
    )


TRIP_PREFERRED_MIN_KW = 100.0
"""Suelo de viaje (Model 3 / DC rápido): tiempos de carga razonables."""
TRIP_FALLBACK_MIN_KW = 50.0
"""Alternativa si con ≥100 kW el corredor no cierra el plan."""


def resolve_planning_min_kw(
    min_kw: float | None,
    *,
    exclude_slow_chargers: bool,
) -> float | None:
    """REVE/viaje: excluir AC y DC &lt;100 kW del corredor de planificación."""
    slow_floor = TRIP_PREFERRED_MIN_KW if exclude_slow_chargers else 0.0
    if min_kw is None:
        return slow_floor if exclude_slow_chargers else None
    return max(min_kw, slow_floor)


def resolve_fallback_planning_min_kw(
    min_kw: float | None,
    *,
    preferred_min_kw: float | None,
) -> float | None:
    """Si el plan ≥100 queda incompleto, permitir DC ≥50 (salvo min_kw explícito >100)."""
    if preferred_min_kw is None:
        return None
    if preferred_min_kw + 1e-6 < TRIP_PREFERRED_MIN_KW:
        return None
    if preferred_min_kw <= TRIP_FALLBACK_MIN_KW + 1e-6:
        return None
    if min_kw is not None and min_kw > TRIP_PREFERRED_MIN_KW + 1e-6:
        return None
    return TRIP_FALLBACK_MIN_KW


def route_plan_needs_power_fallback(computation: object, vehicle: VehicleEnergyProfile) -> bool:
    """True si con el min_kw actual no hay plan usable hasta el destino."""
    if getattr(computation, "reachable_without_stop", False):
        return False
    projected = getattr(computation, "projected_soc_at_destination_with_plan", None)
    if projected is None:
        return True
    return float(projected) + 1e-6 < float(vehicle.min_destination_soc_pct)


def _route_plan_viability_score(
    computation: object,
    vehicle: VehicleEnergyProfile,
) -> tuple[bool, float, int]:
    """Ordenación: plan completo > mayor SOC proyectado > más paradas útiles."""
    complete = not route_plan_needs_power_fallback(computation, vehicle)
    projected = getattr(computation, "projected_soc_at_destination_with_plan", None)
    projected_v = float(projected) if projected is not None else -1.0
    stops = getattr(computation, "stops", ()) or ()
    return (complete, projected_v, len(stops))


def _build_corridor_route_computation(
    repo: StationRepository,
    *,
    polyline: RoutePolyline,
    osrm_route,
    origin_lat: float,
    origin_lon: float,
    vehicle: VehicleEnergyProfile,
    planning_min_kw: float | None,
    max_kw: float | None,
    countries: list[str] | None,
    corridor_km: float,
    behind_margin_km: float,
    limit: int,
    emergency_radius_km: float,
    range_km: float,
    charging_reach_km: float,
    safe_margin_pct: float,
    adjusted_min_pct: float,
    charging_preferences: ChargingPreferences,
    route_preference: RoutePreference,
) -> tuple[object, int]:
    west, south, east, north = polyline.bbox_expanded(corridor_km * 1000)
    candidates = repo.search(
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=planning_min_kw,
        max_kw=max_kw,
        countries=countries,
        limit=10_000,
        offset=0,
    )

    wrong_side_penalty_m = settings.route_wrong_side_penalty_km_default * 1000
    route_distance_km = osrm_route.distance_m / 1000.0
    corridor_ranking = rank_stations_for_charging_plan(
        polyline,
        candidates,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        corridor_m=corridor_km * 1000,
        behind_margin_m=behind_margin_km * 1000,
        wrong_side_penalty_m=wrong_side_penalty_m,
        average_speed_mps=osrm_route.average_speed_mps,
        route_distance_km=route_distance_km,
        display_limit=limit * 3,
    )
    planning_matches = corridor_ranking.planning
    matches = corridor_ranking.display

    origin_projection = polyline.project_point(origin_lat, origin_lon)
    origin_position_km = origin_projection.route_position_m / 1000.0
    destination_distance_km = polyline.length_m / 1000.0

    origin_search_radius_m = max(emergency_radius_km, charging_reach_km, range_km) * 1000.0
    origin_ranked = rank_stations_near_point(
        repo,
        lat=origin_lat,
        lon=origin_lon,
        min_kw=planning_min_kw,
        max_kw=max_kw,
        countries=countries,
        search_radius_m=origin_search_radius_m,
    )
    origin_stops: list = []
    if allows_origin_zone_charging(vehicle.soc_percent):
        origin_computation = build_emergency_charging_plan(
            origin_ranked,
            profile=vehicle,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
            limit=min(limit, 15),
            preferences=charging_preferences,
        )
        origin_stops = origin_computation.stops

    computation = build_route_charging_plan(
        planning_matches,
        origin_position_km=origin_position_km,
        destination_distance_km=destination_distance_km,
        profile=vehicle,
        origin_stops=origin_stops,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        limit=limit,
        preferences=charging_preferences,
        route_distance_km=route_distance_km,
        route_duration_minutes=osrm_route.duration_s / 60.0,
        corridor_stops=matches,
        route_preference=route_preference,
    )
    return computation, len(candidates)


def resolve_consumption_wh_per_km(
    consumption_wh_per_km: float,
    consumption_kwh_per_100km: float | None,
) -> float:
    if consumption_kwh_per_100km is not None:
        if consumption_kwh_per_100km <= 0:
            raise HTTPException(status_code=422, detail="consumption_kwh_per_100km debe ser mayor que 0")
        return consumption_kwh_per_100km * 10.0
    return consumption_wh_per_km


def _enrich_with_destination_stay(
    repo: StationRepository,
    *,
    dest_lat: float,
    dest_lon: float,
    vehicle: VehicleEnergyProfile,
    destination_radius_km: float,
    local_mobility_km: float,
    countries: list[str] | None,
    computation,
    projected_soc_at_arrival_pct: float | None,
) -> tuple[object, DestinationStayAdviceResult]:
    from api.agent_narration import destination_stay_to_schema

    dest_ranked = rank_stations_near_point(
        repo,
        lat=dest_lat,
        lon=dest_lon,
        min_kw=None,
        max_kw=None,
        countries=countries,
        search_radius_m=destination_radius_km * 1000.0,
    )
    advice = analyze_destination_stay(
        dest_ranked,
        profile=vehicle,
        radius_km=destination_radius_km,
        local_mobility_km=local_mobility_km,
        projected_soc_at_arrival_pct=projected_soc_at_arrival_pct,
    )
    enriched = type(computation)(
        range_km=computation.range_km,
        charging_reach_km=computation.charging_reach_km,
        soc_at_destination_pct=computation.soc_at_destination_pct,
        reachable_without_stop=computation.reachable_without_stop,
        stops=computation.stops,
        origin_stops=computation.origin_stops,
        strategies=append_destination_strategy(computation.strategies, advice),
        warnings=[*computation.warnings, *advice.warnings],
        planned_stops=computation.planned_stops,
        projected_soc_at_destination_with_plan=computation.projected_soc_at_destination_with_plan,
    )
    return enriched, destination_stay_to_schema(advice, dest_ranked)


def build_charging_plan(
    repo: StationRepository,
    *,
    origin_lat: float,
    origin_lon: float,
    soc_percent: float,
    usable_capacity_kwh: float,
    consumption_wh_per_km: float,
    terrain_factor: float = 1.0,
    reserve_soc_percent: float = 10.0,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    dest_lat: float | None = None,
    dest_lon: float | None = None,
    waypoints: list[tuple[float, float]] | None = None,
    min_kw: float | None = 100.0,
    max_kw: float | None = None,
    country: str | None = None,
    corridor_km: float = settings.route_corridor_km_default,
    behind_margin_km: float = settings.route_behind_margin_km_default,
    limit: int = settings.route_results_limit_default,
    include_route: bool = True,
    emergency_radius_km: float = 80.0,
    destination_radius_km: float = 10.0,
    local_mobility_km: float = 40.0,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = True,
    vehicle_preset_id: str | None = None,
    preferred_operators: str | None = None,
    max_price_eur_kwh: float | None = None,
    max_charge_power_kw: float = 100.0,
    min_destination_soc_pct: float = 10.0,
    min_stop_arrival_soc_pct: float = 10.0,
    max_charge_soc_pct: float = 80.0,
    exclude_slow_chargers: bool = False,
    consumption_kwh_per_100km: float | None = None,
) -> ChargingPlanBuildResult:
    if min_kw is not None and max_kw is not None and min_kw > max_kw:
        raise HTTPException(status_code=422, detail="min_kw no puede ser mayor que max_kw")

    has_destination = dest_lat is not None and dest_lon is not None
    if (dest_lat is None) ^ (dest_lon is None):
        raise HTTPException(status_code=422, detail="dest_lat y dest_lon deben enviarse juntos o omitirse")

    resolved_waypoints = normalize_waypoints(waypoints)
    if has_destination and not resolved_waypoints:
        same_point_km = geodesic_path_km(origin_lat, origin_lon, dest_lat, dest_lon)
        if same_point_km < 0.2:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Origen y destino son el mismo punto (ruta 0 km). "
                    "Añade al menos una parada intermedia para un viaje de ida y vuelta."
                ),
            )

    vehicle = vehicle_profile_from_inputs(
        soc_percent,
        usable_capacity_kwh,
        resolve_consumption_wh_per_km(consumption_wh_per_km, consumption_kwh_per_100km),
        terrain_factor,
        reserve_soc_percent,
        vehicle_preset_id,
        max_charge_power_kw=max_charge_power_kw,
        min_destination_soc_pct=min_destination_soc_pct,
        min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
        max_charge_soc_pct=max_charge_soc_pct,
    )
    planning_min_kw = resolve_planning_min_kw(min_kw, exclude_slow_chargers=exclude_slow_chargers)
    countries = parse_country_list(country)
    charging_preferences = charging_preferences_from_inputs(
        preferred_operators,
        max_price_eur_kwh,
    )

    if not has_destination:
        range_km = estimate_range_km(vehicle)
        charging_reach_km = estimate_charging_reach_km(vehicle)
        search_radius_m = max(emergency_radius_km, charging_reach_km, range_km) * 1000.0
        ranked = rank_stations_near_point(
            repo,
            lat=origin_lat,
            lon=origin_lon,
            min_kw=planning_min_kw,
            max_kw=max_kw,
            countries=countries,
            search_radius_m=search_radius_m,
        )
        computation = build_emergency_charging_plan(
            ranked,
            profile=vehicle,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
            limit=limit,
            preferences=charging_preferences,
        )
        preview_route_geometry = None
        route_distance_km = None
        route_duration_minutes = None
        if computation.stops:
            nearest = computation.stops[0]
            try:
                osrm_nearest = fetch_osrm_route(
                    origin_lat,
                    origin_lon,
                    nearest.station.location.lat,
                    nearest.station.location.lon,
                )
                preview_route_geometry = osrm_nearest.geojson_geometry
                route_distance_km = round(osrm_nearest.distance_m / 1000.0, 2)
                route_duration_minutes = round(osrm_nearest.duration_s / 60.0, 1)
            except RoutingError:
                preview_route_geometry = None

        return ChargingPlanBuildResult(
            mode="emergency",
            vehicle=vehicle,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=None,
            destination_lon=None,
            corridor_km=None,
            route_distance_km=route_distance_km,
            route_duration_minutes=route_duration_minutes,
            route_shortest_distance_km=None,
            route_fastest_distance_km=None,
            geodesic_distance_km=None,
            route_conventional_distance_km=None,
            route_conventional_duration_minutes=None,
            shortest_excess_km=None,
            route_variants_approximate=False,
            route_geometry=None,
            preview_route_geometry=preview_route_geometry,
            route_preference=None,
            avoid_highways=avoid_highways,
            exclude_slow_chargers=exclude_slow_chargers,
            computation=computation,
            candidates_in_bbox=len(ranked),
            destination_stay=None,
            preferred_operators=charging_preferences.preferred_operators,
            max_price_eur_kwh=charging_preferences.max_price_eur_kwh,
        )

    try:
        osrm_route, route_alternatives, osrm_warnings, variant_routes = fetch_osrm_route_with_alternatives(
            origin_lat,
            origin_lon,
            dest_lat,
            dest_lon,
            route_preference=route_preference,
            avoid_highways=avoid_highways,
            waypoints=resolved_waypoints,
        )
    except RoutingError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo calcular la ruta: {exc}",
        ) from exc

    polyline = RoutePolyline(osrm_route.coordinates)
    range_km = estimate_range_km(vehicle)
    charging_reach_km = estimate_charging_reach_km(vehicle)

    computation, candidates_count = _build_corridor_route_computation(
        repo,
        polyline=polyline,
        osrm_route=osrm_route,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        vehicle=vehicle,
        planning_min_kw=planning_min_kw,
        max_kw=max_kw,
        countries=countries,
        corridor_km=corridor_km,
        behind_margin_km=behind_margin_km,
        limit=limit,
        emergency_radius_km=emergency_radius_km,
        range_km=range_km,
        charging_reach_km=charging_reach_km,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        charging_preferences=charging_preferences,
        route_preference=route_preference,
    )

    power_fallback_warnings: list[str] = []
    fallback_min_kw = resolve_fallback_planning_min_kw(
        min_kw,
        preferred_min_kw=planning_min_kw,
    )
    if fallback_min_kw is not None and route_plan_needs_power_fallback(computation, vehicle):
        fallback_computation, fallback_candidates = _build_corridor_route_computation(
            repo,
            polyline=polyline,
            osrm_route=osrm_route,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            vehicle=vehicle,
            planning_min_kw=fallback_min_kw,
            max_kw=max_kw,
            countries=countries,
            corridor_km=corridor_km,
            behind_margin_km=behind_margin_km,
            limit=limit,
            emergency_radius_km=emergency_radius_km,
            range_km=range_km,
            charging_reach_km=charging_reach_km,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
            charging_preferences=charging_preferences,
            route_preference=route_preference,
        )
        preferred_score = _route_plan_viability_score(computation, vehicle)
        fallback_score = _route_plan_viability_score(fallback_computation, vehicle)
        power_fallback_warnings.append(
            "No hay suficientes cargadores ≥100 kW en el corredor para cerrar el viaje "
            "con tiempos de carga cortos (Model 3 / DC rápido)."
        )
        if fallback_score > preferred_score:
            computation = fallback_computation
            candidates_count = fallback_candidates
            if route_plan_needs_power_fallback(computation, vehicle):
                power_fallback_warnings.append(
                    "Alternativa con DC ≥50 kW tampoco completa el destino; "
                    "valora parar antes, subir SOC de salida o ampliar el corredor."
                )
            else:
                power_fallback_warnings.append(
                    "Plan alternativo con DC ≥50 kW: puede implicar parar antes de tiempo "
                    "o tramos de conducción más largos si el vehículo lo permite."
                )
        else:
            power_fallback_warnings.append(
                "Se mantiene el filtro ≥100 kW; la alternativa ≥50 kW no mejora el plan."
            )

    computation, destination_stay = _enrich_with_destination_stay(
        repo,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        vehicle=vehicle,
        destination_radius_km=destination_radius_km,
        local_mobility_km=local_mobility_km,
        countries=countries,
        computation=computation,
        projected_soc_at_arrival_pct=computation.soc_at_destination_pct,
    )

    extra_warnings = [*power_fallback_warnings, *(osrm_warnings or [])]
    if extra_warnings:
        computation = replace(
            computation,
            warnings=[*computation.warnings, *extra_warnings],
        )

    return ChargingPlanBuildResult(
        mode="route",
        vehicle=vehicle,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_lat=dest_lat,
        destination_lon=dest_lon,
        corridor_km=corridor_km,
        route_distance_km=round(osrm_route.distance_m / 1000.0, 2),
        route_duration_minutes=round(osrm_route.duration_s / 60.0, 1),
        route_shortest_distance_km=route_alternatives.shortest_distance_km,
        route_fastest_distance_km=route_alternatives.fastest_distance_km,
        geodesic_distance_km=route_alternatives.geodesic_distance_km,
        route_conventional_distance_km=route_alternatives.conventional_distance_km,
        route_conventional_duration_minutes=route_alternatives.conventional_duration_minutes,
        route_shortest_duration_minutes=route_alternatives.shortest_duration_minutes,
        route_fastest_duration_minutes=route_alternatives.fastest_duration_minutes,
        shortest_excess_km=route_alternatives.shortest_excess_km,
        route_variants_approximate=route_alternatives.variants_approximate,
        route_geometry=osrm_route.geojson_geometry if include_route else None,
        preview_route_geometry=None,
        route_shortest_geometry=(
            variant_routes["shortest"].geojson_geometry
            if include_route and "shortest" in variant_routes
            else None
        ),
        route_fastest_geometry=(
            variant_routes["fastest"].geojson_geometry
            if include_route and "fastest" in variant_routes
            else None
        ),
        route_conventional_geometry=(
            variant_routes["conventional"].geojson_geometry
            if include_route and "conventional" in variant_routes
            else None
        ),
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        exclude_slow_chargers=exclude_slow_chargers,
        computation=computation,
        candidates_in_bbox=candidates_count,
        destination_stay=destination_stay,
        preferred_operators=charging_preferences.preferred_operators,
        max_price_eur_kwh=charging_preferences.max_price_eur_kwh,
    )
