from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from api.routing.corridor import CorridorMatch
from models.station import Station

ChargingClassification = Literal["safe", "adjusted", "critical", "unreachable"]

CLASSIFICATION_ORDER: dict[ChargingClassification, int] = {
    "safe": 0,
    "adjusted": 1,
    "critical": 2,
    "unreachable": 3,
}

STRATEGY_CHARGE_NOW = "charge_now"
STRATEGY_NEXT_SAFE = "next_safe"
STRATEGY_BEST_VALUE = "best_value"


@dataclass(frozen=True)
class VehicleEnergyProfile:
    soc_percent: float
    usable_capacity_kwh: float
    consumption_wh_per_km: float
    terrain_factor: float = 1.0
    reserve_soc_percent: float = 10.0


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
class ChargingPlanComputation:
    range_km: float
    soc_at_destination_pct: float | None
    reachable_without_stop: bool
    stops: list[ScoredChargingStop]
    strategies: list[ChargingStrategyOption]
    warnings: list[str]


def effective_consumption_wh_per_km(profile: VehicleEnergyProfile) -> float:
    return profile.consumption_wh_per_km * profile.terrain_factor


def available_energy_kwh(profile: VehicleEnergyProfile) -> float:
    usable_soc = max(0.0, profile.soc_percent - profile.reserve_soc_percent)
    return profile.usable_capacity_kwh * usable_soc / 100.0


def estimate_range_km(profile: VehicleEnergyProfile) -> float:
    consumption_kwh_per_km = effective_consumption_wh_per_km(profile) / 1000.0
    if consumption_kwh_per_km <= 0:
        return 0.0
    return available_energy_kwh(profile) / consumption_kwh_per_km


def soc_at_distance_km(profile: VehicleEnergyProfile, distance_km: float) -> float:
    if profile.usable_capacity_kwh <= 0:
        return 0.0
    energy_used_kwh = distance_km * effective_consumption_wh_per_km(profile) / 1000.0
    soc_drop = (energy_used_kwh / profile.usable_capacity_kwh) * 100.0
    return profile.soc_percent - soc_drop


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
    range_km: float,
    safe_margin_pct: float,
    adjusted_min_pct: float,
) -> ScoredChargingStop:
    distance_from_origin_km = max(0.0, match.route_position_m / 1000.0 - origin_position_km)
    soc_arrival_pct = round(soc_at_distance_km(profile, distance_from_origin_km), 1)
    within_range = distance_from_origin_km <= range_km + 1e-6
    classification = classify_soc_arrival(
        soc_arrival_pct,
        within_range=within_range,
        safe_margin_pct=safe_margin_pct,
        adjusted_min_pct=adjusted_min_pct,
    )
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


def _rank_key(stop: ScoredChargingStop) -> tuple[float, float, float, float, float]:
    price = stop.station.dynamic_price_eur_kwh
    price_key = price if price is not None else 999.0
    status_penality = 0.0
    if stop.station.dynamic_status == "occupied":
        status_penality = 1.0
    elif stop.station.dynamic_status == "outofservice":
        status_penality = 2.0
    return (
        CLASSIFICATION_ORDER[stop.classification],
        stop.deviation_km,
        -stop.soc_arrival_pct,
        status_penality,
        price_key,
    )


def _build_strategies(stops: list[ScoredChargingStop]) -> list[ChargingStrategyOption]:
    viable = [stop for stop in stops if stop.classification != "unreachable"]
    strategies: list[ChargingStrategyOption] = []

    charge_now = min(viable, key=_rank_key, default=None)
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
        key=lambda item: (item.station.dynamic_price_eur_kwh or 999, _rank_key(item)),
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

    return strategies


def build_route_charging_plan(
    matches: list[CorridorMatch],
    *,
    origin_position_km: float,
    destination_distance_km: float,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    limit: int = 20,
) -> ChargingPlanComputation:
    range_km = estimate_range_km(profile)
    stops = [
        _stop_from_corridor_match(
            match,
            origin_position_km=origin_position_km,
            profile=profile,
            range_km=range_km,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
        )
        for match in matches
    ]
    stops.sort(key=_rank_key)
    stops = stops[:limit]

    distance_to_dest_km = max(0.0, destination_distance_km - origin_position_km)
    soc_at_destination_pct = round(soc_at_distance_km(profile, distance_to_dest_km), 1)
    reachable_without_stop = (
        distance_to_dest_km <= range_km + 1e-6 and soc_at_destination_pct >= profile.reserve_soc_percent
    )

    warnings: list[str] = []
    if not reachable_without_stop and not any(stop.classification == "safe" for stop in stops):
        warnings.append("No hay paradas seguras antes de agotar autonomía.")
    if any(stop.classification == "critical" for stop in stops[:3]):
        warnings.append("Las primeras opciones llegan con SOC crítico (< 10 %).")
    if soc_at_destination_pct < profile.reserve_soc_percent and not stops:
        warnings.append("No hay cargadores en corredor dentro de tu autonomía.")

    return ChargingPlanComputation(
        range_km=round(range_km, 1),
        soc_at_destination_pct=soc_at_destination_pct,
        reachable_without_stop=reachable_without_stop,
        stops=stops,
        strategies=_build_strategies(stops),
        warnings=warnings,
    )


def build_emergency_charging_plan(
    stations: list[tuple[Station, float]],
    *,
    profile: VehicleEnergyProfile,
    safe_margin_pct: float = 15.0,
    adjusted_min_pct: float = 10.0,
    limit: int = 10,
) -> ChargingPlanComputation:
    range_km = estimate_range_km(profile)
    stops: list[ScoredChargingStop] = []

    for station, distance_km in stations:
        soc_arrival_pct = round(soc_at_distance_km(profile, distance_km), 1)
        within_range = distance_km <= range_km + 1e-6
        classification = classify_soc_arrival(
            soc_arrival_pct,
            within_range=within_range,
            safe_margin_pct=safe_margin_pct,
            adjusted_min_pct=adjusted_min_pct,
        )
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

    stops.sort(key=_rank_key)
    stops = stops[:limit]

    warnings: list[str] = []
    if not any(stop.classification != "unreachable" for stop in stops):
        warnings.append("No hay cargadores alcanzables desde tu posición.")

    return ChargingPlanComputation(
        range_km=round(range_km, 1),
        soc_at_destination_pct=None,
        reachable_without_stop=False,
        stops=stops,
        strategies=_build_strategies(stops),
        warnings=warnings,
    )
