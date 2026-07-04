from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from api.routing.charging_preferences import (
    STRATEGY_PREFERRED_OPERATOR,
    ChargingPreferences,
    operator_matches,
    rank_stop_tuple,
)
from api.routing.corridor import CorridorMatch
from api.routing.dc_charge_curve import estimate_dc_charge_minutes
from models.station import Station

ChargingClassification = Literal["safe", "adjusted", "critical", "unreachable"]

CLASSIFICATION_ORDER: dict[ChargingClassification, int] = {
    "safe": 0,
    "adjusted": 1,
    "critical": 2,
    "unreachable": 3,
}

STRATEGY_CHARGE_NOW = "charge_now"
STRATEGY_CHARGE_AT_ORIGIN = "charge_at_origin"
STRATEGY_NEXT_SAFE = "next_safe"
STRATEGY_BEST_VALUE = "best_value"

# SOC mínimo al llegar a un cargador (llegar con 5 % = crítico pero alcanzable).
CHARGING_MIN_ARRIVAL_SOC_PCT = 5.0


@dataclass(frozen=True)
class VehicleEnergyProfile:
    soc_percent: float
    usable_capacity_kwh: float
    consumption_wh_per_km: float
    terrain_factor: float = 1.0
    reserve_soc_percent: float = 10.0
    vehicle_preset_id: str | None = None


@dataclass(frozen=True)
class ScoredChargingStop:
    station: Station
    deviation_km: float
    route_distance_km: float
    extra_minutes: float
    wrong_side: bool
    distance_from_origin_km: float
    soc_arrival_pct: float
    classification: ChargingClassification


@dataclass(frozen=True)
class ChargingStrategyOption:
    id: str
    label: str
    station_id: str | None
    soc_arrival_pct: float | None
    classification: ChargingClassification | None
    summary: str


@dataclass(frozen=True)
class PlannedRouteStop:
    order: int
    station: Station
    deviation_km: float
    route_distance_km: float
    extra_minutes: float
    wrong_side: bool
    distance_from_origin_km: float
    leg_distance_km: float
    soc_arrival_pct: float
    soc_departure_pct: float
    charge_minutes: float
    classification: ChargingClassification


@dataclass(frozen=True)
class ChargingPlanComputation:
    range_km: float
    charging_reach_km: float
    soc_at_destination_pct: float | None
    reachable_without_stop: bool
    stops: list[ScoredChargingStop]
    origin_stops: list[ScoredChargingStop]
    strategies: list[ChargingStrategyOption]
    warnings: list[str]
    planned_stops: list[PlannedRouteStop] = field(default_factory=list)
    projected_soc_at_destination_with_plan: float | None = None


def effective_consumption_wh_per_km(profile: VehicleEnergyProfile) -> float:
    return profile.consumption_wh_per_km * profile.terrain_factor


def available_energy_kwh(profile: VehicleEnergyProfile, floor_soc_percent: float | None = None) -> float:
    floor = floor_soc_percent if floor_soc_percent is not None else profile.reserve_soc_percent
    usable_soc = max(0.0, profile.soc_percent - floor)
    return profile.usable_capacity_kwh * usable_soc / 100.0


def estimate_range_km(profile: VehicleEnergyProfile) -> float:
    """Autonomía con reserva de planificación (llegar al destino sin cargar)."""
    consumption_kwh_per_km = effective_consumption_wh_per_km(profile) / 1000.0
    if consumption_kwh_per_km <= 0:
        return 0.0
    return available_energy_kwh(profile) / consumption_kwh_per_km


def estimate_charging_reach_km(
    profile: VehicleEnergyProfile,
    min_arrival_soc_pct: float = CHARGING_MIN_ARRIVAL_SOC_PCT,
) -> float:
    """Distancia máxima hasta un cargador (llegada ≥ min_arrival_soc_pct, p. ej. 5 %)."""
    consumption_kwh_per_km = effective_consumption_wh_per_km(profile) / 1000.0
    if consumption_kwh_per_km <= 0:
        return 0.0
    energy = available_energy_kwh(profile, floor_soc_percent=min_arrival_soc_pct)
    return energy / consumption_kwh_per_km


def soc_at_distance_km(profile: VehicleEnergyProfile, distance_km: float) -> float:
    if profile.usable_capacity_kwh <= 0:
        return 0.0
    energy_used_kwh = distance_km * effective_consumption_wh_per_km(profile) / 1000.0
    soc_drop = (energy_used_kwh / profile.usable_capacity_kwh) * 100.0
    return profile.soc_percent - soc_drop


def clamp_display_soc_pct(soc_pct: float) -> float:
    return max(0.0, min(100.0, soc_pct))


def estimate_charging_stops_needed(distance_km: float, range_km: float) -> int:
    if range_km <= 0 or distance_km <= range_km + 1e-6:
        return 0
    return max(1, math.ceil(distance_km / range_km) - 1)


def classify_soc_arrival(
    soc_arrival_pct: float,
    *,
    within_range: bool,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
) -> ChargingClassification:
    if not within_range:
        return "unreachable"
    if soc_arrival_pct >= safe_margin_pct:
        return "safe"
    if soc_arrival_pct >= adjusted_min_pct:
        return "adjusted"
    return "critical"


def _stop_from_corridor_match(
    match: CorridorMatch,
    *,
    origin_position_km: float,
    profile: VehicleEnergyProfile,
    charging_reach_km: float,
    safe_margin_pct: float,
    adjusted_min_pct: float,
) -> ScoredChargingStop:
    distance_from_origin_km = max(0.0, match.route_position_m / 1000.0 - origin_position_km)
    soc_raw = soc_at_distance_km(profile, distance_from_origin_km)
    within_range = distance_from_origin_km <= charging_reach_km + 1e-6
    classification = classify_soc_arrival(
        soc_raw,
        within_range=within_range,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
    )
    soc_arrival_pct = round(clamp_display_soc_pct(soc_raw), 1)
    return ScoredChargingStop(
        station=match.station,
        deviation_km=round(match.deviation_m / 1000.0, 2),
        route_distance_km=round(match.route_position_m / 1000.0, 2),
        extra_minutes=round(match.extra_minutes, 1),
        wrong_side=match.wrong_side,
        distance_from_origin_km=round(distance_from_origin_km, 2),
        soc_arrival_pct=soc_arrival_pct,
        classification=classification,
    )


def _rank_key(
    stop: ScoredChargingStop,
    preferences: ChargingPreferences | None = None,
) -> tuple[float, float, float, float, float, float, float]:
    price = stop.station.dynamic_price_eur_kwh
    price_key = price if price is not None else 999.0
    status_penalty = 0.0
    if stop.station.dynamic_status == "occupied":
        status_penalty = 1.0
    elif stop.station.dynamic_status == "outofservice":
        status_penalty = 2.0
    return rank_stop_tuple(
        classification_order=float(CLASSIFICATION_ORDER[stop.classification]),
        deviation_km=stop.deviation_km,
        soc_arrival_pct=stop.soc_arrival_pct,
        status_penalty=status_penalty,
        price_key=price_key,
        station_operator=stop.station.operator,
        preferences=preferences,
    )


def _build_strategies(
    stops: list[ScoredChargingStop],
    *,
    origin_stops: list[ScoredChargingStop] | None = None,
    preferences: ChargingPreferences | None = None,
) -> list[ChargingStrategyOption]:
    viable = [stop for stop in stops if stop.classification != "unreachable"]
    origin_viable = [stop for stop in (origin_stops or []) if stop.classification != "unreachable"]
    strategies: list[ChargingStrategyOption] = []

    if origin_viable:
        closest_origin = min(origin_viable, key=lambda item: item.distance_from_origin_km)
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_CHARGE_AT_ORIGIN,
                label="Cargar desde la salida",
                station_id=closest_origin.station.id,
                soc_arrival_pct=closest_origin.soc_arrival_pct,
                classification=closest_origin.classification,
                summary=(
                    f"Más cercano a {closest_origin.distance_from_origin_km:.1f} km "
                    f"({closest_origin.soc_arrival_pct:.0f} % SOC estimado al llegar)."
                ),
            )
        )
    elif origin_stops:
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_CHARGE_AT_ORIGIN,
                label="Cargar desde la salida",
                station_id=None,
                soc_arrival_pct=None,
                classification=None,
                summary="No hay cargadores alcanzables cerca del punto de salida.",
            )
        )

    charge_now = min(viable, key=lambda stop: _rank_key(stop, preferences), default=None)
    if charge_now:
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_CHARGE_NOW,
                label="Cargar ya",
                station_id=charge_now.station.id,
                soc_arrival_pct=charge_now.soc_arrival_pct,
                classification=charge_now.classification,
                summary=(
                    f"Primera parada viable con {charge_now.soc_arrival_pct:.0f} % SOC estimado "
                    f"({charge_now.deviation_km:.1f} km de desvío)."
                ),
            )
        )
    else:
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_CHARGE_NOW,
                label="Cargar ya",
                station_id=None,
                soc_arrival_pct=None,
                classification=None,
                summary="No hay cargadores alcanzables con el SOC actual.",
            )
        )

    next_safe = next((stop for stop in stops if stop.classification == "safe"), None)
    if next_safe:
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_NEXT_SAFE,
                label="Siguiente parada segura",
                station_id=next_safe.station.id,
                soc_arrival_pct=next_safe.soc_arrival_pct,
                classification=next_safe.classification,
                summary=(
                    f"Primera parada con margen seguro ({next_safe.soc_arrival_pct:.0f} % SOC) "
                    f"a {next_safe.route_distance_km:.0f} km."
                ),
            )
        )
    else:
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_NEXT_SAFE,
                label="Siguiente parada segura",
                station_id=None,
                soc_arrival_pct=None,
                classification=None,
                summary="Ninguna parada deja un margen de SOC ≥ 15 %.",
            )
        )

    priced = [
        stop
        for stop in stops
        if stop.classification in {"safe", "adjusted"} and stop.station.dynamic_price_eur_kwh is not None
    ]
    best_value = min(
        priced,
        key=lambda item: (item.station.dynamic_price_eur_kwh or 999, _rank_key(item, preferences)),
        default=None,
    )
    if best_value and best_value.station.dynamic_price_eur_kwh is not None:
        strategies.append(
            ChargingStrategyOption(
                id=STRATEGY_BEST_VALUE,
                label="Mejor precio REVE",
                station_id=best_value.station.id,
                soc_arrival_pct=best_value.soc_arrival_pct,
                classification=best_value.classification,
                summary=(
                    f"{best_value.station.dynamic_price_eur_kwh:.2f} €/kWh · "
                    f"{best_value.soc_arrival_pct:.0f} % SOC estimado."
                ),
            )
        )
    else:
        fallback = next((stop for stop in viable if stop.classification in {"safe", "adjusted"}), charge_now)
        if fallback:
            strategies.append(
                ChargingStrategyOption(
                    id=STRATEGY_BEST_VALUE,
                    label="Mejor equilibrio",
                    station_id=fallback.station.id,
                    soc_arrival_pct=fallback.soc_arrival_pct,
                    classification=fallback.classification,
                    summary=(
                        f"Sin precio REVE; alternativa con {fallback.soc_arrival_pct:.0f} % SOC "
                        f"y {fallback.deviation_km:.1f} km de desvío."
                    ),
                )
            )
        else:
            strategies.append(
                ChargingStrategyOption(
                    id=STRATEGY_BEST_VALUE,
                    label="Mejor precio REVE",
                    station_id=None,
                    soc_arrival_pct=None,
                    classification=None,
                    summary="No hay paradas con precio REVE alcanzables.",
                )
            )

    prefs = preferences or ChargingPreferences()
    if prefs.preferred_operators:
        preferred_viable = [
            stop
            for stop in viable
            if operator_matches(stop.station.operator, prefs.preferred_operators)
        ]
        if preferred_viable:
            preferred_stop = min(preferred_viable, key=lambda stop: _rank_key(stop, preferences))
            operator_label = preferred_stop.station.operator or "operador preferido"
            strategies.append(
                ChargingStrategyOption(
                    id=STRATEGY_PREFERRED_OPERATOR,
                    label="Operador preferido",
                    station_id=preferred_stop.station.id,
                    soc_arrival_pct=preferred_stop.soc_arrival_pct,
                    classification=preferred_stop.classification,
                    summary=(
                        f"{operator_label} · {preferred_stop.soc_arrival_pct:.0f} % SOC · "
                        f"{preferred_stop.deviation_km:.1f} km de desvío."
                    ),
                )
            )
        else:
            labels = ", ".join(prefs.preferred_operators[:3])
            strategies.append(
                ChargingStrategyOption(
                    id=STRATEGY_PREFERRED_OPERATOR,
                    label="Operador preferido",
                    station_id=None,
                    soc_arrival_pct=None,
                    classification=None,
                    summary=f"Ninguna parada alcanzable de: {labels}.",
                )
            )

    return strategies


DEFAULT_CHARGE_TARGET_SOC_PCT = 80.0
DEFAULT_DESTINATION_TARGET_SOC_PCT = 30.0
MAX_PLANNED_ROUTE_STOPS = 8


def estimate_charge_minutes(
    arrival_soc_pct: float,
    departure_soc_pct: float,
    *,
    usable_capacity_kwh: float,
    max_power_kw: float,
    vehicle_preset_id: str | None = None,
) -> float:
    return estimate_dc_charge_minutes(
        arrival_soc_pct,
        departure_soc_pct,
        usable_capacity_kwh=usable_capacity_kwh,
        station_max_kw=max_power_kw,
        vehicle_preset_id=vehicle_preset_id,
    )


def _departure_soc_for_stop(
    *,
    arrival_soc_pct: float,
    remaining_km: float,
    profile: VehicleEnergyProfile,
    destination_target_soc_pct: float,
    charge_target_soc_pct: float,
    hops_remaining: int,
) -> float:
    if hops_remaining <= 1:
        soc_at_dest = soc_at_distance_km(
            VehicleEnergyProfile(
                soc_percent=arrival_soc_pct,
                usable_capacity_kwh=profile.usable_capacity_kwh,
                consumption_wh_per_km=profile.consumption_wh_per_km,
                terrain_factor=profile.terrain_factor,
                reserve_soc_percent=profile.reserve_soc_percent,
            ),
            remaining_km,
        )
        min_departure = arrival_soc_pct + max(0.0, destination_target_soc_pct - soc_at_dest)
        return min(100.0, max(min_departure, charge_target_soc_pct))
    return min(100.0, max(arrival_soc_pct + 5.0, charge_target_soc_pct))


def build_planned_route_stops(
    matches: list[CorridorMatch],
    *,
    origin_position_km: float,
    destination_distance_km: float,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    destination_target_soc_pct: float = DEFAULT_DESTINATION_TARGET_SOC_PCT,
    charge_target_soc_pct: float = DEFAULT_CHARGE_TARGET_SOC_PCT,
    max_stops: int = MAX_PLANNED_ROUTE_STOPS,
    preferences: ChargingPreferences | None = None,
) -> tuple[list[PlannedRouteStop], list[str], float | None]:
    distance_to_dest_km = max(0.0, destination_distance_km - origin_position_km)
    if distance_to_dest_km <= estimate_range_km(profile) + 1e-6:
        return [], [], round(clamp_display_soc_pct(soc_at_distance_km(profile, distance_to_dest_km)), 1)

    warnings: list[str] = []
    planned: list[PlannedRouteStop] = []
    used_station_ids: set[str] = set()
    current_route_km = origin_position_km
    current_soc = profile.soc_percent
    previous_route_km = origin_position_km

    for _attempt in range(max_stops):
        remaining_km = max(0.0, destination_distance_km - current_route_km)
        segment_profile = VehicleEnergyProfile(
            soc_percent=current_soc,
            usable_capacity_kwh=profile.usable_capacity_kwh,
            consumption_wh_per_km=profile.consumption_wh_per_km,
            terrain_factor=profile.terrain_factor,
            reserve_soc_percent=profile.reserve_soc_percent,
        )
        segment_range_km = estimate_range_km(segment_profile)
        if remaining_km <= segment_range_km + 1e-6:
            projected = soc_at_distance_km(segment_profile, remaining_km)
            return planned, warnings, round(clamp_display_soc_pct(projected), 1)

        charging_reach_km = estimate_charging_reach_km(segment_profile)
        segment_end_km = current_route_km + charging_reach_km
        segment_matches = [
            match
            for match in matches
            if match.station.id not in used_station_ids
            and current_route_km < (match.route_position_m / 1000.0) <= segment_end_km + 1e-6
        ]
        if not segment_matches:
            warnings.append(
                f"No hay cargador alcanzable en el tramo ~{current_route_km:.0f}–{segment_end_km:.0f} km "
                f"(SOC {current_soc:.0f} %)."
            )
            break

        scored = [
            _stop_from_corridor_match(
                match,
                origin_position_km=current_route_km,
                profile=segment_profile,
                charging_reach_km=charging_reach_km,
                safe_margin_pct=safe_margin_pct,
                adjusted_min_pct=adjusted_min_pct,
            )
            for match in segment_matches
        ]
        viable = [stop for stop in scored if stop.classification != "unreachable"]
        if not viable:
            warnings.append(
                f"Ningún cargador viable en el tramo ~{current_route_km:.0f}–{segment_end_km:.0f} km."
            )
            break

        chosen = min(viable, key=lambda stop: _rank_key(stop, preferences))
        stop_route_km = chosen.route_distance_km
        leg_distance_km = max(0.0, stop_route_km - previous_route_km)
        hops_remaining = estimate_charging_stops_needed(remaining_km, segment_range_km)
        departure_soc = _departure_soc_for_stop(
            arrival_soc_pct=chosen.soc_arrival_pct,
            remaining_km=max(0.0, destination_distance_km - stop_route_km),
            profile=profile,
            destination_target_soc_pct=destination_target_soc_pct,
            charge_target_soc_pct=charge_target_soc_pct,
            hops_remaining=hops_remaining,
        )
        charge_minutes = estimate_charge_minutes(
            chosen.soc_arrival_pct,
            departure_soc,
            usable_capacity_kwh=profile.usable_capacity_kwh,
            max_power_kw=chosen.station.max_power_kw,
            vehicle_preset_id=profile.vehicle_preset_id,
        )
        planned.append(
            PlannedRouteStop(
                order=len(planned) + 1,
                station=chosen.station,
                deviation_km=chosen.deviation_km,
                route_distance_km=chosen.route_distance_km,
                extra_minutes=chosen.extra_minutes,
                wrong_side=chosen.wrong_side,
                distance_from_origin_km=chosen.distance_from_origin_km,
                leg_distance_km=round(leg_distance_km, 2),
                soc_arrival_pct=chosen.soc_arrival_pct,
                soc_departure_pct=round(departure_soc, 1),
                charge_minutes=charge_minutes,
                classification=chosen.classification,
            )
        )
        used_station_ids.add(chosen.station.id)
        previous_route_km = stop_route_km
        current_route_km = stop_route_km
        current_soc = departure_soc

    if planned:
        final_profile = VehicleEnergyProfile(
            soc_percent=current_soc,
            usable_capacity_kwh=profile.usable_capacity_kwh,
            consumption_wh_per_km=profile.consumption_wh_per_km,
            terrain_factor=profile.terrain_factor,
            reserve_soc_percent=profile.reserve_soc_percent,
        )
        projected = soc_at_distance_km(final_profile, max(0.0, destination_distance_km - current_route_km))
        projected_clamped = round(clamp_display_soc_pct(projected), 1)
        if projected < destination_target_soc_pct:
            warnings.append(
                f"Con {len(planned)} parada(s) planificada(s) llegarías con ~{projected_clamped:.0f} % "
                f"(objetivo {destination_target_soc_pct:.0f} %)."
            )
        return planned, warnings, projected_clamped

    return planned, warnings, None


def build_route_charging_plan(
    matches: list[CorridorMatch],
    *,
    origin_position_km: float,
    destination_distance_km: float,
    profile: VehicleEnergyProfile,
    origin_stops: list[ScoredChargingStop] | None = None,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    limit: int = 20,
    preferences: ChargingPreferences | None = None,
) -> ChargingPlanComputation:
    range_km = estimate_range_km(profile)
    charging_reach_km = estimate_charging_reach_km(profile)
    stops = [
        _stop_from_corridor_match(
            match,
            origin_position_km=origin_position_km,
            profile=profile,
            charging_reach_km=charging_reach_km,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
        )
        for match in matches
    ]
    stops.sort(key=lambda stop: _rank_key(stop, preferences))
    stops = stops[:limit]

    resolved_origin_stops = origin_stops or []
    viable = [stop for stop in stops if stop.classification != "unreachable"]
    origin_viable = [stop for stop in resolved_origin_stops if stop.classification != "unreachable"]

    distance_to_dest_km = max(0.0, destination_distance_km - origin_position_km)
    soc_raw_at_dest = soc_at_distance_km(profile, distance_to_dest_km)
    soc_at_destination_pct = round(clamp_display_soc_pct(soc_raw_at_dest), 1)
    reachable_without_stop = (
        distance_to_dest_km <= range_km + 1e-6 and soc_raw_at_dest >= profile.reserve_soc_percent
    )

    warnings: list[str] = []
    if distance_to_dest_km > range_km + 1e-6:
        stops_needed = estimate_charging_stops_needed(distance_to_dest_km, range_km)
        warnings.append(
            f"Ruta larga ({distance_to_dest_km:.0f} km): autonomía sin parar ~{range_km:.0f} km. "
            f"Planifica al menos {stops_needed} parada(s) de carga en ruta."
        )
    if soc_raw_at_dest < profile.reserve_soc_percent and distance_to_dest_km > range_km + 1e-6:
        warnings.append(
            "Sin paradas en ruta agotarías la batería antes del destino."
        )
    if not reachable_without_stop and not any(stop.classification == "safe" for stop in stops):
        warnings.append("No hay paradas seguras en la ruta antes de agotar autonomía.")
    if any(stop.classification == "critical" for stop in stops[:3]):
        warnings.append("Las primeras opciones en ruta llegan con SOC crítico (< 10 %).")
    if soc_at_destination_pct < profile.reserve_soc_percent and not stops and not resolved_origin_stops:
        warnings.append("No hay cargadores en corredor ni cerca del origen dentro de tu autonomía.")
    elif soc_at_destination_pct < profile.reserve_soc_percent and not viable and origin_viable:
        warnings.append(
            "No alcanzas cargadores en la ruta; carga primero en un punto cercano a tu salida."
        )

    planned_stops, planned_warnings, projected_with_plan = build_planned_route_stops(
        matches,
        origin_position_km=origin_position_km,
        destination_distance_km=destination_distance_km,
        profile=profile,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        preferences=preferences,
    )
    warnings.extend(planned_warnings)

    return ChargingPlanComputation(
        range_km=round(range_km, 1),
        charging_reach_km=round(charging_reach_km, 1),
        soc_at_destination_pct=soc_at_destination_pct,
        reachable_without_stop=reachable_without_stop,
        stops=stops,
        origin_stops=resolved_origin_stops,
        strategies=_build_strategies(
            stops,
            origin_stops=resolved_origin_stops,
            preferences=preferences,
        ),
        warnings=warnings,
        planned_stops=planned_stops,
        projected_soc_at_destination_with_plan=projected_with_plan,
    )


def build_emergency_charging_plan(
    stations: list[tuple[Station, float]],
    *,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    limit: int = 10,
    preferences: ChargingPreferences | None = None,
) -> ChargingPlanComputation:
    range_km = estimate_range_km(profile)
    charging_reach_km = estimate_charging_reach_km(profile)
    stops: list[ScoredChargingStop] = []

    for station, distance_km in stations:
        soc_raw = soc_at_distance_km(profile, distance_km)
        within_range = distance_km <= charging_reach_km + 1e-6
        classification = classify_soc_arrival(
            soc_raw,
            within_range=within_range,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
        )
        soc_arrival_pct = round(clamp_display_soc_pct(soc_raw), 1)
        stops.append(
            ScoredChargingStop(
                station=station,
                deviation_km=round(distance_km, 2),
                route_distance_km=round(distance_km, 2),
                extra_minutes=0.0,
                wrong_side=False,
                distance_from_origin_km=round(distance_km, 2),
                soc_arrival_pct=soc_arrival_pct,
                classification=classification,
            )
        )

    stops.sort(key=lambda stop: _rank_key(stop, preferences))
    stops = stops[:limit]

    warnings: list[str] = []
    if not any(stop.classification != "unreachable" for stop in stops):
        warnings.append("No hay cargadores alcanzables desde tu posición.")
        if stops:
            closest = stops[0]
            warnings.append(
                f"El más cercano está a {closest.distance_from_origin_km:.1f} km "
                f"(alcance hasta cargador {charging_reach_km:.1f} km)."
            )

    return ChargingPlanComputation(
        range_km=round(range_km, 1),
        charging_reach_km=round(charging_reach_km, 1),
        soc_at_destination_pct=None,
        reachable_without_stop=False,
        stops=stops,
        origin_stops=stops,
        strategies=_build_strategies([], origin_stops=stops, preferences=preferences),
        warnings=warnings,
    )
