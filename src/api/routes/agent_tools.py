from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.agent_narration import build_agent_narration
from api.agent_trip_guide import build_trip_guide_response
from api.auth.private_access import require_private_access
from api.charging_plan_service import build_charging_plan
from api.config import settings
from api.dependencies import get_repository
from api.routes.charging_plan import charging_plan_to_response
from api.schemas import (
    MAX_CORRIDOR_KM,
    MAX_ROUTE_RESULTS_LIMIT,
    RoutePreference,
    TripAdviceResponse,
    TripGuideResponse,
)
from db.repository import StationRepository

router = APIRouter(
    prefix="/api/v1/agent",
    tags=["agent"],
    dependencies=[Depends(require_private_access)],
)


@router.get("/trip-advice")
def agent_trip_advice(
    repo: Annotated[StationRepository, Depends(get_repository)],
    origin_lat: Annotated[float, Query(ge=-90, le=90)],
    origin_lon: Annotated[float, Query(ge=-180, le=180)],
    soc_percent: Annotated[float, Query(ge=0, le=100)],
    usable_capacity_kwh: Annotated[float, Query(gt=0, le=200)],
    consumption_wh_per_km: Annotated[float, Query(gt=0, le=500)],
    terrain_factor: Annotated[float, Query(gt=0, le=2)] = 1.0,
    reserve_soc_percent: Annotated[float, Query(ge=0, le=50)] = 10.0,
    safe_margin_pct: Annotated[float, Query(ge=0, le=50)] = 15.0,
    adjusted_min_pct: Annotated[float, Query(ge=0, le=50)] = 10.0,
    dest_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    dest_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    min_kw: Annotated[float, Query(ge=0)] = 100.0,
    max_kw: Annotated[float | None, Query(ge=0)] = None,
    country: Annotated[str | None, Query()] = None,
    corridor_km: Annotated[float, Query(gt=0, le=MAX_CORRIDOR_KM)] = settings.route_corridor_km_default,
    behind_margin_km: Annotated[float, Query(ge=0, le=20)] = settings.route_behind_margin_km_default,
    limit: Annotated[int, Query(ge=1, le=MAX_ROUTE_RESULTS_LIMIT)] = settings.route_results_limit_default,
    include_route: Annotated[bool, Query()] = False,
    emergency_radius_km: Annotated[float, Query(gt=0, le=200)] = 80.0,
    destination_radius_km: Annotated[float, Query(gt=0, le=50, description="Radio análisis destino (km)")] = 10.0,
    local_mobility_km: Annotated[
        float,
        Query(gt=0, le=200, description="Km locales previstos en destino"),
    ] = 40.0,
    route_preference: Annotated[RoutePreference, Query()] = "fastest",
    avoid_highways: Annotated[bool, Query()] = False,
    preferred_operators: Annotated[
        str | None,
        Query(max_length=500, description="Operadores preferidos (CSV)"),
    ] = None,
    max_price_eur_kwh: Annotated[
        float | None,
        Query(gt=0, le=2, description="Precio máximo preferido (€/kWh)"),
    ] = None,
    vehicle_preset_id: Annotated[
        str | None,
        Query(max_length=64, description="Preset vehículo para curva DC"),
    ] = None,
) -> TripAdviceResponse:
    """Plan de carga + narrativa para Dify / Cursor CLI (números del motor, texto orientativo)."""
    if not settings.charging_agent_enabled:
        raise HTTPException(status_code=503, detail="Asistente de viaje desactivado (CHARGING_AGENT_ENABLED)")

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
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        preferred_operators=preferred_operators,
        max_price_eur_kwh=max_price_eur_kwh,
        vehicle_preset_id=vehicle_preset_id,
    )
    plan = charging_plan_to_response(built)
    summary, bullets = build_agent_narration(plan)
    return TripAdviceResponse(plan=plan, agent_summary=summary, agent_bullets=bullets)


@router.get("/score-charging-plan")
def agent_score_charging_plan(
    repo: Annotated[StationRepository, Depends(get_repository)],
    origin_lat: Annotated[float, Query(ge=-90, le=90)],
    origin_lon: Annotated[float, Query(ge=-180, le=180)],
    soc_percent: Annotated[float, Query(ge=0, le=100)],
    usable_capacity_kwh: Annotated[float, Query(gt=0, le=200)],
    consumption_wh_per_km: Annotated[float, Query(gt=0, le=500)],
    terrain_factor: Annotated[float, Query(gt=0, le=2)] = 1.0,
    reserve_soc_percent: Annotated[float, Query(ge=0, le=50)] = 10.0,
    dest_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    dest_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    min_kw: Annotated[float, Query(ge=0)] = 100.0,
    corridor_km: Annotated[float, Query(gt=0, le=MAX_CORRIDOR_KM)] = settings.route_corridor_km_default,
    destination_radius_km: Annotated[float, Query(gt=0, le=50)] = 10.0,
    local_mobility_km: Annotated[float, Query(gt=0, le=200)] = 40.0,
) -> TripAdviceResponse:
    """Alias reducido para workflows Dify (#6056 score_charging_plan)."""
    return agent_trip_advice(
        repo=repo,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        soc_percent=soc_percent,
        usable_capacity_kwh=usable_capacity_kwh,
        consumption_wh_per_km=consumption_wh_per_km,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        min_kw=min_kw,
        corridor_km=corridor_km,
        include_route=False,
        destination_radius_km=destination_radius_km,
        local_mobility_km=local_mobility_km,
    )


@router.get("/trip-guide")
def agent_trip_guide(
    repo: Annotated[StationRepository, Depends(get_repository)],
    origin_lat: Annotated[float, Query(ge=-90, le=90)],
    origin_lon: Annotated[float, Query(ge=-180, le=180)],
    soc_percent: Annotated[float, Query(ge=0, le=100)],
    usable_capacity_kwh: Annotated[float, Query(gt=0, le=200)],
    consumption_wh_per_km: Annotated[float, Query(gt=0, le=500)],
    terrain_factor: Annotated[float, Query(gt=0, le=2)] = 1.0,
    reserve_soc_percent: Annotated[float, Query(ge=0, le=50)] = 10.0,
    safe_margin_pct: Annotated[float, Query(ge=0, le=50)] = 15.0,
    adjusted_min_pct: Annotated[float, Query(ge=0, le=50)] = 10.0,
    dest_lat: Annotated[float | None, Query(ge=-90, le=90)] = None,
    dest_lon: Annotated[float | None, Query(ge=-180, le=180)] = None,
    min_kw: Annotated[float, Query(ge=0)] = 100.0,
    max_kw: Annotated[float | None, Query(ge=0)] = None,
    country: Annotated[str | None, Query()] = None,
    corridor_km: Annotated[float, Query(gt=0, le=MAX_CORRIDOR_KM)] = settings.route_corridor_km_default,
    behind_margin_km: Annotated[float, Query(ge=0, le=20)] = settings.route_behind_margin_km_default,
    limit: Annotated[int, Query(ge=1, le=MAX_ROUTE_RESULTS_LIMIT)] = settings.route_results_limit_default,
    include_route: Annotated[bool, Query()] = False,
    emergency_radius_km: Annotated[float, Query(gt=0, le=200)] = 80.0,
    destination_radius_km: Annotated[float, Query(gt=0, le=50)] = 10.0,
    local_mobility_km: Annotated[float, Query(gt=0, le=200)] = 40.0,
    route_preference: Annotated[RoutePreference, Query()] = "fastest",
    avoid_highways: Annotated[bool, Query()] = False,
    preferred_operators: Annotated[str | None, Query(max_length=500)] = None,
    max_price_eur_kwh: Annotated[float | None, Query(gt=0, le=2)] = None,
    dest_label: Annotated[str | None, Query(max_length=500)] = None,
    cultural_poi: Annotated[bool, Query()] = True,
    invoke_dify: Annotated[bool, Query()] = False,
) -> TripGuideResponse:
    """Contexto + guía para workflow Dify (HTTP tool). invoke_dify=false devuelve guía local."""
    if not settings.charging_agent_enabled:
        raise HTTPException(status_code=503, detail="Asistente de viaje desactivado")

    advice = agent_trip_advice(
        repo=repo,
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
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        preferred_operators=preferred_operators,
        max_price_eur_kwh=max_price_eur_kwh,
    )
    return build_trip_guide_response(
        advice.plan,
        destination_label=dest_label,
        cultural_poi_enabled=cultural_poi,
        invoke_dify=invoke_dify,
    )
