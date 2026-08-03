"""Plan de carga multi-pierna: encadena build_charging_plan con SOC y pernoctas."""

from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException

from api.charging_plan_service import build_charging_plan
from api.routes.charging_plan import charging_plan_to_response
from api.schemas import (
    ChargingPlanResponse,
    MultiLegAggregate,
    MultiLegChargingPlanResponse,
    MultiLegPlanLegResult,
    PlannedRouteStopResult,
    RouteEndpoint,
    RoutePreference,
)
from db.repository import StationRepository

MAX_LEGS = 5


@dataclass(frozen=True)
class MultiLegStopInput:
    lat: float
    lon: float
    label: str
    overnight: bool = False
    nights: int | None = None


def _arrival_soc(plan: ChargingPlanResponse) -> float:
    if plan.projected_soc_at_destination_with_plan is not None:
        return float(plan.projected_soc_at_destination_with_plan)
    if plan.soc_at_destination_pct is not None:
        return float(plan.soc_at_destination_pct)
    return 10.0


def _departure_soc_after_stop(
    plan: ChargingPlanResponse,
    *,
    overnight: bool,
    max_charge_soc_pct: float,
) -> tuple[float, str | None]:
    arrival = _arrival_soc(plan)
    if not overnight:
        return arrival, None
    stay = plan.destination_stay
    if stay is None or stay.bands.total == 0 or stay.infrastructure_level == "none":
        return arrival, (
            f"Pernocta en {plan.destination and 'destino'}: sin cargadores detectados; "
            f"se asume salida con ~{arrival:.0f} % (llegada)."
        )
    # Overnight: assume charge toward max_charge_soc when any local infra exists
    target = max(arrival, min(float(max_charge_soc_pct), 90.0))
    note = (
        f"Pernocta: se asume carga overnight hasta ~{target:.0f} % "
        f"(infra {stay.infrastructure_level}, {stay.bands.total} cargadores)."
    )
    return target, note


def build_multi_leg_charging_plan(
    repo: StationRepository,
    *,
    origin_lat: float,
    origin_lon: float,
    origin_label: str,
    stops: list[MultiLegStopInput],
    soc_percent: float,
    usable_capacity_kwh: float,
    consumption_wh_per_km: float,
    terrain_factor: float = 1.0,
    reserve_soc_percent: float = 10.0,
    min_kw: float = 100.0,
    corridor_km: float = 10.0,
    include_route: bool = True,
    destination_radius_km: float = 10.0,
    local_mobility_km: float = 40.0,
    route_preference: RoutePreference = "fastest",
    avoid_highways: bool = False,
    preferred_operators: str | None = None,
    max_price_eur_kwh: float | None = None,
    vehicle_preset_id: str | None = None,
    max_charge_power_kw: float = 100.0,
    min_destination_soc_pct: float = 10.0,
    min_stop_arrival_soc_pct: float = 10.0,
    max_charge_soc_pct: float = 80.0,
    exclude_slow_chargers: bool = False,
    consumption_kwh_per_100km: float | None = None,
) -> MultiLegChargingPlanResponse:
    if not stops:
        raise HTTPException(status_code=422, detail="El itinerario no tiene destinos")
    if len(stops) > MAX_LEGS:
        raise HTTPException(status_code=422, detail=f"Máximo {MAX_LEGS} piernas")

    warnings: list[str] = []
    leg_results: list[MultiLegPlanLegResult] = []
    all_stops: list[PlannedRouteStopResult] = []
    current_lat, current_lon = origin_lat, origin_lon
    current_label = origin_label
    current_soc = float(soc_percent)
    total_km = 0.0
    total_drive = 0.0
    total_charge = 0.0
    global_order = 0

    for index, stop in enumerate(stops):
        local_km = local_mobility_km * float(stop.nights or (1 if stop.overnight else 0) or 0)
        if stop.overnight and local_km <= 0:
            local_km = local_mobility_km

        built = build_charging_plan(
            repo,
            origin_lat=current_lat,
            origin_lon=current_lon,
            soc_percent=current_soc,
            usable_capacity_kwh=usable_capacity_kwh,
            consumption_wh_per_km=consumption_wh_per_km,
            terrain_factor=terrain_factor,
            reserve_soc_percent=reserve_soc_percent,
            dest_lat=stop.lat,
            dest_lon=stop.lon,
            min_kw=min_kw,
            corridor_km=corridor_km,
            include_route=include_route,
            destination_radius_km=destination_radius_km,
            local_mobility_km=local_km if stop.overnight else max(5.0, local_mobility_km * 0.25),
            route_preference=route_preference,
            avoid_highways=avoid_highways,
            preferred_operators=preferred_operators,
            max_price_eur_kwh=max_price_eur_kwh,
            vehicle_preset_id=vehicle_preset_id,
            max_charge_power_kw=max_charge_power_kw,
            min_destination_soc_pct=min_destination_soc_pct,
            min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
            max_charge_soc_pct=max_charge_soc_pct,
            exclude_slow_chargers=exclude_slow_chargers,
            consumption_kwh_per_100km=consumption_kwh_per_100km,
        )
        plan = charging_plan_to_response(built)
        arrival = _arrival_soc(plan)
        departure_next, overnight_note = _departure_soc_after_stop(
            plan,
            overnight=stop.overnight,
            max_charge_soc_pct=max_charge_soc_pct,
        )
        if overnight_note:
            warnings.append(overnight_note)
        warnings.extend(plan.warnings)

        for planned in plan.planned_stops:
            global_order += 1
            all_stops.append(planned.model_copy(update={"order": global_order}))

        if plan.route_distance_km is not None:
            total_km += plan.route_distance_km
        if plan.route_duration_minutes is not None:
            total_drive += plan.route_duration_minutes
        total_charge += sum(s.charge_minutes for s in plan.planned_stops)

        leg_results.append(
            MultiLegPlanLegResult(
                order=index + 1,
                from_label=current_label,
                to_label=stop.label,
                overnight=stop.overnight,
                nights=stop.nights,
                departure_soc_pct=round(current_soc, 1),
                arrival_soc_pct=round(arrival, 1),
                next_departure_soc_pct=round(departure_next, 1) if index < len(stops) - 1 else None,
                plan=plan,
            )
        )

        current_lat, current_lon = stop.lat, stop.lon
        current_label = stop.label
        current_soc = departure_next

    aggregate = MultiLegAggregate(
        total_route_km=round(total_km, 1),
        total_driving_minutes=round(total_drive, 1),
        total_charge_minutes=round(total_charge, 1),
        final_soc_pct=round(_arrival_soc(leg_results[-1].plan), 1) if leg_results else None,
        all_planned_stops=all_stops,
        origin=RouteEndpoint(lat=origin_lat, lon=origin_lon),
        final_destination=RouteEndpoint(lat=stops[-1].lat, lon=stops[-1].lon),
    )

    summary_parts = [
        f"{len(leg_results)} tramo{'s' if len(leg_results) != 1 else ''}",
        f"~{aggregate.total_route_km:.0f} km",
        f"~{aggregate.total_driving_minutes:.0f} min conducción",
    ]
    if aggregate.total_charge_minutes:
        summary_parts.append(f"~{aggregate.total_charge_minutes:.0f} min carga")

    return MultiLegChargingPlanResponse(
        legs=leg_results,
        aggregate=aggregate,
        warnings=warnings,
        agent_summary=" · ".join(summary_parts),
        agent_bullets=[
            f"Tramo {leg.order}: {leg.from_label} → {leg.to_label}"
            + (f" (pernocta{f' {leg.nights}n' if leg.nights else ''})" if leg.overnight else "")
            + f" · salida {leg.departure_soc_pct:.0f}% → llegada {leg.arrival_soc_pct:.0f}%"
            for leg in leg_results
        ],
    )
