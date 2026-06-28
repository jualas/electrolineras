from __future__ import annotations

import math
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.config import settings
from api.dependencies import get_repository
from api.query_params import parse_country_list
from api.routing.charging_plan import (
    VehicleEnergyProfile,
    build_emergency_charging_plan,
    build_route_charging_plan,
    estimate_charging_reach_km,
    estimate_range_km,
)
from api.routing.corridor import RoutePolyline, rank_stations_along_route
from api.routing.osrm import RoutingError, fetch_osrm_route
from api.schemas import (
    MAX_CORRIDOR_KM,
    MAX_ROUTE_RESULTS_LIMIT,
    ChargingPlanResponse,
    ChargingPlanStopResult,
    ChargingPlanStrategyResult,
    RouteEndpoint,
    VehicleEnergyInput,
)
from db.repository import StationRepository
from db.spatial import haversine_m

router = APIRouter(prefix="/api/v1", tags=["charging-plan"])


def _rank_stations_near_origin(
    repo: StationRepository,
    *,
    origin_lat: float,
    origin_lon: float,
    min_kw: float | None,
    max_kw: float | None,
    countries: list[str] | None,
    search_radius_m: float,
) -> list[tuple[Station, float]]:
    lat_pad = search_radius_m / 111_320.0
    cos_lat = max(0.1, abs(math.cos(math.radians(origin_lat))))
    lon_pad = search_radius_m / (111_320.0 * cos_lat)
    candidates = repo.search(
        west=origin_lon - lon_pad,
        south=origin_lat - lat_pad,
        east=origin_lon + lon_pad,
        north=origin_lat + lat_pad,
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
                haversine_m(origin_lat, origin_lon, station.location.lat, station.location.lon) / 1000.0,
            )
            for station in candidates
        ),
        key=lambda item: item[1],
    )


def _vehicle_profile_from_query(
    soc_percent: float,
    usable_capacity_kwh: float,
    consumption_wh_per_km: float,
    terrain_factor: float,
    reserve_soc_percent: float,
) -> VehicleEnergyProfile:
    if usable_capacity_kwh <= 0:
        raise HTTPException(status_code=422, detail="usable_capacity_kwh debe ser mayor que 0")
    if consumption_wh_per_km <= 0:
        raise HTTPException(status_code=422, detail="consumption_wh_per_km debe ser mayor que 0")
    if terrain_factor <= 0:
        raise HTTPException(status_code=422, detail="terrain_factor debe ser mayor que 0")
    return VehicleEnergyProfile(
        soc_percent=soc_percent,
        usable_capacity_kwh=usable_capacity_kwh,
        consumption_wh_per_km=consumption_wh_per_km,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
    )


def _to_response(
    *,
    mode: Literal["route", "emergency"],
    vehicle: VehicleEnergyProfile,
    origin_lat: float,
    origin_lon: float,
    destination_lat: float | None,
    destination_lon: float | None,
    corridor_km: float | None,
    route_distance_km: float | None,
    route_duration_minutes: float | None,
    route_geometry: dict | None,
    preview_route_geometry: dict | None = None,
    computation,
    candidates_in_bbox: int,
) -> ChargingPlanResponse:
    vehicle_input = VehicleEnergyInput(
        soc_percent=vehicle.soc_percent,
        usable_capacity_kwh=vehicle.usable_capacity_kwh,
        consumption_wh_per_km=vehicle.consumption_wh_per_km,
        terrain_factor=vehicle.terrain_factor,
        reserve_soc_percent=vehicle.reserve_soc_percent,
    )
    destination = None
    if destination_lat is not None and destination_lon is not None:
        destination = RouteEndpoint(lat=destination_lat, lon=destination_lon)

    return ChargingPlanResponse(
        mode=mode,
        vehicle=vehicle_input,
        range_km=computation.range_km,
        charging_reach_km=computation.charging_reach_km,
        origin=RouteEndpoint(lat=origin_lat, lon=origin_lon),
        destination=destination,
        corridor_km=corridor_km,
        route_distance_km=route_distance_km,
        route_duration_minutes=route_duration_minutes,
        soc_at_destination_pct=computation.soc_at_destination_pct,
        reachable_without_stop=computation.reachable_without_stop,
        route_geometry=route_geometry,
        preview_route_geometry=preview_route_geometry,
        stops=[
            ChargingPlanStopResult(
                station=stop.station,
                deviation_km=stop.deviation_km,
                route_distance_km=stop.route_distance_km,
                extra_minutes=stop.extra_minutes,
                wrong_side=stop.wrong_side,
                distance_from_origin_km=stop.distance_from_origin_km,
                soc_arrival_pct=stop.soc_arrival_pct,
                classification=stop.classification,
            )
            for stop in computation.stops
        ],
        origin_stops=[
            ChargingPlanStopResult(
                station=stop.station,
                deviation_km=stop.deviation_km,
                route_distance_km=stop.route_distance_km,
                extra_minutes=stop.extra_minutes,
                wrong_side=stop.wrong_side,
                distance_from_origin_km=stop.distance_from_origin_km,
                soc_arrival_pct=stop.soc_arrival_pct,
                classification=stop.classification,
            )
            for stop in computation.origin_stops
        ],
        strategies=[
            ChargingPlanStrategyResult(
                id=strategy.id,
                label=strategy.label,
                station_id=strategy.station_id,
                soc_arrival_pct=strategy.soc_arrival_pct,
                classification=strategy.classification,
                summary=strategy.summary,
            )
            for strategy in computation.strategies
        ],
        warnings=computation.warnings,
        candidates_in_bbox=candidates_in_bbox,
    )


@router.get("/stations/charging-plan")
def stations_charging_plan(
    repo: Annotated[StationRepository, Depends(get_repository)],
    origin_lat: Annotated[float, Query(ge=-90, le=90, description="Latitud origen")],
    origin_lon: Annotated[float, Query(ge=-180, le=180, description="Longitud origen")],
    soc_percent: Annotated[float, Query(ge=0, le=100, description="SOC actual (%)")],
    usable_capacity_kwh: Annotated[float, Query(gt=0, le=200, description="Capacidad útil (kWh)")],
    consumption_wh_per_km: Annotated[float, Query(gt=0, le=500, description="Consumo base (Wh/km)")],
    terrain_factor: Annotated[
        float,
        Query(gt=0, le=2, description="Multiplicador de consumo por terreno"),
    ] = 1.0,
    reserve_soc_percent: Annotated[
        float,
        Query(ge=0, le=50, description="SOC reserva mínima (%)"),
    ] = 10.0,
    safe_margin_pct: Annotated[
        float,
        Query(ge=0, le=50, description="Margen clasificación segura (%)"),
    ] = 15.0,
    adjusted_min_pct: Annotated[
        float,
        Query(ge=0, le=50, description="Umbral mínimo clasificación ajustada (%)"),
    ] = 10.0,
    dest_lat: Annotated[float | None, Query(ge=-90, le=90, description="Latitud destino")] = None,
    dest_lon: Annotated[float | None, Query(ge=-180, le=180, description="Longitud destino")] = None,
    min_kw: Annotated[
        float,
        Query(ge=0, description="Potencia mínima (kW); default viaje ≥100"),
    ] = 100.0,
    max_kw: Annotated[float | None, Query(ge=0, description="Potencia máxima (kW)")] = None,
    country: Annotated[str | None, Query(description="Países ISO (ES,PT)")] = None,
    corridor_km: Annotated[
        float,
        Query(gt=0, le=MAX_CORRIDOR_KM, description="Ancho del corredor en km"),
    ] = settings.route_corridor_km_default,
    behind_margin_km: Annotated[
        float,
        Query(ge=0, le=20, description="Margen anti-retroceso en km"),
    ] = settings.route_behind_margin_km_default,
    limit: Annotated[
        int,
        Query(ge=1, le=MAX_ROUTE_RESULTS_LIMIT, description="Máximo de paradas"),
    ] = settings.route_results_limit_default,
    include_route: Annotated[
        bool,
        Query(description="Incluir geometría GeoJSON de la ruta"),
    ] = True,
    emergency_radius_km: Annotated[
        float,
        Query(gt=0, le=200, description="Radio búsqueda emergencia (km)"),
    ] = 80.0,
) -> ChargingPlanResponse:
    if min_kw is not None and max_kw is not None and min_kw > max_kw:
        raise HTTPException(status_code=422, detail="min_kw no puede ser mayor que max_kw")

    has_destination = dest_lat is not None and dest_lon is not None
    if (dest_lat is None) ^ (dest_lon is None):
        raise HTTPException(status_code=422, detail="dest_lat y dest_lon deben enviarse juntos o omitirse")

    vehicle = _vehicle_profile_from_query(
        soc_percent,
        usable_capacity_kwh,
        consumption_wh_per_km,
        terrain_factor,
        reserve_soc_percent,
    )
    countries = parse_country_list(country)

    if not has_destination:
        range_km = estimate_range_km(vehicle)
        charging_reach_km = estimate_charging_reach_km(vehicle)
        search_radius_m = max(emergency_radius_km, charging_reach_km, range_km) * 1000.0
        ranked = _rank_stations_near_origin(
            repo,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
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

        return _to_response(
            mode="emergency",
            vehicle=vehicle,
            origin_lat=origin_lat,
            origin_lon=origin_lon,
            destination_lat=None,
            destination_lon=None,
            corridor_km=None,
            route_distance_km=route_distance_km,
            route_duration_minutes=route_duration_minutes,
            route_geometry=None,
            preview_route_geometry=preview_route_geometry,
            computation=computation,
            candidates_in_bbox=len(ranked),
        )

    try:
        osrm_route = fetch_osrm_route(origin_lat, origin_lon, dest_lat, dest_lon)
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
    origin_ranked = _rank_stations_near_origin(
        repo,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
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
    )

    return _to_response(
        mode="route",
        vehicle=vehicle,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        destination_lat=dest_lat,
        destination_lon=dest_lon,
        corridor_km=corridor_km,
        route_distance_km=round(osrm_route.distance_m / 1000.0, 2),
        route_duration_minutes=round(osrm_route.duration_s / 60.0, 1),
        route_geometry=osrm_route.geojson_geometry if include_route else None,
        computation=computation,
        candidates_in_bbox=len(candidates),
    )
