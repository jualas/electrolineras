from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Literal

from api.routing.charging_preferences import (
    STRATEGY_PREFERRED_OPERATOR,
    ChargingPreferences,
    on_route_operator_rank,
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
# Si la 1.ª parada tras exclusión ~2 h llega por debajo, relajar (Hellín vs Albacete).
FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT = 20.0


@dataclass(frozen=True)
class VehicleEnergyProfile:
    soc_percent: float
    usable_capacity_kwh: float
    consumption_wh_per_km: float
    terrain_factor: float = 1.0
    reserve_soc_percent: float = 10.0
    vehicle_preset_id: str | None = None
    # Parámetros estilo REVE (planificación multi-parada)
    max_charge_power_kw: float = 100.0
    min_destination_soc_pct: float = 10.0
    min_stop_arrival_soc_pct: float = 10.0
    max_charge_soc_pct: float = 80.0


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
    leg_driving_minutes: float
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
) -> tuple[float, ...]:
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
DEFAULT_DESTINATION_TARGET_SOC_PCT = 10.0
MAX_PLANNED_ROUTE_STOPS = 8

# DGT: pausa recomendada ~2–2:30 h; máximo ~3 h por confort fisiológico.
TARGET_DRIVING_LEG_MINUTES = 135.0
MAX_DRIVING_LEG_MINUTES = 180.0
DEFAULT_AVG_SPEED_KMH = 90.0
INTERMEDIATE_ARRIVAL_SOC_TARGET = 10.0
DEPARTURE_SOC_BUFFER_PCT = 3.0
# Techo DC rápido (UI REVE max_charge_soc); no implica cargar siempre hasta aquí.
OPTIMAL_CHARGE_CEILING_SOC_PCT = 80.0
# Punto dulce Tesla/REVE: 10→60-70 % minimiza tiempo total (curva DC LFP/NMC).
INTERMEDIATE_OPTIMAL_CHARGE_SOC_PCT = 65.0
# Primer tramo desde SOC alto: mismo objetivo ~2–2:30 h (no estirar a 3 h;
# si no, la 2.ª parada queda a ~1–1:30 h por alcance de batería).
FIRST_LEG_FULL_SOC_THRESHOLD_PCT = 95.0
FIRST_LEG_DRIVING_MINUTES = TARGET_DRIVING_LEG_MINUTES
MIN_MEANINGFUL_CHARGE_MINUTES = 8.0
MIN_WORTHWHILE_CHARGE_MINUTES = 12.0
MIN_WORTHWHILE_SOC_GAIN_PCT = 10.0
HIGH_ARRIVAL_MICRO_STOP_SOC_PCT = 45.0
MICRO_STOP_SHORT_CHARGE_ARRIVAL_SOC_PCT = 44.0
MIN_FORWARD_PROGRESS_KM = 5.0
# Con SOC ≤10 % permitir 1.ª parada a pocos metros/km del origen (#6157).
ORIGIN_ZONE_MIN_FORWARD_KM = 0.3
DEVIATION_PENALTY_KM_BUCKET = 5.0
MIN_LEG_PROGRESS_FRACTION = 0.85
HIGHWAY_MIN_LEG_PROGRESS_FRACTION = 0.90
# Un tramo cuenta como «suficientemente largo» vs el mínimo de segmento.
MIN_LEG_ACCEPT_FRACTION = 0.90
HIGH_SOC_SKIP_ORIGIN_FRACTION = 0.75
# Por debajo de este SOC se permite cargar junto al punto de salida antes de iniciar el viaje.
ORIGIN_CHARGE_SOC_THRESHOLD_PCT = 10.0
MIN_ORIGIN_SKIP_ABSOLUTE_KM = 40.0
ON_ROUTE_DEVIATION_KM = 2.0
PREFERRED_ON_ROUTE_TIME_BONUS_MIN = 8.0


def min_leg_progress_fraction(route_preference: str | None = None) -> float:
    """Fracción mínima del tramo ideal antes de permitir una parada."""
    if route_preference in {"fastest", "shortest"}:
        return HIGHWAY_MIN_LEG_PROGRESS_FRACTION
    return MIN_LEG_PROGRESS_FRACTION


def asymmetric_distance_to_target_km(stop_km: float, target_stop_km: float) -> float:
    """Penaliza más llegar demasiado pronto que un poco tarde al target ~2–2:30 h."""
    delta = stop_km - target_stop_km
    if delta < 0:
        return abs(delta) * 1.5
    return delta


def allows_origin_zone_charging(trip_start_soc_pct: float) -> bool:
    """True si conviene cargar junto a la salida (SOC ≤ umbral, p. ej. 10 %)."""
    return trip_start_soc_pct <= ORIGIN_CHARGE_SOC_THRESHOLD_PCT + 1e-6


def origin_exclusion_radius_km(
    target_leg_km: float,
    trip_start_soc_pct: float,
    *,
    charging_reach_km: float | None = None,
    max_leg_km: float | None = None,
) -> float:
    """Distancia mínima desde la salida antes de la 1.ª parada (≈2 h DGT si SOC >10 %)."""
    if allows_origin_zone_charging(trip_start_soc_pct):
        return 0.0
    exclusion = max(MIN_ORIGIN_SKIP_ABSOLUTE_KM, target_leg_km * MIN_LEG_ACCEPT_FRACTION)
    if charging_reach_km is not None and charging_reach_km > 0:
        # No exigir parada más lejos de lo que la batería puede alcanzar (TeslaMate / alto consumo).
        max_exclusion = max(0.0, charging_reach_km - 30.0)
        exclusion = min(exclusion, max_exclusion)
    if max_leg_km is not None and max_leg_km > 0:
        # Dejar ventana de candidatos antes del techo de 3 h (rutas lentas / shortest).
        exclusion = min(exclusion, max_leg_km * MIN_LEG_ACCEPT_FRACTION)
    return exclusion


def relaxed_origin_exclusion_km(origin_exclusion_km: float) -> float:
    """Exclusión mínima si la ventana [~2 h, alcance] no tiene cargadores (#6151).

    En ruta «rápida» la exclusión ~2 h puede superar el alcance útil con SOC medio;
    sin relajar, el plan queda vacío mientras «directa» (más lenta) sí encuentra paradas.
    """
    if origin_exclusion_km <= MIN_ORIGIN_SKIP_ABSOLUTE_KM + 1e-6:
        return 0.0
    return MIN_ORIGIN_SKIP_ABSOLUTE_KM


def first_stop_comfort_matches(
    matches: list[CorridorMatch],
    *,
    current_route_km: float,
    profile: VehicleEnergyProfile,
) -> list[CorridorMatch]:
    """Candidatos de 1.ª parada con llegada ≥ confort (~20 %).

    No usar min(llegadas) sobre la ventana ampliada: el crítico (Albacete) sigue dentro
    y el min no mejora aunque exista Hellín cómodo.
    """
    comfort: list[CorridorMatch] = []
    for match in matches:
        leg_km = max(0.0, (match.route_position_m / 1000.0) - current_route_km)
        arrival = soc_at_distance_km(profile, leg_km)
        if arrival + 1e-6 >= FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT:
            comfort.append(match)
    return comfort


def hop_min_forward_km(*, trip_start_soc_pct: float, is_first_hop: bool) -> float:
    """Avance mínimo en ruta: casi 0 si SOC≤10 % en la 1.ª parada (#6157 / batería-primero)."""
    if is_first_hop and allows_origin_zone_charging(trip_start_soc_pct):
        return ORIGIN_ZONE_MIN_FORWARD_KM
    return MIN_FORWARD_PROGRESS_KM


def reachable_segment_candidates(
    matches: list[CorridorMatch],
    *,
    current_route_km: float,
    charging_reach_km: float,
    used_station_ids: set[str],
    min_forward_km: float,
    remaining_km: float,
) -> tuple[list[CorridorMatch], float, float]:
    """Ventana batería-primero: cargadores en (current + min_forward, current + reach].

    Sin exclusión DGT dura. El espaciado ~2 h solo afecta al ranking posterior.
    Devuelve (candidatos, segment_min_km, segment_end_km).
    """
    segment_min_km = current_route_km + max(0.0, min_forward_km)
    segment_end_km = current_route_km + min(max(0.0, charging_reach_km), max(0.0, remaining_km))
    if segment_end_km <= current_route_km + 1e-6:
        return [], segment_min_km, segment_end_km
    candidates = [
        match
        for match in matches
        if match.station.id not in used_station_ids
        and current_route_km < (match.route_position_m / 1000.0) <= segment_end_km + 1e-6
        and (match.route_position_m / 1000.0) >= segment_min_km - 1e-6
    ]
    return candidates, segment_min_km, segment_end_km


def preferred_stop_target_km(
    *,
    current_route_km: float,
    charging_reach_km: float,
    remaining_km: float,
    target_leg_km: float,
    current_soc: float,
    avg_speed_kmh: float,
) -> float:
    """Km de ruta preferido (~2–2:30 h) acotado al alcance de batería."""
    leg_target = target_leg_km
    if current_soc >= FIRST_LEG_FULL_SOC_THRESHOLD_PCT:
        leg_target = leg_distance_for_driving_minutes(avg_speed_kmh, FIRST_LEG_DRIVING_MINUTES)
    return current_route_km + min(charging_reach_km, leg_target, remaining_km)


def _next_hop_has_reachable_charger(
    matches: list[CorridorMatch],
    *,
    from_route_km: float,
    departure_soc_pct: float,
    profile: VehicleEnergyProfile,
    destination_distance_km: float,
    used_station_ids: set[str],
) -> bool:
    """True si con ese SOC de salida se llega al destino o hay DC en el alcance."""
    segment_profile = _profile_at_soc(profile, departure_soc_pct)
    remaining = max(0.0, destination_distance_km - from_route_km)
    if remaining <= estimate_range_km(segment_profile) + 1e-6:
        return True
    reach = estimate_charging_reach_km(segment_profile)
    cands, _, _ = reachable_segment_candidates(
        matches,
        current_route_km=from_route_km,
        charging_reach_km=reach,
        used_station_ids=used_station_ids,
        min_forward_km=MIN_FORWARD_PROGRESS_KM,
        remaining_km=remaining,
    )
    return bool(cands)


def _bump_departure_soc_for_next_hop(
    *,
    arrival_soc_pct: float,
    departure_soc_pct: float,
    stop_route_km: float,
    station_max_kw: float,
    matches: list[CorridorMatch],
    profile: VehicleEnergyProfile,
    destination_distance_km: float,
    used_station_ids: set[str],
) -> tuple[float, float]:
    """Sube SOC de salida hasta abrir la siguiente ventana reach o techo DC."""
    ceiling = min(profile.max_charge_soc_pct, OPTIMAL_CHARGE_CEILING_SOC_PCT)
    departure = departure_soc_pct
    while departure + 0.5 < ceiling and not _next_hop_has_reachable_charger(
        matches,
        from_route_km=stop_route_km,
        departure_soc_pct=departure,
        profile=profile,
        destination_distance_km=destination_distance_km,
        used_station_ids=used_station_ids,
    ):
        departure = min(ceiling, departure + 5.0)
    charge_minutes = estimate_charge_minutes(
        arrival_soc_pct,
        departure,
        usable_capacity_kwh=profile.usable_capacity_kwh,
        max_power_kw=station_max_kw,
        vehicle_preset_id=profile.vehicle_preset_id,
        vehicle_max_charge_kw=profile.max_charge_power_kw,
    )
    return departure, charge_minutes


def resolve_avg_speed_kmh(
    route_distance_km: float | None,
    route_duration_minutes: float | None,
) -> float:
    if route_distance_km and route_duration_minutes and route_duration_minutes > 1:
        speed = route_distance_km / (route_duration_minutes / 60.0)
        return max(40.0, min(140.0, speed))
    return DEFAULT_AVG_SPEED_KMH


def leg_distance_for_driving_minutes(avg_speed_kmh: float, minutes: float) -> float:
    return avg_speed_kmh * (minutes / 60.0)


def driving_minutes_for_distance(leg_distance_km: float, avg_speed_kmh: float) -> float:
    if avg_speed_kmh <= 0:
        return 0.0
    return (leg_distance_km / avg_speed_kmh) * 60.0


def estimate_driving_breaks_needed(distance_km: float, avg_speed_kmh: float) -> int:
    leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, TARGET_DRIVING_LEG_MINUTES)
    if leg_km <= 0 or distance_km <= leg_km + 1e-6:
        return 0
    return max(1, math.ceil(distance_km / leg_km) - 1)


def _segment_min_route_km(
    *,
    trip_start_route_km: float,
    current_route_km: float,
    current_soc: float,
    trip_start_soc: float,
    target_leg_km: float,
    max_leg_km: float,
    profile: VehicleEnergyProfile,
    route_preference: str | None = None,
) -> float:
    exclusion_km = origin_exclusion_radius_km(
        target_leg_km,
        trip_start_soc,
        charging_reach_km=estimate_charging_reach_km(profile),
        max_leg_km=max_leg_km,
    )
    from_trip_start = current_route_km - trip_start_route_km
    progress_fraction = min_leg_progress_fraction(route_preference)

    # #6157 — SOC ≤10 %: no exigir ~15–2 h; la 1.ª parada debe poder ser el cargador de salida.
    if allows_origin_zone_charging(trip_start_soc) and from_trip_start < 1.0:
        return trip_start_route_km + ORIGIN_ZONE_MIN_FORWARD_KM

    if exclusion_km > 0 and from_trip_start < 1.0:
        return trip_start_route_km + exclusion_km

    min_leg_km = target_leg_km * progress_fraction
    if current_soc >= 70.0:
        min_leg_km = max(min_leg_km, target_leg_km * max(0.8, progress_fraction - 0.05))
    min_leg_km = min(min_leg_km, max_leg_km)
    segment_profile = _profile_at_soc(profile, current_soc)
    charging_reach_km = estimate_charging_reach_km(segment_profile)
    min_leg_km = min(min_leg_km, charging_reach_km * 0.95)
    candidate = current_route_km + max(min_leg_km, 15.0)
    if exclusion_km > 0:
        candidate = max(candidate, trip_start_route_km + exclusion_km)
    return candidate


def _is_meaningful_charging_stop(
    *,
    arrival_soc_pct: float,
    departure_soc_pct: float,
    charge_minutes: float,
    leg_distance_km: float,
    min_leg_km: float,
    stop_route_km: float,
    trip_start_route_km: float,
    origin_exclusion_km: float,
    allow_short_origin_leg: bool = False,
) -> bool:
    if origin_exclusion_km > 0 and (stop_route_km - trip_start_route_km) < origin_exclusion_km - 1e-6:
        return False
    # #6157: con SOC ≤10 % la 1.ª parada puede estar a pocos km de la salida.
    if not allow_short_origin_leg and leg_distance_km + 1e-6 < min_leg_km * 0.5:
        return False
    soc_gain = departure_soc_pct - arrival_soc_pct
    # Micro-parada (#6154 Totana/Cúllar): con batería no crítica, exigir ganancia ≥10 %.
    # En HPC 5–8 min suelen ser solo +5 % SOC — no compensan el desvío.
    if (
        arrival_soc_pct + 1e-6 >= FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT
        and soc_gain + 1e-6 < MIN_WORTHWHILE_SOC_GAIN_PCT
    ):
        return False
    if leg_distance_km + 1e-6 >= min_leg_km * MIN_LEG_ACCEPT_FRACTION:
        return True
    return (
        charge_minutes >= MIN_WORTHWHILE_CHARGE_MINUTES
        and soc_gain >= MIN_WORTHWHILE_SOC_GAIN_PCT
    )


def _is_worth_charging_stop(
    *,
    arrival_soc_pct: float,
    departure_soc_pct: float,
    charge_minutes: float,
    leg_distance_km: float,
    min_leg_km: float,
    stop_route_km: float,
    trip_start_route_km: float,
    origin_exclusion_km: float,
    trip_start_soc_pct: float,
    avg_speed_kmh: float,
) -> bool:
    """Descarta micro-paradas (#6098, #6154): alta llegada y poca ganancia de carga."""
    soc_gain = departure_soc_pct - arrival_soc_pct
    allow_short_origin_leg = allows_origin_zone_charging(trip_start_soc_pct)
    if (
        arrival_soc_pct + 1e-6 >= FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT
        and soc_gain + 1e-6 < MIN_WORTHWHILE_SOC_GAIN_PCT
    ):
        return False

    if allow_short_origin_leg and leg_distance_km + 1e-6 >= ORIGIN_ZONE_MIN_FORWARD_KM:
        # Carga de emergencia cerca del origen: basta una ganancia útil.
        if soc_gain + 1e-6 >= MIN_WORTHWHILE_SOC_GAIN_PCT or (
            charge_minutes + 1e-6 >= MIN_WORTHWHILE_CHARGE_MINUTES
        ):
            return True

    if leg_distance_km + 1e-6 >= min_leg_km * MIN_LEG_ACCEPT_FRACTION:
        return _is_meaningful_charging_stop(
            arrival_soc_pct=arrival_soc_pct,
            departure_soc_pct=departure_soc_pct,
            charge_minutes=charge_minutes,
            leg_distance_km=leg_distance_km,
            min_leg_km=min_leg_km,
            stop_route_km=stop_route_km,
            trip_start_route_km=trip_start_route_km,
            origin_exclusion_km=origin_exclusion_km,
            allow_short_origin_leg=allow_short_origin_leg,
        )

    if (
        arrival_soc_pct >= MICRO_STOP_SHORT_CHARGE_ARRIVAL_SOC_PCT
        and charge_minutes < MIN_WORTHWHILE_CHARGE_MINUTES
    ):
        return False
    if arrival_soc_pct > HIGH_ARRIVAL_MICRO_STOP_SOC_PCT and soc_gain < MIN_WORTHWHILE_SOC_GAIN_PCT:
        return False
    if charge_minutes < MIN_WORTHWHILE_CHARGE_MINUTES and soc_gain < MIN_WORTHWHILE_SOC_GAIN_PCT:
        return False
    if trip_start_soc_pct >= FIRST_LEG_FULL_SOC_THRESHOLD_PCT:
        max_leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, MAX_DRIVING_LEG_MINUTES)
        first_leg_min_km = max(
            origin_exclusion_km,
            leg_distance_for_driving_minutes(avg_speed_kmh, FIRST_LEG_DRIVING_MINUTES)
            * MIN_LEG_ACCEPT_FRACTION,
        )
        first_leg_min_km = min(first_leg_min_km, max_leg_km * MIN_LEG_ACCEPT_FRACTION)
        from_start = stop_route_km - trip_start_route_km
        if from_start < first_leg_min_km and arrival_soc_pct > HIGH_ARRIVAL_MICRO_STOP_SOC_PCT:
            return False
    return _is_meaningful_charging_stop(
        arrival_soc_pct=arrival_soc_pct,
        departure_soc_pct=departure_soc_pct,
        charge_minutes=charge_minutes,
        leg_distance_km=leg_distance_km,
        min_leg_km=min_leg_km,
        stop_route_km=stop_route_km,
        trip_start_route_km=trip_start_route_km,
        origin_exclusion_km=origin_exclusion_km,
        allow_short_origin_leg=allow_short_origin_leg,
    )


def _filter_segment_matches(
    matches: list[CorridorMatch],
    *,
    segment_min_km: float,
    segment_end_km: float,
    used_station_ids: set[str],
    current_route_km: float,
    trip_start_route_km: float,
    origin_exclusion_km: float,
) -> list[CorridorMatch]:
    return [
        match
        for match in matches
        if match.station.id not in used_station_ids
        and current_route_km < (match.route_position_m / 1000.0) <= segment_end_km + 1e-6
        and (match.route_position_m / 1000.0) >= segment_min_km - 1e-6
        and (
            origin_exclusion_km <= 0
            or (match.route_position_m / 1000.0) - trip_start_route_km >= origin_exclusion_km - 1e-6
        )
    ]


def _profile_at_soc(profile: VehicleEnergyProfile, soc_percent: float) -> VehicleEnergyProfile:
    return VehicleEnergyProfile(
        soc_percent=soc_percent,
        usable_capacity_kwh=profile.usable_capacity_kwh,
        consumption_wh_per_km=profile.consumption_wh_per_km,
        terrain_factor=profile.terrain_factor,
        reserve_soc_percent=profile.reserve_soc_percent,
        vehicle_preset_id=profile.vehicle_preset_id,
        max_charge_power_kw=profile.max_charge_power_kw,
        min_destination_soc_pct=profile.min_destination_soc_pct,
        min_stop_arrival_soc_pct=profile.min_stop_arrival_soc_pct,
        max_charge_soc_pct=profile.max_charge_soc_pct,
    )


def soc_required_to_drive_km(
    profile: VehicleEnergyProfile,
    distance_km: float,
    arrival_soc_pct: float,
) -> float:
    if distance_km <= 0:
        return arrival_soc_pct
    consumption_kwh = distance_km * effective_consumption_wh_per_km(profile) / 1000.0
    soc_drop = (consumption_kwh / profile.usable_capacity_kwh) * 100.0
    return min(100.0, arrival_soc_pct + soc_drop)


def effective_station_charge_kw(station_max_kw: float, profile: VehicleEnergyProfile) -> float:
    return min(float(station_max_kw), profile.max_charge_power_kw)


def estimate_charge_minutes(
    arrival_soc_pct: float,
    departure_soc_pct: float,
    *,
    usable_capacity_kwh: float,
    max_power_kw: float,
    vehicle_preset_id: str | None = None,
    vehicle_max_charge_kw: float | None = None,
) -> float:
    station_kw = max_power_kw
    if vehicle_max_charge_kw is not None:
        station_kw = min(station_kw, vehicle_max_charge_kw)
    return estimate_dc_charge_minutes(
        arrival_soc_pct,
        departure_soc_pct,
        usable_capacity_kwh=usable_capacity_kwh,
        station_max_kw=station_kw,
        vehicle_preset_id=vehicle_preset_id,
    )


def _is_final_driving_hop(
    remaining_km: float,
    profile: VehicleEnergyProfile,
    avg_speed_kmh: float,
) -> bool:
    full_range = estimate_range_km(_profile_at_soc(profile, 100.0))
    max_leg_km = min(
        full_range,
        leg_distance_for_driving_minutes(avg_speed_kmh, MAX_DRIVING_LEG_MINUTES),
    )
    return remaining_km <= max_leg_km + 1e-6


def _intermediate_charge_ceiling_pct(profile: VehicleEnergyProfile) -> float:
    """Techo de carga en paradas intermedias (zona rápida DC, estilo Tesla/REVE)."""
    return min(
        profile.max_charge_soc_pct,
        OPTIMAL_CHARGE_CEILING_SOC_PCT,
        INTERMEDIATE_OPTIMAL_CHARGE_SOC_PCT,
    )


def _optimal_departure_soc_for_stop(
    *,
    arrival_soc_pct: float,
    remaining_km: float,
    profile: VehicleEnergyProfile,
    destination_target_soc_pct: float,
    is_final_hop: bool,
    avg_speed_kmh: float,
) -> float:
    if remaining_km <= 1e-6:
        return min(100.0, max(arrival_soc_pct + 5.0, arrival_soc_pct))

    if is_final_hop:
        segment_profile = _profile_at_soc(profile, arrival_soc_pct)
        soc_at_dest = soc_at_distance_km(segment_profile, remaining_km)
        min_departure = arrival_soc_pct + max(0.0, destination_target_soc_pct - soc_at_dest)
        buffered = min(100.0, min_departure + DEPARTURE_SOC_BUFFER_PCT)
        capped = min(buffered, profile.max_charge_soc_pct)
        return min(100.0, max(capped, arrival_soc_pct + 5.0))

    # Paradas intermedias: energía para ~2 h de conducción, sin llenar hasta el taper lento.
    next_leg_km = min(
        remaining_km,
        leg_distance_for_driving_minutes(avg_speed_kmh, TARGET_DRIVING_LEG_MINUTES),
    )
    min_departure = soc_required_to_drive_km(
        profile,
        next_leg_km,
        profile.min_stop_arrival_soc_pct,
    )
    buffered = min(100.0, min_departure + DEPARTURE_SOC_BUFFER_PCT)
    sweet_spot_ceiling = _intermediate_charge_ceiling_pct(profile)
    departure = min(buffered, sweet_spot_ceiling)
    departure = max(departure, arrival_soc_pct + 5.0)
    # #6154: si paras con SOC no crítico, carga al menos +10 % (evita pinchazos de 5 min).
    if arrival_soc_pct + 1e-6 >= FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT:
        worthwhile_floor = min(
            profile.max_charge_soc_pct,
            arrival_soc_pct + MIN_WORTHWHILE_SOC_GAIN_PCT,
        )
        departure = max(departure, worthwhile_floor)
    return min(departure, profile.max_charge_soc_pct)


def _planned_stop_selection_key(
    stop: ScoredChargingStop,
    *,
    charge_minutes: float,
    target_stop_km: float,
    preferences: ChargingPreferences | None,
) -> tuple[float, ...]:
    distance_to_target = asymmetric_distance_to_target_km(stop.route_distance_km, target_stop_km)
    distance_bucket = round(distance_to_target / 25.0)
    deviation_bucket = round(stop.deviation_km / DEVIATION_PENALTY_KM_BUCKET)
    on_route_rank = on_route_operator_rank(
        stop.station.operator,
        preferences,
        stop.deviation_km,
    )
    base = _rank_key(stop, preferences)
    return (
        deviation_bucket,
        on_route_rank,
        distance_bucket,
        float(CLASSIFICATION_ORDER[stop.classification]),
        charge_minutes,
        -stop.station.max_power_kw,
        stop.extra_minutes,
        *base,
    )


def _pick_best_planned_stop(
    viable: list[ScoredChargingStop],
    *,
    profile: VehicleEnergyProfile,
    destination_distance_km: float,
    avg_speed_kmh: float,
    destination_target_soc_pct: float,
    target_stop_km: float,
    preferences: ChargingPreferences | None,
) -> tuple[ScoredChargingStop, float, float]:
    best: ScoredChargingStop | None = None
    best_departure = 0.0
    best_charge = 0.0
    best_key: tuple[float, ...] | None = None

    for stop in viable:
        remaining = max(0.0, destination_distance_km - stop.route_distance_km)
        is_final = _is_final_driving_hop(remaining, profile, avg_speed_kmh)
        departure = _optimal_departure_soc_for_stop(
            arrival_soc_pct=stop.soc_arrival_pct,
            remaining_km=remaining,
            profile=profile,
            destination_target_soc_pct=destination_target_soc_pct,
            is_final_hop=is_final,
            avg_speed_kmh=avg_speed_kmh,
        )
        charge_min = estimate_charge_minutes(
            stop.soc_arrival_pct,
            departure,
            usable_capacity_kwh=profile.usable_capacity_kwh,
            max_power_kw=stop.station.max_power_kw,
            vehicle_preset_id=profile.vehicle_preset_id,
            vehicle_max_charge_kw=profile.max_charge_power_kw,
        )
        key = _planned_stop_selection_key(
            stop,
            charge_minutes=charge_min,
            target_stop_km=target_stop_km,
            preferences=preferences,
        )
        if best is None or key < best_key:
            best = stop
            best_departure = departure
            best_charge = charge_min
            best_key = key

    if best is None:
        msg = "viable list must not be empty"
        raise ValueError(msg)
    return best, best_departure, best_charge


def build_planned_route_stops_greedy(
    matches: list[CorridorMatch],
    *,
    origin_position_km: float,
    destination_distance_km: float,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    destination_target_soc_pct: float | None = None,
    charge_target_soc_pct: float = DEFAULT_CHARGE_TARGET_SOC_PCT,
    max_stops: int = MAX_PLANNED_ROUTE_STOPS,
    preferences: ChargingPreferences | None = None,
    route_distance_km: float | None = None,
    route_duration_minutes: float | None = None,
    route_preference: str | None = None,
) -> tuple[list[PlannedRouteStop], list[str], float | None]:
    """Greedy batería-primero: SOC → reach → candidatos → ranking (~2 h suave) → carga."""
    _ = charge_target_soc_pct  # legacy param; optimal SOC replaces fixed 80 % target
    resolved_destination_soc = (
        destination_target_soc_pct
        if destination_target_soc_pct is not None
        else profile.min_destination_soc_pct
    )
    avg_speed_kmh = resolve_avg_speed_kmh(route_distance_km, route_duration_minutes)
    distance_to_dest_km = max(0.0, destination_distance_km - origin_position_km)
    if distance_to_dest_km <= estimate_range_km(profile) + 1e-6:
        return [], [], round(clamp_display_soc_pct(soc_at_distance_km(profile, distance_to_dest_km)), 1)

    warnings: list[str] = []
    planned: list[PlannedRouteStop] = []
    used_station_ids: set[str] = set()
    trip_start_route_km = origin_position_km
    trip_start_soc = profile.soc_percent
    current_route_km = origin_position_km
    current_soc = profile.soc_percent
    previous_route_km = origin_position_km

    max_leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, MAX_DRIVING_LEG_MINUTES)
    target_leg_km = leg_distance_for_driving_minutes(avg_speed_kmh, TARGET_DRIVING_LEG_MINUTES)
    allow_origin_zone = allows_origin_zone_charging(trip_start_soc)

    for _attempt in range(max_stops):
        remaining_km = max(0.0, destination_distance_km - current_route_km)
        segment_profile = _profile_at_soc(profile, current_soc)
        segment_range_km = estimate_range_km(segment_profile)
        if remaining_km <= segment_range_km + 1e-6:
            projected = soc_at_distance_km(segment_profile, remaining_km)
            return planned, warnings, round(clamp_display_soc_pct(projected), 1)

        charging_reach_km = estimate_charging_reach_km(segment_profile)
        is_first_hop = current_route_km <= trip_start_route_km + 1e-6
        min_forward = hop_min_forward_km(
            trip_start_soc_pct=trip_start_soc,
            is_first_hop=is_first_hop,
        )
        segment_matches, segment_min_km, segment_end_km = reachable_segment_candidates(
            matches,
            current_route_km=current_route_km,
            charging_reach_km=charging_reach_km,
            used_station_ids=used_station_ids,
            min_forward_km=min_forward,
            remaining_km=remaining_km,
        )
        # Preferencia suave ~3 h: si hay candidatos dentro del techo fisiológico, úsalos.
        soft_end_km = current_route_km + min(charging_reach_km, max_leg_km, remaining_km)
        if soft_end_km + 1e-6 < segment_end_km:
            within_soft = [
                m
                for m in segment_matches
                if (m.route_position_m / 1000.0) <= soft_end_km + 1e-6
            ]
            if within_soft:
                segment_matches = within_soft
                segment_end_km = soft_end_km

        target_stop_km = preferred_stop_target_km(
            current_route_km=current_route_km,
            charging_reach_km=charging_reach_km,
            remaining_km=remaining_km,
            target_leg_km=target_leg_km,
            current_soc=current_soc,
            avg_speed_kmh=avg_speed_kmh,
        )
        preferred_min_leg_km = max(
            min_forward,
            min(
                target_leg_km * min_leg_progress_fraction(route_preference),
                charging_reach_km * 0.95,
            ),
        )
        # Tras la 1.ª parada, el espaciado ~2 h es solo ranking; no descartar
        # candidatos alcanzables (p. ej. Cúllar tras Lorca anticipada).
        if not is_first_hop:
            preferred_min_leg_km = min_forward

        if is_first_hop and allow_origin_zone and segment_matches:
            warnings.append(
                "SOC bajo al salir: se sugiere cargar cerca del origen antes de continuar."
            )

        # Comfort (#6152): si hay llegada ≥20 % en la ventana reach, preferir esos.
        if is_first_hop and segment_matches and not allow_origin_zone:
            comfort_matches = first_stop_comfort_matches(
                segment_matches,
                current_route_km=current_route_km,
                profile=segment_profile,
            )
            if comfort_matches and len(comfort_matches) < len(segment_matches):
                segment_matches = comfort_matches
                warnings.append(
                    "Primera parada anticipada: el tramo ~2 h dejaría poca batería "
                    "al llegar; se sugiere cargar antes."
                )
            elif not comfort_matches and segment_matches:
                # Ventana reach sin tramo ~2 h cómodo (#6151 / batería-primero).
                farthest = max(m.route_position_m / 1000.0 for m in segment_matches)
                if farthest + 1e-6 < target_stop_km:
                    warnings.append(
                        "Primera parada anticipada: no hay cargador en el tramo ~2 h "
                        "alcanzable con tu SOC; se sugiere cargar antes."
                    )

        if not segment_matches:
            warnings.append(
                f"No hay cargador alcanzable en el tramo ~{current_route_km:.0f}–{segment_end_km:.0f} km "
                f"(SOC {current_soc:.0f} %, alcance ~{charging_reach_km:.0f} km)."
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

        forward_viable = [
            stop
            for stop in viable
            if stop.route_distance_km > current_route_km + min_forward - 1e-6
            and stop.route_distance_km >= segment_min_km - 1e-6
        ]
        if forward_viable:
            viable = forward_viable
        elif viable:
            warnings.append(
                f"Sin cargadores por delante de km {current_route_km:.0f}; "
                "revisa corredor o filtros kW."
            )
            break

        chosen, departure_soc, charge_minutes = _pick_best_planned_stop(
            viable,
            profile=profile,
            destination_distance_km=destination_distance_km,
            avg_speed_kmh=avg_speed_kmh,
            destination_target_soc_pct=resolved_destination_soc,
            target_stop_km=target_stop_km,
            preferences=preferences,
        )
        stop_route_km = chosen.route_distance_km
        if stop_route_km <= previous_route_km + 1e-6:
            used_station_ids.add(chosen.station.id)
            warnings.append(
                f"Omitido cargador a km {stop_route_km:.0f} (retrocede respecto a km {previous_route_km:.0f})."
            )
            continue
        leg_distance_km = max(0.0, stop_route_km - previous_route_km)

        # Batería-primero: no exclusión DGT dura. El ranking (~2 h) prefiere paradas
        # lejanas; _is_worth sigue rechazando micro-paradas con SOC alto.
        if not _is_worth_charging_stop(
            arrival_soc_pct=chosen.soc_arrival_pct,
            departure_soc_pct=departure_soc,
            charge_minutes=charge_minutes,
            leg_distance_km=leg_distance_km,
            min_leg_km=preferred_min_leg_km,
            stop_route_km=stop_route_km,
            trip_start_route_km=trip_start_route_km,
            origin_exclusion_km=0.0,
            trip_start_soc_pct=trip_start_soc,
            avg_speed_kmh=avg_speed_kmh,
        ):
            used_station_ids.add(chosen.station.id)
            warnings.append(
                f"Omitido cargador a {chosen.distance_from_origin_km:.0f} km (parada innecesaria tan cerca de la salida)."
            )
            if len(used_station_ids) > max_stops * 3:
                break
            continue

        ids_after_stop = used_station_ids | {chosen.station.id}
        bumped_dep, bumped_charge = _bump_departure_soc_for_next_hop(
            arrival_soc_pct=chosen.soc_arrival_pct,
            departure_soc_pct=departure_soc,
            stop_route_km=stop_route_km,
            station_max_kw=chosen.station.max_power_kw,
            matches=matches,
            profile=profile,
            destination_distance_km=destination_distance_km,
            used_station_ids=ids_after_stop,
        )
        if bumped_dep > departure_soc + 0.5:
            warnings.append(
                "Carga más alta en esta parada: con la carga intermedia no habría "
                "cargador alcanzable en el siguiente tramo."
            )
            departure_soc = bumped_dep
            charge_minutes = bumped_charge

        leg_driving_minutes = driving_minutes_for_distance(leg_distance_km, avg_speed_kmh)
        if leg_driving_minutes > MAX_DRIVING_LEG_MINUTES + 5:
            warnings.append(
                f"Tramo {len(planned) + 1}: ~{leg_driving_minutes:.0f} min conducción "
                f"(recomendado ≤{TARGET_DRIVING_LEG_MINUTES:.0f} min, máx. {MAX_DRIVING_LEG_MINUTES:.0f})."
            )
        planned.append(
            PlannedRouteStop(
                order=len(planned) + 1,
                station=chosen.station,
                deviation_km=chosen.deviation_km,
                route_distance_km=chosen.route_distance_km,
                extra_minutes=chosen.extra_minutes,
                wrong_side=chosen.wrong_side,
                distance_from_origin_km=round(stop_route_km - trip_start_route_km, 2),
                leg_distance_km=round(leg_distance_km, 2),
                leg_driving_minutes=round(leg_driving_minutes, 1),
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
        final_profile = _profile_at_soc(profile, current_soc)
        projected = soc_at_distance_km(final_profile, max(0.0, destination_distance_km - current_route_km))
        projected_clamped = round(clamp_display_soc_pct(projected), 1)
        if projected < resolved_destination_soc:
            warnings.append(
                f"Con {len(planned)} parada(s) planificada(s) llegarías con ~{projected_clamped:.0f} % "
                f"(objetivo {resolved_destination_soc:.0f} %)."
            )
        return planned, warnings, projected_clamped

    return planned, warnings, None



def build_planned_route_stops(
    matches: list[CorridorMatch],
    *,
    origin_position_km: float,
    destination_distance_km: float,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    destination_target_soc_pct: float | None = None,
    charge_target_soc_pct: float = DEFAULT_CHARGE_TARGET_SOC_PCT,
    max_stops: int = MAX_PLANNED_ROUTE_STOPS,
    preferences: ChargingPreferences | None = None,
    route_distance_km: float | None = None,
    route_duration_minutes: float | None = None,
    route_preference: str | None = None,
) -> tuple[list[PlannedRouteStop], list[str], float | None]:
    """Plan multi-parada: optimizador global (#6087) con fallback greedy."""
    from api.routing.route_stop_optimizer import optimize_planned_route_stops

    optimized = optimize_planned_route_stops(
        matches,
        origin_position_km=origin_position_km,
        destination_distance_km=destination_distance_km,
        profile=profile,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        destination_target_soc_pct=destination_target_soc_pct,
        max_stops=max_stops,
        preferences=preferences,
        route_distance_km=route_distance_km,
        route_duration_minutes=route_duration_minutes,
        trip_start_route_km=origin_position_km,
        route_preference=route_preference,
    )
    if optimized is not None:
        return optimized

    return build_planned_route_stops_greedy(
        matches,
        origin_position_km=origin_position_km,
        destination_distance_km=destination_distance_km,
        profile=profile,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
        destination_target_soc_pct=destination_target_soc_pct,
        charge_target_soc_pct=charge_target_soc_pct,
        max_stops=max_stops,
        preferences=preferences,
        route_distance_km=route_distance_km,
        route_duration_minutes=route_duration_minutes,
        route_preference=route_preference,
    )


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
    route_distance_km: float | None = None,
    route_duration_minutes: float | None = None,
    corridor_stops: list[CorridorMatch] | None = None,
    route_preference: str | None = None,
) -> ChargingPlanComputation:
    range_km = estimate_range_km(profile)
    charging_reach_km = estimate_charging_reach_km(profile)
    corridor_matches = corridor_stops if corridor_stops is not None else matches
    stops = [
        _stop_from_corridor_match(
            match,
            origin_position_km=origin_position_km,
            profile=profile,
            charging_reach_km=charging_reach_km,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
        )
        for match in corridor_matches
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
    avg_speed_kmh = resolve_avg_speed_kmh(route_distance_km, route_duration_minutes)
    if distance_to_dest_km > range_km + 1e-6:
        battery_stops = estimate_charging_stops_needed(distance_to_dest_km, range_km)
        driving_stops = estimate_driving_breaks_needed(distance_to_dest_km, avg_speed_kmh)
        stops_needed = max(battery_stops, driving_stops)
        warnings.append(
            f"Ruta larga ({distance_to_dest_km:.0f} km): autonomía sin parar ~{range_km:.0f} km. "
            f"Planifica al menos {stops_needed} parada(s) "
            f"(batería {battery_stops}, pausas ~{TARGET_DRIVING_LEG_MINUTES / 60:.0f} h {driving_stops})."
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
        route_distance_km=route_distance_km,
        route_duration_minutes=route_duration_minutes,
        route_preference=route_preference,
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
