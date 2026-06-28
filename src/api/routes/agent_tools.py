from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from api.agent_narration import build_agent_narration
from api.charging_plan_service import build_charging_plan
from api.config import settings
from api.dependencies import get_repository
from api.routes.charging_plan import charging_plan_to_response
from api.schemas import MAX_CORRIDOR_KM, MAX_ROUTE_RESULTS_LIMIT, TripAdviceResponse
from db.repository import StationRepository

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])


def _verify_agent_access(
    x_agent_token: Annotated[str | None, Header(alias="X-Agent-Token")] = None,
) -> None:
    expected = settings.agent_api_token.strip()
    if not expected:
        return
    if x_agent_token != expected:
        raise HTTPException(status_code=401, detail="Token de agente inválido o ausente")


@router.get("/trip-advice", dependencies=[Depends(_verify_agent_access)])
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
    )
    plan = charging_plan_to_response(built)
    summary, bullets = build_agent_narration(plan)
    return TripAdviceResponse(plan=plan, agent_summary=summary, agent_bullets=bullets)


@router.get("/score-charging-plan", dependencies=[Depends(_verify_agent_access)])
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
