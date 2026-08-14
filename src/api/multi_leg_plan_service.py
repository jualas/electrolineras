"""Plan de carga multi-pierna: encadena build_charging_plan con SOC y pernoctas."""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

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
from api.routing.trip_metrics import format_duration_minutes
from db.repository import StationRepository

MAX_LEGS = 5
# Último hito cerca del origen → se trata como regreso a casa (forzar pernocta previa).
RETURN_HOME_RADIUS_KM = 20.0
# Overnight: en destino o desplazamiento corto en coche (no a 10 km).
# ≤1 km ≈ andando; hasta 3 km ≈ mover el coche al cargador y dejarlo.
OVERNIGHT_ONSITE_MAX_KM = 3.0
# Sin overnight: llegar con SOC para salir y alcanzar un cargador rápido en ~80–100 km.
NO_OVERNIGHT_FIRST_CHARGER_KM = 90.0
NO_OVERNIGHT_MIN_DEPARTURE_SOC = 40.0
NO_OVERNIGHT_MAX_ARRIVAL_SOC = 50.0  # tope del schema min_destination_soc_pct
_NOISE_WARNING_SNIPPETS = (
    "Sin paradas en ruta agotarías",
    "Ruta larga (",
    "Planifica al menos",
    "Plan optimizado:",
    "Pernocta activada",
    "pausas ~",
)


@dataclass(frozen=True)
class MultiLegStopInput:
    lat: float
    lon: float
    label: str
    overnight: bool = False
    nights: int | None = None


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def apply_return_home_overnight(
    stops: list[MultiLegStopInput],
    *,
    origin_lat: float,
    origin_lon: float,
) -> tuple[list[MultiLegStopInput], list[str]]:
    """Si el último hito es regreso a casa, marca pernocta en los destinos intermedios."""
    if len(stops) < 2:
        return stops, []
    last = stops[-1]
    if _haversine_km(last.lat, last.lon, origin_lat, origin_lon) > RETURN_HOME_RADIUS_KM:
        return stops, []
    notes: list[str] = []
    updated: list[MultiLegStopInput] = []
    for index, stop in enumerate(stops):
        if index >= len(stops) - 1:
            updated.append(stop)
            continue
        if stop.overnight:
            updated.append(stop)
            continue
        updated.append(replace(stop, overnight=True, nights=stop.nights or 1))
    return updated, notes


def _arrival_soc(plan: ChargingPlanResponse) -> float:
    if plan.projected_soc_at_destination_with_plan is not None:
        return float(plan.projected_soc_at_destination_with_plan)
    if plan.soc_at_destination_pct is not None:
        return float(plan.soc_at_destination_pct)
    return 10.0


def _nearest_destination_charger_km(plan: ChargingPlanResponse) -> float | None:
    stay = plan.destination_stay
    if stay is None:
        return None
    if stay.bands.nearest_km is not None:
        return float(stay.bands.nearest_km)
    if stay.nearest_chargers:
        return min(float(c.distance_km) for c in stay.nearest_chargers)
    return None


def _can_assume_overnight_charge(plan: ChargingPlanResponse) -> tuple[bool, float | None]:
    """Solo si hay cargadores en el propio destino (radio andando), no a varios km."""
    stay = plan.destination_stay
    if stay is None or stay.bands.total == 0 or stay.infrastructure_level == "none":
        return False, None
    nearest = _nearest_destination_charger_km(plan)
    if nearest is None:
        return False, None
    return nearest <= OVERNIGHT_ONSITE_MAX_KM, nearest


def _departure_soc_after_stop(
    plan: ChargingPlanResponse,
    *,
    overnight: bool,
    max_charge_soc_pct: float,
) -> tuple[float, str | None]:
    arrival = _arrival_soc(plan)
    if not overnight:
        return arrival, None
    can_charge, nearest = _can_assume_overnight_charge(plan)
    if not can_charge:
        if nearest is None:
            return arrival, (
                f"Pernocta: sin cargador en el destino; salida ~{arrival:.0f} % (sin asumir overnight)."
            )
        return arrival, (
            f"Pernocta: cargador más cercano a ~{nearest:.1f} km "
            f"(>{OVERNIGHT_ONSITE_MAX_KM:g} km); no se asume overnight. Salida ~{arrival:.0f} %."
        )
    target = max(arrival, min(float(max_charge_soc_pct), 90.0))
    if nearest is not None and nearest > 1.0:
        note = (
            f"Pernocta: carga overnight hasta ~{target:.0f} % "
            f"(habrá que desplazar el coche ~{nearest:.1f} km al cargador)."
        )
    else:
        note = (
            f"Pernocta: carga overnight hasta ~{target:.0f} % "
            f"(cargador a ~{(nearest or 0):.1f} km del destino)."
        )
    return target, note


def _compact_multi_leg_warnings(warnings: list[str], *, limit: int = 6) -> list[str]:
    """Quita ruido repetido del planificador y deja avisos accionables."""
    seen: set[str] = set()
    compact: list[str] = []
    for warning in warnings:
        text = warning.strip()
        if not text or text in seen:
            continue
        if any(snippet in text for snippet in _NOISE_WARNING_SNIPPETS):
            continue
        seen.add(text)
        compact.append(text)
        if len(compact) >= limit:
            break
    return compact


def required_arrival_soc_without_overnight(
    *,
    usable_capacity_kwh: float,
    consumption_wh_per_km: float,
    terrain_factor: float = 1.0,
    reserve_soc_percent: float = 10.0,
    min_destination_soc_pct: float = 10.0,
    first_charger_km: float = NO_OVERNIGHT_FIRST_CHARGER_KM,
) -> float:
    """SOC mínimo al llegar (y salir) si no hay overnight: margen hasta el 1.er cargador."""
    if usable_capacity_kwh <= 0:
        return min(NO_OVERNIGHT_MAX_ARRIVAL_SOC, max(NO_OVERNIGHT_MIN_DEPARTURE_SOC, min_destination_soc_pct))
    consumption_kwh_per_km = (consumption_wh_per_km * terrain_factor) / 1000.0
    soc_for_reach = (first_charger_km * consumption_kwh_per_km / usable_capacity_kwh) * 100.0
    needed = reserve_soc_percent + soc_for_reach + 5.0
    return min(
        NO_OVERNIGHT_MAX_ARRIVAL_SOC,
        max(NO_OVERNIGHT_MIN_DEPARTURE_SOC, min_destination_soc_pct, needed),
    )


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

    stops, _overnight_notes = apply_return_home_overnight(
        stops,
        origin_lat=origin_lat,
        origin_lon=origin_lon,
    )
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
        has_next_leg = index < len(stops) - 1

        def _build_leg(dest_soc_floor: float):
            return build_charging_plan(
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
                min_destination_soc_pct=dest_soc_floor,
                min_stop_arrival_soc_pct=min_stop_arrival_soc_pct,
                max_charge_soc_pct=max_charge_soc_pct,
                exclude_slow_chargers=exclude_slow_chargers,
                consumption_kwh_per_100km=consumption_kwh_per_100km,
            )

        built = _build_leg(min_destination_soc_pct)
        plan = charging_plan_to_response(built)
        arrival = _arrival_soc(plan)
        can_overnight, nearest_charger_km = (
            _can_assume_overnight_charge(plan) if stop.overnight else (False, None)
        )
        raised_arrival_for_return = False

        # Sin overnight en destino + hay vuelta: cargar más antes de llegar
        # para salir con margen hasta el siguiente cargador rápido.
        if stop.overnight and has_next_leg and not can_overnight:
            required = required_arrival_soc_without_overnight(
                usable_capacity_kwh=usable_capacity_kwh,
                consumption_wh_per_km=consumption_wh_per_km,
                terrain_factor=terrain_factor,
                reserve_soc_percent=reserve_soc_percent,
                min_destination_soc_pct=min_destination_soc_pct,
            )
            if arrival + 1.0 < required:
                built = _build_leg(required)
                plan = charging_plan_to_response(built)
                arrival = _arrival_soc(plan)
                raised_arrival_for_return = True
                dist_note = (
                    f" (cargador a ~{nearest_charger_km:.1f} km)"
                    if nearest_charger_km is not None
                    else ""
                )
                warnings.append(
                    f"Sin overnight fiable en «{stop.label}»{dist_note}: "
                    f"carga antes de llegar para entrar con ≥{required:.0f} % "
                    f"y poder salir hacia un cargador en la vuelta."
                )

        departure_next, overnight_note = _departure_soc_after_stop(
            plan,
            overnight=stop.overnight,
            max_charge_soc_pct=max_charge_soc_pct,
        )
        if overnight_note and not raised_arrival_for_return:
            warnings.append(overnight_note)
        # Solo avisos accionables del tramo (no el muro de «ruta larga / sin paradas…»).
        for warning in plan.warnings:
            if any(snippet in warning for snippet in _NOISE_WARNING_SNIPPETS):
                continue
            if "recomendamos" in warning.lower() or "no se asume" in warning.lower():
                warnings.append(warning)
            elif "emergencia" in warning.lower() or "antes de lo ideal" in warning.lower():
                warnings.append(warning)
            elif "no hay cargador" in warning.lower() or "ningún cargador" in warning.lower():
                warnings.append(warning)

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

    drive_total = format_duration_minutes(aggregate.total_driving_minutes)
    charge_total = format_duration_minutes(aggregate.total_charge_minutes)
    summary_parts = [
        f"{len(leg_results)} tramo{'s' if len(leg_results) != 1 else ''}",
        f"~{aggregate.total_route_km:.0f} km",
    ]
    if drive_total:
        summary_parts.append(f"~{drive_total} conducción (suma tramos)")
    if charge_total:
        summary_parts.append(f"~{charge_total} carga")

    leg_bullets: list[str] = []
    for leg in leg_results:
        drive = format_duration_minutes(leg.plan.route_duration_minutes)
        km = leg.plan.route_distance_km
        parts = [
            f"Tramo {leg.order}: {leg.from_label} → {leg.to_label}",
        ]
        if leg.overnight:
            parts[0] += f" (pernocta{f' {leg.nights}n' if leg.nights else ''})"
        if km is not None:
            parts.append(f"~{km:.0f} km")
        if drive:
            parts.append(f"~{drive} conducción")
        parts.append(f"salida {leg.departure_soc_pct:.0f}% → llegada {leg.arrival_soc_pct:.0f}%")
        leg_bullets.append(" · ".join(parts))

    return MultiLegChargingPlanResponse(
        legs=leg_results,
        aggregate=aggregate,
        warnings=_compact_multi_leg_warnings(warnings),
        agent_summary=" · ".join(summary_parts),
        agent_bullets=leg_bullets,
    )
