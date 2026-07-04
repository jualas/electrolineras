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
    build_emergency_charging_plan,
    build_route_charging_plan,
    estimate_charging_reach_km,
    estimate_range_km,
)
from api.routing.corridor import RoutePolyline, rank_stations_along_route
from api.routing.destination_stay import analyze_destination_stay, append_destination_strategy
from api.routing.osrm import (
    RoutePreference,
    RoutingError,
    fetch_osrm_route,
    fetch_osrm_route_with_alternatives,
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
) -> VehicleEnergyProfile:
    if usable_capacity_kwh <= 0:
        raise HTTPException(status_code=422, detail="usable_capacity_kwh debe ser mayor que 0")
    if consumption_wh_per_km <= 0:
        raise HTTPException(status_code=422, detail="consumption_wh_per_km debe ser mayor que 0")
    if terrain_factor <= 0:
        raise HTTPException(status_code=422, detail="terrain_factor debe ser mayor que 0")
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
    )


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
    avoid_highways: bool = False,
    vehicle_preset_id: str | None = None,
    preferred_operators: str | None = None,
    max_price_eur_kwh: float | None = None,
) -> ChargingPlanBuildResult:
    if min_kw is not None and max_kw is not None and min_kw > max_kw:
        raise HTTPException(status_code=422, detail="min_kw no puede ser mayor que max_kw")

    has_destination = dest_lat is not None and dest_lon is not None
    if (dest_lat is None) ^ (dest_lon is None):
        raise HTTPException(status_code=422, detail="dest_lat y dest_lon deben enviarse juntos o omitirse")

    vehicle = vehicle_profile_from_inputs(
        soc_percent,
        usable_capacity_kwh,
        consumption_wh_per_km,
        terrain_factor,
        reserve_soc_percent,
        vehicle_preset_id,
    )
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
            min_kw=min_kw,
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
        )
    except RoutingError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"No se pudo calcular la ruta: {exc}",
        ) from exc

    polyline = RoutePolyline(osrm_route.coordinates)
    west, south, east, north = polyline.bbox_expanded(corridor_km * 1000)
    candidates = repo.search(
        west=west,
        south=south,
        east=east,
        north=north,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        limit=10_000,
        offset=0,
    )

    wrong_side_penalty_m = settings.route_wrong_side_penalty_km_default * 1000
    matches = rank_stations_along_route(
        polyline,
        candidates,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        corridor_m=corridor_km * 1000,
        behind_margin_m=behind_margin_km * 1000,
        wrong_side_penalty_m=wrong_side_penalty_m,
        average_speed_mps=osrm_route.average_speed_mps,
        limit=limit * 3,
    )

    origin_projection = polyline.project_point(origin_lat, origin_lon)
    origin_position_km = origin_projection.route_position_m / 1000.0
    destination_distance_km = polyline.length_m / 1000.0

    range_km = estimate_range_km(vehicle)
    charging_reach_km = estimate_charging_reach_km(vehicle)
    origin_search_radius_m = max(emergency_radius_km, charging_reach_km, range_km) * 1000.0
    origin_ranked = rank_stations_near_point(
        repo,
        lat=origin_lat,
        lon=origin_lon,
        min_kw=min_kw,
        max_kw=max_kw,
        countries=countries,
        search_radius_m=origin_search_radius_m,
    )
    origin_computation = build_emergency_charging_plan(
        origin_ranked,
        profile=vehicle,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        limit=min(limit, 15),
        preferences=charging_preferences,
    )

    computation = build_route_charging_plan(
        matches,
        origin_position_km=origin_position_km,
        destination_distance_km=destination_distance_km,
        profile=vehicle,
        origin_stops=origin_computation.stops,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        limit=limit,
        preferences=charging_preferences,
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

    if osrm_warnings:
        computation = replace(
            computation,
            warnings=[*computation.warnings, *osrm_warnings],
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
        computation=computation,
        candidates_in_bbox=len(candidates),
        destination_stay=destination_stay,
        preferred_operators=charging_preferences.preferred_operators,
        max_price_eur_kwh=charging_preferences.max_price_eur_kwh,
    )
