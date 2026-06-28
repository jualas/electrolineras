from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.charging_plan_service import ChargingPlanBuildResult, build_charging_plan
from api.config import settings
from api.dependencies import get_repository
from api.routing.charging_plan import VehicleEnergyProfile
from api.schemas import (
    MAX_CORRIDOR_KM,
    MAX_ROUTE_RESULTS_LIMIT,
    ChargingPlanResponse,
    ChargingPlanStopResult,
    ChargingPlanStrategyResult,
    DestinationStayAdviceResult,
    RouteEndpoint,
    VehicleEnergyInput,
)
from db.repository import StationRepository

router = APIRouter(prefix="/api/v1", tags=["charging-plan"])


def charging_plan_to_response(built: ChargingPlanBuildResult) -> ChargingPlanResponse:
    return _to_response(
        mode=built.mode,
        vehicle=built.vehicle,
        origin_lat=built.origin_lat,
        origin_lon=built.origin_lon,
        destination_lat=built.destination_lat,
        destination_lon=built.destination_lon,
        corridor_km=built.corridor_km,
        route_distance_km=built.route_distance_km,
        route_duration_minutes=built.route_duration_minutes,
        route_geometry=built.route_geometry,
        preview_route_geometry=built.preview_route_geometry,
        computation=built.computation,
        candidates_in_bbox=built.candidates_in_bbox,
        destination_stay=built.destination_stay,
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
    destination_stay: DestinationStayAdviceResult | None = None,
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
        destination_stay=destination_stay,
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
    destination_radius_km: Annotated[
        float,
        Query(gt=0, le=50, description="Radio análisis infraestructura en destino (km)"),
    ] = 10.0,
    local_mobility_km: Annotated[
        float,
        Query(gt=0, le=200, description="Km de movilidad local previstos en destino"),
    ] = 40.0,
) -> ChargingPlanResponse:
    built = build_charging_plan(
        repo,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        soc_percent=soc_percent,
        usable_capacity_kwh=usable_capacity_kwh,
        consumption_wh_per_km=consumption_wh_per_km,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        min_kw=min_kw,
        max_kw=max_kw,
        country=country,
        corridor_km=corridor_km,
        behind_margin_km=behind_margin_km,
        limit=limit,
        include_route=include_route,
        emergency_radius_km=emergency_radius_km,
        destination_radius_km=destination_radius_km,
        local_mobility_km=local_mobility_km,
    )
    return charging_plan_to_response(built)
