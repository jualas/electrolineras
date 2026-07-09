from __future__ import annotations

from api.routing.charging_plan import PlannedRouteStop, VehicleEnergyProfile, effective_consumption_wh_per_km
from api.schemas import PlannedRouteStopResult, RouteTripSummaryResult


def _leg_energy_kwh(leg_distance_km: float, consumption_wh_per_km: float) -> float:
    if leg_distance_km <= 0:
        return 0.0
    return leg_distance_km * consumption_wh_per_km / 1000.0


def _charge_energy_kwh(
    profile: VehicleEnergyProfile,
    soc_from_pct: float,
    soc_to_pct: float,
) -> float:
    delta = max(0.0, soc_to_pct - soc_from_pct)
    return profile.usable_capacity_kwh * delta / 100.0


def enrich_planned_stop_metrics(
    stop: PlannedRouteStop,
    *,
    profile: VehicleEnergyProfile,
) -> dict[str, float | None]:
    consumption = effective_consumption_wh_per_km(profile)
    leg_energy = _leg_energy_kwh(stop.leg_distance_km, consumption)
    charge_energy = _charge_energy_kwh(profile, stop.soc_arrival_pct, stop.soc_departure_pct)
    price = stop.station.dynamic_price_eur_kwh
    charge_cost = round(charge_energy * price, 2) if price is not None and price > 0 else None
    effective_kw = min(stop.station.max_power_kw, profile.max_charge_power_kw)
    return {
        "leg_energy_kwh": round(leg_energy, 2),
        "recommended_charge_from_pct": round(stop.soc_arrival_pct, 1),
        "recommended_charge_to_pct": round(stop.soc_departure_pct, 1),
        "effective_charge_power_kw": round(effective_kw, 1),
        "estimated_charge_cost_eur": charge_cost,
    }


def build_route_trip_summary(
    *,
    profile: VehicleEnergyProfile,
    planned_stops: list[PlannedRouteStop],
    route_distance_km: float | None,
    route_duration_minutes: float | None,
    projected_destination_soc_pct: float | None,
) -> RouteTripSummaryResult | None:
    if route_distance_km is None or route_duration_minutes is None:
        return None

    consumption = effective_consumption_wh_per_km(profile)
    total_energy_kwh = route_distance_km * consumption / 1000.0
    driving_minutes = route_duration_minutes
    total_charge_minutes = sum(stop.charge_minutes for stop in planned_stops)
    charge_costs: list[float] = []

    for stop in planned_stops:
        metrics = enrich_planned_stop_metrics(stop, profile=profile)
        cost = metrics.get("estimated_charge_cost_eur")
        if isinstance(cost, (int, float)):
            charge_costs.append(float(cost))

    estimated_cost = round(sum(charge_costs), 2) if charge_costs else None

    return RouteTripSummaryResult(
        total_duration_minutes=round(driving_minutes + total_charge_minutes, 1),
        driving_duration_minutes=round(driving_minutes, 1),
        total_charge_minutes=round(total_charge_minutes, 1),
        total_energy_kwh=round(total_energy_kwh, 1),
        estimated_charge_cost_eur=estimated_cost,
        projected_destination_soc_pct=projected_destination_soc_pct,
        stop_count=len(planned_stops),
    )


def planned_stop_to_result(
    stop: PlannedRouteStop,
    *,
    profile: VehicleEnergyProfile,
) -> PlannedRouteStopResult:
    metrics = enrich_planned_stop_metrics(stop, profile=profile)
    return PlannedRouteStopResult(
        order=stop.order,
        station=stop.station,
        deviation_km=stop.deviation_km,
        route_distance_km=stop.route_distance_km,
        extra_minutes=stop.extra_minutes,
        wrong_side=stop.wrong_side,
        distance_from_origin_km=stop.distance_from_origin_km,
        leg_distance_km=stop.leg_distance_km,
        leg_driving_minutes=stop.leg_driving_minutes,
        soc_arrival_pct=stop.soc_arrival_pct,
        soc_departure_pct=stop.soc_departure_pct,
        charge_minutes=stop.charge_minutes,
        classification=stop.classification,
        leg_energy_kwh=metrics["leg_energy_kwh"],
        recommended_charge_from_pct=metrics["recommended_charge_from_pct"],
        recommended_charge_to_pct=metrics["recommended_charge_to_pct"],
        effective_charge_power_kw=metrics["effective_charge_power_kw"],
        estimated_charge_cost_eur=metrics["estimated_charge_cost_eur"],
        operator=stop.station.operator,
    )
