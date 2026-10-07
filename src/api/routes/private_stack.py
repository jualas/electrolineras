from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from api.agent_trip_chat import chat_action_chips, handle_trip_chat_turn
from api.agent_trip_guide import build_trip_guide_response
from api.auth.private_access import (
    private_stack_configured,
    private_totp_auth_configured,
    require_private_access,
)
from api.config import settings
from api.dependencies import get_repository
from api.integrations.cursor_bridge_client import cursor_bridge_configured
from api.integrations.dify_client import dify_trip_guide_configured
from api.integrations.telemetry_energy import vehicle_energy_from_telemetry
from api.integrations.teslamate import TeslaMateError, VehicleTelemetry
from api.integrations.vehicle_telemetry import (
    fetch_vehicle_telemetry,
    mqtt_configured,
    teslamate_api_configured,
    vehicle_telemetry_configured,
)
from api.routes.agent_tools import agent_trip_advice
from api.schemas import (
    MAX_CORRIDOR_KM,
    HomeLocationResult,
    PrivateStackStatusResult,
    RoutePreference,
    TripAdviceResponse,
    TripChatRequest,
    TripChatResponse,
    TripGuideResponse,
    VehicleTelemetryResult,
)
from db.repository import StationRepository

router = APIRouter(
    prefix="/api/v1/private",
    tags=["private"],
    dependencies=[Depends(require_private_access)],
)


def _telemetry_to_schema(telemetry: VehicleTelemetry) -> VehicleTelemetryResult:
    return VehicleTelemetryResult(
        car_id=telemetry.car_id,
        display_name=telemetry.display_name,
        state=telemetry.state,
        lat=telemetry.lat,
        lon=telemetry.lon,
        battery_level_pct=telemetry.battery_level_pct,
        usable_battery_level_pct=telemetry.usable_battery_level_pct,
        est_battery_range_km=telemetry.est_battery_range_km,
        rated_battery_range_km=telemetry.rated_battery_range_km,
        ideal_battery_range_km=telemetry.ideal_battery_range_km,
        model=telemetry.model,
        trim_badging=telemetry.trim_badging,
        car_model_label=telemetry.car_model_label,
        version=telemetry.version,
        charging_state=telemetry.charging_state,
        inside_temp_c=telemetry.inside_temp_c,
        outside_temp_c=telemetry.outside_temp_c,
        odometer_km=telemetry.odometer_km,
        efficiency_kwh_per_km=telemetry.efficiency_kwh_per_km,
        source=telemetry.source,
    )


def _get_vehicle_telemetry(car_id: int | None = None) -> VehicleTelemetry:
    if not vehicle_telemetry_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "Telemetría TeslaMate no configurada. "
                "MQTT: TESLAMATE_MQTT_* (recomendado, ver INTEGRACION_APPS.md) "
                "o TeslaMateApi: TESLAMATE_API_*"
            ),
        )
    try:
        return fetch_vehicle_telemetry(car_id=car_id)
    except TeslaMateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/status")
def private_stack_status() -> PrivateStackStatusResult:
    return PrivateStackStatusResult(
        private_stack_enabled=settings.private_stack_enabled,
        token_required=private_stack_configured(),
        teslamate_configured=vehicle_telemetry_configured(),
        charging_agent_enabled=settings.charging_agent_enabled,
        login_enabled=private_totp_auth_configured(),
        mqtt_configured=mqtt_configured(),
        teslamate_api_configured=teslamate_api_configured(),
        dify_trip_guide_configured=dify_trip_guide_configured(),
        cursor_bridge_configured=cursor_bridge_configured(),
    )


@router.get("/home-location")
def private_home_location() -> HomeLocationResult:
    if settings.home_lat is None or settings.home_lon is None:
        raise HTTPException(status_code=404, detail="Ubicación de casa no configurada")
    return HomeLocationResult(label=settings.home_label, lat=settings.home_lat, lon=settings.home_lon)


@router.get("/vehicle/state")
def private_vehicle_state(
    car_id: Annotated[int | None, Query(ge=1, description="ID TeslaMate; default TESLAMATE_CAR_ID")] = None,
) -> VehicleTelemetryResult:
    telemetry = _get_vehicle_telemetry(car_id=car_id)
    return _telemetry_to_schema(telemetry)


def _resolve_car_energy(
    telemetry: VehicleTelemetry,
    *,
    terrain_factor: float,
    reserve_soc_percent: float,
    departure_soc_percent: float | None,
    vehicle_preset_id: str | None = None,
    usable_capacity_kwh: float | None = None,
) -> tuple[float, float, float, float, float]:
    """Returns soc, capacity, consumption, reserve, live_soc."""
    live_soc = telemetry.battery_level_pct
    soc_percent, usable_capacity_kwh, consumption_wh_per_km, reserve = vehicle_energy_from_telemetry(
        telemetry,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        departure_soc_percent=departure_soc_percent,
        vehicle_preset_id=vehicle_preset_id,
        usable_capacity_kwh=usable_capacity_kwh,
    )
    return soc_percent, usable_capacity_kwh, consumption_wh_per_km, reserve, live_soc


def _trip_advice_response(
    *,
    repo: StationRepository,
    telemetry: VehicleTelemetry,
    terrain_factor: float,
    reserve_soc_percent: float,
    departure_soc_percent: float | None,
    vehicle_preset_id: str | None = None,
    usable_capacity_kwh: float | None = None,
    **agent_kwargs,
) -> TripAdviceResponse:
    try:
        soc_percent, resolved_capacity, consumption_wh_per_km, reserve, live_soc = _resolve_car_energy(
            telemetry,
            terrain_factor=terrain_factor,
            reserve_soc_percent=reserve_soc_percent,
            departure_soc_percent=departure_soc_percent,
            vehicle_preset_id=vehicle_preset_id,
            usable_capacity_kwh=usable_capacity_kwh,
        )
    except TeslaMateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    advice = agent_trip_advice(
        repo=repo,
        origin_lat=telemetry.lat,
        origin_lon=telemetry.lon,
        soc_percent=soc_percent,
        usable_capacity_kwh=resolved_capacity,
        consumption_wh_per_km=consumption_wh_per_km,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve,
        vehicle_preset_id=vehicle_preset_id,
        **agent_kwargs,
    )
    bullets = list(advice.agent_bullets)
    if abs(soc_percent - live_soc) >= 1:
        bullets.insert(
            0,
            f"Simulación al salir: {soc_percent:.0f} % SOC (ahora {live_soc:.0f} % en el coche).",
        )
    return TripAdviceResponse(
        plan=advice.plan,
        agent_summary=advice.agent_summary,
        agent_bullets=bullets,
        vehicle=_telemetry_to_schema(telemetry),
        live_soc_percent=round(live_soc, 1),
        departure_soc_percent=round(soc_percent, 1),
    )


@router.get("/trip-advice-from-car")
def private_trip_advice_from_car(
    repo: Annotated[StationRepository, Depends(get_repository)],
    dest_lat: Annotated[float, Query(ge=-90, le=90)],
    dest_lon: Annotated[float, Query(ge=-180, le=180)],
    via_lat: Annotated[
        list[float] | None,
        Query(description="Latitudes de paradas intermedias (mismo orden que via_lon)"),
    ] = None,
    via_lon: Annotated[
        list[float] | None,
        Query(description="Longitudes de paradas intermedias (mismo orden que via_lat)"),
    ] = None,
    terrain_factor: Annotated[float, Query(gt=0, le=2)] = 1.0,
    reserve_soc_percent: Annotated[float, Query(ge=0, le=50)] = 10.0,
    min_kw: Annotated[float, Query(ge=0)] = 100.0,
    corridor_km: Annotated[float, Query(gt=0, le=MAX_CORRIDOR_KM)] = settings.route_corridor_km_default,
    destination_radius_km: Annotated[float, Query(gt=0, le=50)] = 10.0,
    local_mobility_km: Annotated[float, Query(gt=0, le=200)] = 40.0,
    car_id: Annotated[int | None, Query(ge=1)] = None,
    include_route: Annotated[bool, Query()] = False,
    route_preference: Annotated[RoutePreference, Query()] = "fastest",
    avoid_highways: Annotated[bool, Query(description="Evitar peajes (OSRM exclude=toll). Default true.")] = True,
    preferred_operators: Annotated[str | None, Query(max_length=500)] = None,
    max_price_eur_kwh: Annotated[float | None, Query(gt=0, le=2)] = None,
    departure_soc_percent: Annotated[
        float | None,
        Query(ge=5, le=100, description="Simular SOC al salir (p. ej. tras cargar en casa)"),
    ] = None,
    max_charge_power_kw: Annotated[float, Query(gt=0, le=350)] = 100.0,
    min_destination_soc_pct: Annotated[float, Query(ge=0, le=50)] = 10.0,
    min_stop_arrival_soc_pct: Annotated[float, Query(ge=0, le=50)] = 10.0,
    max_charge_soc_pct: Annotated[float, Query(ge=20, le=100)] = 80.0,
    exclude_slow_chargers: Annotated[bool, Query()] = False,
    consumption_kwh_per_100km: Annotated[float | None, Query(gt=0, le=50)] = None,
    vehicle_preset_id: Annotated[str | None, Query(max_length=64)] = None,
    usable_capacity_kwh: Annotated[float | None, Query(gt=0, le=200)] = None,
) -> TripAdviceResponse:
    """Plan de carga usando posición y SOC del coche vía TeslaMate (solo stack privado)."""
    if not settings.charging_agent_enabled:
        raise HTTPException(status_code=503, detail="Asistente de viaje desactivado")

    telemetry = _get_vehicle_telemetry(car_id=car_id)
    return _trip_advice_response(
        repo=repo,
        telemetry=telemetry,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        departure_soc_percent=departure_soc_percent,
        vehicle_preset_id=vehicle_preset_id,
        usable_capacity_kwh=usable_capacity_kwh,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        via_lat=via_lat,
        via_lon=via_lon,
        min_kw=min_kw,
        corridor_km=corridor_km,
        include_route=include_route,
        destination_radius_km=destination_radius_km,
        local_mobility_km=local_mobility_km,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        preferred_operators=preferred_operators,
        max_price_eur_kwh=max_price_eur_kwh,
        max_charge_power_kw=max_charge_power_kw,
        min_destination_soc_pct=min_destination_soc_pct,
        min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
        max_charge_soc_pct=max_charge_soc_pct,
        exclude_slow_chargers=exclude_slow_chargers,
        consumption_kwh_per_100km=consumption_kwh_per_100km,
    )


@router.get("/trip-guide-from-car")
def private_trip_guide_from_car(
    repo: Annotated[StationRepository, Depends(get_repository)],
    dest_lat: Annotated[float, Query(ge=-90, le=90)],
    dest_lon: Annotated[float, Query(ge=-180, le=180)],
    via_lat: Annotated[
        list[float] | None,
        Query(description="Latitudes de paradas intermedias (mismo orden que via_lon)"),
    ] = None,
    via_lon: Annotated[
        list[float] | None,
        Query(description="Longitudes de paradas intermedias (mismo orden que via_lat)"),
    ] = None,
    terrain_factor: Annotated[float, Query(gt=0, le=2)] = 1.0,
    reserve_soc_percent: Annotated[float, Query(ge=0, le=50)] = 10.0,
    min_kw: Annotated[float, Query(ge=0)] = 100.0,
    corridor_km: Annotated[float, Query(gt=0, le=MAX_CORRIDOR_KM)] = settings.route_corridor_km_default,
    destination_radius_km: Annotated[float, Query(gt=0, le=50)] = 10.0,
    local_mobility_km: Annotated[float, Query(gt=0, le=200)] = 40.0,
    car_id: Annotated[int | None, Query(ge=1)] = None,
    include_route: Annotated[bool, Query()] = False,
    dest_label: Annotated[str | None, Query(max_length=500)] = None,
    cultural_poi: Annotated[bool, Query(description="Incluir ideas culturales y gastronomía")] = True,
    invoke_dify: Annotated[bool, Query(description="Llamar workflow Dify si está configurado")] = True,
    user_note: Annotated[str | None, Query(max_length=2000, description="Pregunta o nota para la guía IA")] = None,
    route_preference: Annotated[RoutePreference, Query()] = "fastest",
    avoid_highways: Annotated[bool, Query(description="Evitar peajes (OSRM exclude=toll). Default true.")] = True,
    preferred_operators: Annotated[str | None, Query(max_length=500)] = None,
    max_price_eur_kwh: Annotated[float | None, Query(gt=0, le=2)] = None,
    departure_soc_percent: Annotated[
        float | None,
        Query(ge=5, le=100, description="Simular SOC al salir (p. ej. tras cargar en casa)"),
    ] = None,
    max_charge_power_kw: Annotated[float, Query(gt=0, le=350)] = 100.0,
    min_destination_soc_pct: Annotated[float, Query(ge=0, le=50)] = 10.0,
    min_stop_arrival_soc_pct: Annotated[float, Query(ge=0, le=50)] = 10.0,
    max_charge_soc_pct: Annotated[float, Query(ge=20, le=100)] = 80.0,
    exclude_slow_chargers: Annotated[bool, Query()] = False,
    consumption_kwh_per_100km: Annotated[float | None, Query(gt=0, le=50)] = None,
    vehicle_preset_id: Annotated[str | None, Query(max_length=64)] = None,
    usable_capacity_kwh: Annotated[float | None, Query(gt=0, le=200)] = None,
) -> TripGuideResponse:
    """Plan de carga + guía de viaje (motor local o Dify) desde telemetría del coche."""
    if not settings.charging_agent_enabled:
        raise HTTPException(status_code=503, detail="Asistente de viaje desactivado")

    telemetry = _get_vehicle_telemetry(car_id=car_id)
    advice = _trip_advice_response(
        repo=repo,
        telemetry=telemetry,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        departure_soc_percent=departure_soc_percent,
        vehicle_preset_id=vehicle_preset_id,
        usable_capacity_kwh=usable_capacity_kwh,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        via_lat=via_lat,
        via_lon=via_lon,
        min_kw=min_kw,
        corridor_km=corridor_km,
        include_route=include_route,
        destination_radius_km=destination_radius_km,
        local_mobility_km=local_mobility_km,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        preferred_operators=preferred_operators,
        max_price_eur_kwh=max_price_eur_kwh,
        max_charge_power_kw=max_charge_power_kw,
        min_destination_soc_pct=min_destination_soc_pct,
        min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
        max_charge_soc_pct=max_charge_soc_pct,
        exclude_slow_chargers=exclude_slow_chargers,
        consumption_kwh_per_100km=consumption_kwh_per_100km,
    )
    guide = build_trip_guide_response(
        advice.plan,
        vehicle=advice.vehicle,
        destination_label=dest_label,
        cultural_poi_enabled=cultural_poi,
        user_note=user_note,
        invoke_dify=invoke_dify,
    )
    return guide.model_copy(
        update={
            "agent_bullets": advice.agent_bullets,
            "live_soc_percent": advice.live_soc_percent,
            "departure_soc_percent": advice.departure_soc_percent,
        }
    )


@router.post("/trip-chat")
def private_trip_chat(body: TripChatRequest) -> TripChatResponse:
    """Turno de chat sobre el plan activo (#6166). No genera guía monólogo."""
    if not settings.charging_agent_enabled:
        raise HTTPException(status_code=503, detail="Asistente de viaje desactivado")

    history = [{"role": item.role, "content": item.content} for item in body.history]
    turn = handle_trip_chat_turn(
        body.message,
        plan_snapshot=body.plan_snapshot,
        history=history,
        allow_llm=body.allow_llm,
    )
    return TripChatResponse(
        reply=turn.reply,
        reply_source=turn.reply_source,
        intent_id=turn.intent_id,
        needs_replan=turn.needs_replan or turn.overrides.needs_replan(),
        overrides=turn.overrides.as_dict(),
        chips=chat_action_chips(),
    )

