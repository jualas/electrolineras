from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query

from api.charging_plan_service import ChargingPlanBuildResult, build_charging_plan
from api.config import settings
from api.dependencies import get_repository
from api.routing.charging_plan import VehicleEnergyProfile
from api.routing.trip_metrics import build_route_trip_summary, planned_stop_to_result
from api.schemas import (
    MAX_CORRIDOR_KM,
    MAX_ROUTE_RESULTS_LIMIT,
    ChargingPlanResponse,
    ChargingPlanStopResult,
    ChargingPlanStrategyResult,
    DestinationStayAdviceResult,
    PlannedRouteStopResult,
    RouteEndpoint,
    RoutePreference,
    VehicleEnergyInput,
)
from db.repository import StationRepository

router = APIRouter(prefix="/api/v1", tags=["charging-plan"])


def parse_via_waypoints(
    via_lat: list[float] | None,
    via_lon: list[float] | None,
) -> list[tuple[float, float]]:
    via_lats = via_lat or []
    via_lons = via_lon or []
    if len(via_lats) != len(via_lons):
        raise HTTPException(
            status_code=422,
            detail="via_lat y via_lon deben tener la misma longitud",
        )
    for lat in via_lats:
        if lat < -90 or lat > 90:
            raise HTTPException(status_code=422, detail="via_lat fuera de rango")
    for lon in via_lons:
        if lon < -180 or lon > 180:
            raise HTTPException(status_code=422, detail="via_lon fuera de rango")
    return list(zip(via_lats, via_lons, strict=True))


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
        route_shortest_distance_km=built.route_shortest_distance_km,
        route_fastest_distance_km=built.route_fastest_distance_km,
        geodesic_distance_km=built.geodesic_distance_km,
        route_conventional_distance_km=built.route_conventional_distance_km,
        route_conventional_duration_minutes=built.route_conventional_duration_minutes,
        shortest_excess_km=built.shortest_excess_km,
        route_variants_approximate=built.route_variants_approximate,
        route_geometry=built.route_geometry,
        route_shortest_geometry=built.route_shortest_geometry,
        route_fastest_geometry=built.route_fastest_geometry,
        route_conventional_geometry=built.route_conventional_geometry,
        preview_route_geometry=built.preview_route_geometry,
        route_preference=built.route_preference,
        avoid_highways=built.avoid_highways,
        exclude_slow_chargers=built.exclude_slow_chargers,
        computation=built.computation,
        candidates_in_bbox=built.candidates_in_bbox,
        destination_stay=built.destination_stay,
        preferred_operators=built.preferred_operators,
        max_price_eur_kwh=built.max_price_eur_kwh,
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
    route_shortest_distance_km: float | None = None,
    route_fastest_distance_km: float | None = None,
    geodesic_distance_km: float | None = None,
    route_conventional_distance_km: float | None = None,
    route_conventional_duration_minutes: float | None = None,
    shortest_excess_km: float | None = None,
    route_variants_approximate: bool = False,
    route_geometry: dict | None,
    route_shortest_geometry: dict | None = None,
    route_fastest_geometry: dict | None = None,
    route_conventional_geometry: dict | None = None,
    preview_route_geometry: dict | None = None,
    route_preference: RoutePreference | None = None,
    avoid_highways: bool = False,
    exclude_slow_chargers: bool = False,
    computation,
    candidates_in_bbox: int,
    destination_stay: DestinationStayAdviceResult | None = None,
    preferred_operators: tuple[str, ...] = (),
    max_price_eur_kwh: float | None = None,
) -> ChargingPlanResponse:
    vehicle_input = VehicleEnergyInput(
        soc_percent=vehicle.soc_percent,
        usable_capacity_kwh=vehicle.usable_capacity_kwh,
        consumption_wh_per_km=vehicle.consumption_wh_per_km,
        terrain_factor=vehicle.terrain_factor,
        reserve_soc_percent=vehicle.reserve_soc_percent,
        vehicle_preset_id=vehicle.vehicle_preset_id,
        max_charge_power_kw=vehicle.max_charge_power_kw,
        min_destination_soc_pct=vehicle.min_destination_soc_pct,
        min_stop_arrival_soc_pct=vehicle.min_stop_arrival_soc_pct,
        max_charge_soc_pct=vehicle.max_charge_soc_pct,
        consumption_kwh_per_100km=round(vehicle.consumption_wh_per_km / 10.0, 2),
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
        route_shortest_distance_km=route_shortest_distance_km,
        route_fastest_distance_km=route_fastest_distance_km,
        geodesic_distance_km=geodesic_distance_km,
        route_conventional_distance_km=route_conventional_distance_km,
        route_conventional_duration_minutes=route_conventional_duration_minutes,
        shortest_excess_km=shortest_excess_km,
        route_variants_approximate=route_variants_approximate,
        soc_at_destination_pct=computation.soc_at_destination_pct,
        reachable_without_stop=computation.reachable_without_stop,
        route_geometry=route_geometry,
        route_shortest_geometry=route_shortest_geometry,
        route_fastest_geometry=route_fastest_geometry,
        route_conventional_geometry=route_conventional_geometry,
        preview_route_geometry=preview_route_geometry,
        route_preference=route_preference,
        avoid_highways=avoid_highways,
        exclude_slow_chargers=exclude_slow_chargers,
        preferred_operators=list(preferred_operators),
        max_price_eur_kwh=max_price_eur_kwh,
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
        planned_stops=[
            planned_stop_to_result(stop, profile=vehicle)
            for stop in computation.planned_stops
        ],
        projected_soc_at_destination_with_plan=computation.projected_soc_at_destination_with_plan,
        route_trip_summary=build_route_trip_summary(
            profile=vehicle,
            planned_stops=computation.planned_stops,
            route_distance_km=route_distance_km,
            route_duration_minutes=route_duration_minutes,
            projected_destination_soc_pct=computation.projected_soc_at_destination_with_plan,
        ),
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
    via_lat: Annotated[
        list[float] | None,
        Query(description="Latitudes de paradas intermedias (mismo orden que via_lon)"),
    ] = None,
    via_lon: Annotated[
        list[float] | None,
        Query(description="Longitudes de paradas intermedias (mismo orden que via_lat)"),
    ] = None,
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
    route_preference: Annotated[
        RoutePreference,
        Query(
            description=(
                "fastest = menos tiempo; shortest = menos km; "
                "conventional = solo nacionales/secundarias (sin autovía, sin priorizar tiempo)"
            ),
        ),
    ] = "fastest",
    avoid_highways: Annotated[
        bool,
        Query(description="Evitar autopistas de peaje (OSRM exclude=toll); autovías libres permitidas"),
    ] = False,
    vehicle_preset_id: Annotated[
        str | None,
        Query(max_length=64, description="Preset vehículo para curva DC (p. ej. tesla-model3-sr-2023)"),
    ] = None,
    preferred_operators: Annotated[
        str | None,
        Query(
            max_length=500,
            description="Operadores preferidos (CSV, p. ej. ionity,tesla); ranking blando",
        ),
    ] = None,
    max_price_eur_kwh: Annotated[
        float | None,
        Query(gt=0, le=2, description="Precio máximo preferido (€/kWh); ranking blando"),
    ] = None,
    max_charge_power_kw: Annotated[
        float,
        Query(gt=0, le=350, description="Potencia máx. de carga del vehículo (kW); estilo REVE"),
    ] = 100.0,
    min_destination_soc_pct: Annotated[
        float,
        Query(ge=0, le=50, description="SOC mínimo deseado al llegar al destino (%)"),
    ] = 10.0,
    min_stop_arrival_soc_pct: Annotated[
        float,
        Query(ge=0, le=50, description="SOC mínimo al llegar a cada parada de carga (%)"),
    ] = 10.0,
    max_charge_soc_pct: Annotated[
        float,
        Query(ge=20, le=100, description="SOC máximo de carga rápida DC por parada (%)"),
    ] = 80.0,
    exclude_slow_chargers: Annotated[
        bool,
        Query(description="Excluir cargadores lentos (AC / <50 kW) del plan en ruta"),
    ] = False,
    consumption_kwh_per_100km: Annotated[
        float | None,
        Query(gt=0, le=50, description="Consumo (kWh/100 km); alternativa a consumption_wh_per_km"),
    ] = None,
    battery_capacity_kwh: Annotated[
        float | None,
        Query(gt=0, le=200, description="Alias de usable_capacity_kwh (kWh útiles)"),
    ] = None,
    departure_soc_pct: Annotated[
        float | None,
        Query(ge=0, le=100, description="Alias de soc_percent — SOC al salir (%)"),
    ] = None,
) -> ChargingPlanResponse:
    resolved_capacity = battery_capacity_kwh if battery_capacity_kwh is not None else usable_capacity_kwh
    resolved_soc = departure_soc_pct if departure_soc_pct is not None else soc_percent
    waypoints = parse_via_waypoints(via_lat, via_lon)
    built = build_charging_plan(
        repo,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
        soc_percent=resolved_soc,
        usable_capacity_kwh=resolved_capacity,
        consumption_wh_per_km=consumption_wh_per_km,
        terrain_factor=terrain_factor,
        reserve_soc_percent=reserve_soc_percent,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        dest_lat=dest_lat,
        dest_lon=dest_lon,
        waypoints=waypoints or None,
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
        vehicle_preset_id=vehicle_preset_id,
        preferred_operators=preferred_operators,
        max_price_eur_kwh=max_price_eur_kwh,
        max_charge_power_kw=max_charge_power_kw,
        min_destination_soc_pct=min_destination_soc_pct,
        min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
        max_charge_soc_pct=max_charge_soc_pct,
        exclude_slow_chargers=exclude_slow_chargers,
        consumption_kwh_per_100km=consumption_kwh_per_100km,
    )
    return charging_plan_to_response(built)
