from __future__ import annotations

from api.routing.charging_plan import estimate_charging_stops_needed
from api.routing.destination_stay import DestinationStayAdvice, classify_power_band
from api.schemas import (
    ChargingClassification,
    ChargingPlanResponse,
    DestinationChargerOption,
    DestinationStayAdviceResult,
    PlannedRouteStopResult,
)
from models.station import Station

_CLASSIFICATION_LABELS: dict[ChargingClassification, str] = {
    "safe": "segura",
    "adjusted": "ajustada",
    "critical": "crítica",
    "unreachable": "no alcanzable",
}


def _route_preference_label(preference: str | None) -> str:
    if preference == "fastest":
        return "más rápida (tiempo mínimo con velocidades de vía)"
    if preference == "shortest":
        return "más directa (menos km y desvío vs línea recta)"
    if preference == "conventional":
        return "solo convencionales (nacionales/locales, sin autovía)"
    return "calculada"


def _planned_stop_label(stop: PlannedRouteStopResult) -> str:
    return station_display_label(stop.station)


def _format_planned_stop_bullet(stop: PlannedRouteStopResult) -> str:
    classification = _CLASSIFICATION_LABELS.get(stop.classification, stop.classification)
    charge_text = (
        f" · carga ~{stop.charge_minutes:.0f} min hasta {stop.soc_departure_pct:.0f} %"
        if stop.charge_minutes > 0
        else f" · salida ~{stop.soc_departure_pct:.0f} %"
    )
    drive_text = ""
    if stop.leg_driving_minutes > 0:
        from api.routing.trip_metrics import format_duration_minutes

        drive_fmt = format_duration_minutes(stop.leg_driving_minutes)
        drive_text = f" · ~{drive_fmt} conducción" if drive_fmt else ""
    return (
        f"Parada {stop.order}: {_planned_stop_label(stop)} "
        f"(km {stop.route_distance_km:.0f}, tramo {stop.leg_distance_km:.0f} km{drive_text}) · "
        f"llegada ~{stop.soc_arrival_pct:.0f} %{charge_text} · "
        f"{stop.station.max_power_kw:.0f} kW · {classification}"
    )


def station_display_label(station: Station) -> str:
    if station.site_name:
        return station.site_name
    if station.location.address:
        return station.location.address
    operator = station.operator or station.source
    return f"{operator} · {station.id}"


def nearest_destination_chargers_from_ranked(
    ranked: list[tuple[Station, float]],
    *,
    limit: int = 5,
) -> list[DestinationChargerOption]:
    options: list[DestinationChargerOption] = []
    for station, distance_km in ranked[:limit]:
        options.append(
            DestinationChargerOption(
                station_id=station.id,
                label=station_display_label(station),
                operator=station.operator,
                max_power_kw=station.max_power_kw,
                distance_km=round(distance_km, 2),
                lat=station.location.lat,
                lon=station.location.lon,
                power_band=classify_power_band(station.max_power_kw),
            )
        )
    return options


def build_agent_narration(
    plan: ChargingPlanResponse,
    destination_stay: DestinationStayAdviceResult | None = None,
) -> tuple[str, list[str]]:
    destination_stay = destination_stay or plan.destination_stay
    bullets: list[str] = []
    pref_parts: list[str] = []
    if plan.preferred_operators:
        pref_parts.append(f"operador {', '.join(plan.preferred_operators[:3])}")
    if plan.max_price_eur_kwh is not None:
        pref_parts.append(f"máx. {plan.max_price_eur_kwh:.2f} €/kWh")
    if pref_parts:
        bullets.append(f"Preferencias de carga: {' · '.join(pref_parts)} (ranking blando).")

    if plan.mode == "route" and plan.destination:
        pref_label = _route_preference_label(plan.route_preference)
        avoid = " · sin peajes" if plan.avoid_highways else ""
        distance = plan.route_distance_km or 0.0
        geodesic = plan.geodesic_distance_km
        shortest_km = plan.route_shortest_distance_km or distance
        fastest_km = plan.route_fastest_distance_km or distance
        conventional_km = plan.route_conventional_distance_km
        geodesic_text = f" · línea recta ~{geodesic:.0f} km" if geodesic else ""
        conventional_text = (
            f" · convencionales ~{conventional_km:.0f} km"
            if conventional_km is not None
            else ""
        )
        approx = " (aprox.)" if plan.route_variants_approximate else ""
        bullets.append(
            f"Ruta {pref_label}{avoid}: plan ~{distance:.0f} km{geodesic_text}{approx} · "
            f"ref. corta ~{shortest_km:.0f} km · ref. rápida ~{fastest_km:.0f} km"
            f"{conventional_text} · autonomía útil ~{plan.range_km:.0f} km "
            f"(SOC {plan.vehicle.soc_percent:.0f} %)."
        )
        if not plan.route_variants_approximate and plan.route_preference:
            pref = plan.route_preference
            if pref == "shortest" and shortest_km < fastest_km - 1:
                bullets.append(
                    f"Ruta elegida: la más directa (~{shortest_km:.0f} km vs ~{fastest_km:.0f} km rápida)."
                )
            elif pref == "fastest" and fastest_km < shortest_km - 1:
                bullets.append(
                    f"Ruta elegida: la más rápida (~{fastest_km:.0f} km vs ~{shortest_km:.0f} km directa)."
                )
            elif pref == "conventional" and conventional_km is not None:
                bullets.append(
                    f"Ruta elegida: convencionales (~{conventional_km:.0f} km, sin autovía/peajes)."
                )
        if plan.soc_at_destination_pct is not None and plan.route_distance_km is not None:
            if not plan.reachable_without_stop and plan.route_distance_km > plan.range_km:
                stops_needed = estimate_charging_stops_needed(plan.route_distance_km, plan.range_km)
                bullets.append(
                    f"Sin paradas agotarías la batería ({plan.route_distance_km:.0f} km, "
                    f"autonomía ~{plan.range_km:.0f} km). Mínimo ~{stops_needed} parada(s) en ruta."
                )
            elif plan.soc_at_destination_pct <= 0:
                bullets.append("Sin paradas en ruta agotarías la batería antes del destino.")
            else:
                bullets.append(
                    f"Sin paradas en ruta llegarías con ~{plan.soc_at_destination_pct:.0f} % al destino."
                )
        if plan.planned_stops:
            bullets.append(
                f"Plan multi-parada: {len(plan.planned_stops)} parada(s) ordenada(s) en la ruta activa."
            )
            for stop in plan.planned_stops:
                bullets.append(_format_planned_stop_bullet(stop))
            if plan.projected_soc_at_destination_with_plan is not None:
                bullets.append(
                    f"Con el plan de paradas llegarías al destino con "
                    f"~{plan.projected_soc_at_destination_with_plan:.0f} %."
                )
    elif plan.mode == "emergency":
        bullets.append(f"Modo emergencia · autonomía ~{plan.range_km:.0f} km.")

    if destination_stay:
        bullets.append(f"Zona destino: {destination_stay.summary}.")
        if destination_stay.charge_time_hint not in {s.summary for s in plan.strategies}:
            bullets.append(destination_stay.charge_time_hint)
        if destination_stay.arrival_gap_pct is not None and destination_stay.arrival_gap_pct > 3:
            projected = destination_stay.projected_soc_at_arrival_pct
            if projected is not None and projected < 0:
                bullets.append(
                    "Necesitas paradas de carga en ruta; sin ellas no llegarías al destino."
                )
            else:
                bullets.append(
                    f"Considera cargar en ruta o antes del último tramo: "
                    f"faltan ~{destination_stay.arrival_gap_pct:.0f} % respecto al objetivo recomendado."
                )

    seen_warnings: set[str] = set()
    for warning in plan.warnings[:4]:
        if warning not in seen_warnings:
            bullets.append(f"⚠ {warning}")
            seen_warnings.add(warning)
    for warning in (destination_stay.warnings if destination_stay else [])[:2]:
        if warning not in seen_warnings:
            bullets.append(f"⚠ {warning}")
            seen_warnings.add(warning)

    summary = bullets[0] if bullets else "Plan de carga calculado."
    if destination_stay and destination_stay.infrastructure_level in {"none", "ac_slow"}:
        summary = (
            f"Destino con poca infraestructura rápida: objetivo ≥"
            f"{destination_stay.recommended_soc_at_arrival_pct:.0f} % al llegar."
        )
    return summary, bullets


def destination_stay_to_schema(
    advice: DestinationStayAdvice,
    nearest_ranked: list[tuple[Station, float]] | None = None,
) -> DestinationStayAdviceResult:
    nearest_chargers = (
        nearest_destination_chargers_from_ranked(nearest_ranked) if nearest_ranked else []
    )
    return DestinationStayAdviceResult(
        radius_km=advice.radius_km,
        local_mobility_km=advice.local_mobility_km,
        local_soc_needed_pct=advice.local_soc_needed_pct,
        recommended_soc_at_arrival_pct=advice.recommended_soc_at_arrival_pct,
        minimum_soc_at_arrival_pct=advice.minimum_soc_at_arrival_pct,
        projected_soc_at_arrival_pct=advice.projected_soc_at_arrival_pct,
        arrival_gap_pct=advice.arrival_gap_pct,
        bands={
            "ac_slow": advice.bands.ac_slow,
            "ac_fast": advice.bands.ac_fast,
            "dc_fast": advice.bands.dc_fast,
            "hpc": advice.bands.hpc,
            "total": advice.bands.total,
            "best_max_kw": advice.bands.best_max_kw,
            "nearest_km": advice.bands.nearest_km,
        },
        infrastructure_level=advice.infrastructure_level,
        charge_time_hint=advice.charge_time_hint,
        summary=advice.summary,
        warnings=advice.warnings,
        nearest_chargers=nearest_chargers,
    )
