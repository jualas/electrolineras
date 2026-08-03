from __future__ import annotations

from typing import Literal

from api.agent_narration import build_agent_narration
from api.integrations.dify_client import (
    DifyError,
    dify_trip_guide_configured,
    run_trip_guide_workflow,
    trip_context_payload,
)
from api.integrations.poi_hints import fetch_destination_poi_hints
from api.schemas import (
    ChargingPlanResponse,
    ConsumptionBinName,
    ConsumptionConfidence,
    ConsumptionProfileResponse,
    ConsumptionSource,
    PlannedRouteStopResult,
    TripGuideContext,
    TripGuideResponse,
    VehicleTelemetryResult,
)


def _charging_while_visiting_hint(plan: ChargingPlanResponse) -> str | None:
    stay = plan.destination_stay
    if not stay or not stay.nearest_chargers:
        return None
    nearest = stay.nearest_chargers[0]
    if nearest.power_band in {"ac_slow", "ac_fast"}:
        return (
            f"Carga lenta cerca del destino ({nearest.label}, ~{nearest.distance_km:.1f} km). "
            "Combina visitas cercanas mientras el coche carga."
        )
    return (
        f"Carga rápida disponible (~{nearest.max_power_kw:.0f} kW, "
        f"{nearest.distance_km:.1f} km del destino); paradas cortas entre visitas."
    )


def _planned_stop_snapshot(stop: PlannedRouteStopResult) -> dict:
    return {
        "order": stop.order,
        "station_id": stop.station.id,
        "label": stop.station.site_name or stop.station.location.address,
        "operator": stop.operator or stop.station.operator,
        "max_power_kw": stop.station.max_power_kw,
        "route_distance_km": stop.route_distance_km,
        "leg_distance_km": stop.leg_distance_km,
        "leg_driving_minutes": stop.leg_driving_minutes,
        "distance_from_origin_km": stop.distance_from_origin_km,
        "deviation_km": stop.deviation_km,
        "extra_minutes": stop.extra_minutes,
        "soc_arrival_pct": stop.soc_arrival_pct,
        "soc_departure_pct": stop.soc_departure_pct,
        "charge_minutes": stop.charge_minutes,
        "classification": stop.classification,
        "leg_energy_kwh": stop.leg_energy_kwh,
        "recommended_charge_from_pct": stop.recommended_charge_from_pct,
        "recommended_charge_to_pct": stop.recommended_charge_to_pct,
        "effective_charge_power_kw": stop.effective_charge_power_kw,
        "estimated_charge_cost_eur": stop.estimated_charge_cost_eur,
    }


def _plan_snapshot(plan: ChargingPlanResponse) -> dict:
    snapshot: dict = {
        "mode": plan.mode,
        "range_km": plan.range_km,
        "charging_reach_km": plan.charging_reach_km,
        "geodesic_distance_km": plan.geodesic_distance_km,
        "route_distance_km": plan.route_distance_km,
        "route_duration_minutes": plan.route_duration_minutes,
        "route_shortest_distance_km": plan.route_shortest_distance_km,
        "route_fastest_distance_km": plan.route_fastest_distance_km,
        "route_conventional_distance_km": plan.route_conventional_distance_km,
        "route_conventional_duration_minutes": plan.route_conventional_duration_minutes,
        "route_variants_approximate": plan.route_variants_approximate,
        "route_preference": plan.route_preference,
        "avoid_highways": plan.avoid_highways,
        "soc_at_destination_pct": plan.soc_at_destination_pct,
        "projected_soc_at_destination_with_plan": plan.projected_soc_at_destination_with_plan,
        "reachable_without_stop": plan.reachable_without_stop,
        "warnings": plan.warnings,
        "stops": [
            {
                "station_id": stop.station.id,
                "label": stop.station.site_name or stop.station.location.address,
                "max_power_kw": stop.station.max_power_kw,
                "soc_arrival_pct": stop.soc_arrival_pct,
                "route_distance_km": stop.route_distance_km,
            }
            for stop in plan.stops
        ],
        "planned_stops": [_planned_stop_snapshot(stop) for stop in plan.planned_stops],
        "strategies": [
            {
                "id": strategy.id,
                "label": strategy.label,
                "summary": strategy.summary,
                "soc_arrival_pct": strategy.soc_arrival_pct,
            }
            for strategy in plan.strategies
        ],
        "consumption_source": plan.consumption_source,
        "consumption_kwh_per_100km": plan.consumption_kwh_per_100km,
        "consumption_confidence": plan.consumption_confidence,
        "consumption_note": plan.consumption_note,
        "consumption_bin": plan.consumption_bin,
    }
    if plan.route_trip_summary is not None:
        snapshot["route_trip_summary"] = plan.route_trip_summary.model_dump()
    if plan.destination_stay:
        snapshot["destination_stay"] = {
            "recommended_soc_at_arrival_pct": plan.destination_stay.recommended_soc_at_arrival_pct,
            "minimum_soc_at_arrival_pct": plan.destination_stay.minimum_soc_at_arrival_pct,
            "projected_soc_at_arrival_pct": plan.destination_stay.projected_soc_at_arrival_pct,
            "arrival_gap_pct": plan.destination_stay.arrival_gap_pct,
            "infrastructure_level": plan.destination_stay.infrastructure_level,
            "summary": plan.destination_stay.summary,
            "charge_time_hint": plan.destination_stay.charge_time_hint,
            "nearest_chargers": [
                charger.model_dump() for charger in plan.destination_stay.nearest_chargers
            ],
        }
    return snapshot


def _vehicle_snapshot(vehicle: VehicleTelemetryResult | None) -> dict:
    if not vehicle:
        return {}
    return {
        "display_name": vehicle.display_name,
        "car_model_label": vehicle.car_model_label,
        "battery_level_pct": vehicle.battery_level_pct,
        "rated_battery_range_km": vehicle.rated_battery_range_km,
        "est_battery_range_km": vehicle.est_battery_range_km,
        "charging_state": vehicle.charging_state,
        "outside_temp_c": vehicle.outside_temp_c,
    }


def build_trip_guide_context(
    plan: ChargingPlanResponse,
    *,
    vehicle: VehicleTelemetryResult | None = None,
    destination_label: str | None = None,
    cultural_poi_enabled: bool = False,
    user_note: str | None = None,
    consumption_profile: ConsumptionProfileResponse | None = None,
    consumption_source: ConsumptionSource | None = None,
    consumption_kwh_per_100km: float | None = None,
    consumption_confidence: ConsumptionConfidence | None = None,
    consumption_note: str | None = None,
    consumption_bin: ConsumptionBinName | None = None,
) -> TripGuideContext:
    poi_hints: list[str] = []
    if cultural_poi_enabled and plan.destination:
        poi_hints = fetch_destination_poi_hints(
            plan.destination.lat,
            plan.destination.lon,
            destination_label,
        )

    nearest = plan.destination_stay.nearest_chargers if plan.destination_stay else []

    return TripGuideContext(
        destination_label=destination_label,
        cultural_poi_enabled=cultural_poi_enabled,
        user_note=(user_note or "").strip() or None,
        poi_hints=poi_hints,
        nearest_destination_chargers=nearest,
        charging_while_visiting_hint=_charging_while_visiting_hint(plan),
        vehicle_snapshot=_vehicle_snapshot(vehicle),
        plan_snapshot=_plan_snapshot(plan),
        consumption_profile=consumption_profile,
        consumption_source=consumption_source if consumption_source is not None else plan.consumption_source,
        consumption_kwh_per_100km=(
            consumption_kwh_per_100km
            if consumption_kwh_per_100km is not None
            else plan.consumption_kwh_per_100km
        ),
        consumption_confidence=(
            consumption_confidence
            if consumption_confidence is not None
            else plan.consumption_confidence
        ),
        consumption_note=consumption_note if consumption_note is not None else plan.consumption_note,
        consumption_bin=consumption_bin if consumption_bin is not None else plan.consumption_bin,
    )


def format_deterministic_guide(
    summary: str,
    bullets: list[str],
    context: TripGuideContext,
) -> str:
    lines = ["## Resumen del viaje", summary, ""]
    snapshot = context.plan_snapshot
    if snapshot.get("mode") == "route" and snapshot.get("route_distance_km") is not None:
        lines.append("### Comparativa de rutas")
        geodesic = snapshot.get("geodesic_distance_km")
        if geodesic:
            lines.append(f"- Línea recta: ~{geodesic:.0f} km")
        lines.append(f"- Ruta activa: ~{snapshot['route_distance_km']:.0f} km")
        shortest = snapshot.get("route_shortest_distance_km")
        fastest = snapshot.get("route_fastest_distance_km")
        conventional = snapshot.get("route_conventional_distance_km")
        if shortest is not None:
            lines.append(f"- Referencia corta: ~{shortest:.0f} km")
        if fastest is not None:
            lines.append(f"- Referencia rápida: ~{fastest:.0f} km")
        if conventional is not None:
            lines.append(f"- Referencia convencionales: ~{conventional:.0f} km")
        if snapshot.get("route_variants_approximate"):
            lines.append("- _Variantes de referencia aproximadas (OSRM no disponible)._")
        lines.append("")

    if context.consumption_note or context.consumption_kwh_per_100km is not None:
        lines.append("### Consumo del plan")
        if context.consumption_note:
            lines.append(f"- {context.consumption_note}")
        elif context.consumption_kwh_per_100km is not None:
            lines.append(f"- Consumo efectivo: **{context.consumption_kwh_per_100km:.1f} kWh/100 km**")
        if context.consumption_source:
            lines.append(f"- Fuente: `{context.consumption_source}`")
        if context.consumption_confidence:
            lines.append(f"- Confianza: `{context.consumption_confidence}`")
        profile = context.consumption_profile
        if profile and profile.available and profile.bins:
            bin_bits = []
            for key in ("highway", "mixed", "conventional", "mountain"):
                stats = profile.bins.get(key)
                if stats and stats.kwh_per_100km is not None and stats.sample_count > 0:
                    bin_bits.append(f"{key} {stats.kwh_per_100km:.1f} ({stats.sample_count})")
            if bin_bits:
                lines.append(f"- Bins históricos (≥{profile.min_distance_km:.0f} km): " + "; ".join(bin_bits))
        lines.append("")

    if bullets:
        lines.append("### Plan de carga")
        lines.extend(f"- {bullet}" for bullet in bullets)
        lines.append("")

    trip_summary = snapshot.get("route_trip_summary")
    if trip_summary:
        lines.append("### Resumen REVE")
        lines.append(
            f"- Tiempo total ~{trip_summary.get('total_duration_minutes', 0):.0f} min "
            f"(conducción ~{trip_summary.get('driving_duration_minutes', 0):.0f} min, "
            f"carga ~{trip_summary.get('total_charge_minutes', 0):.0f} min)"
        )
        lines.append(
            f"- Energía ~{trip_summary.get('total_energy_kwh', 0):.0f} kWh · "
            f"{trip_summary.get('stop_count', 0)} parada(s)"
        )
        if trip_summary.get("estimated_charge_cost_eur") is not None:
            lines.append(f"- Coste carga est. ~{trip_summary['estimated_charge_cost_eur']:.2f} €")
        lines.append("")

    planned_stops = snapshot.get("planned_stops") or []
    if planned_stops:
        lines.append("### Paradas planificadas")
        for stop in planned_stops:
            charge_text = (
                f" · carga ~{stop['charge_minutes']:.0f} min → {stop['soc_departure_pct']:.0f} %"
                if stop.get("charge_minutes", 0) > 0
                else f" · salida ~{stop['soc_departure_pct']:.0f} %"
            )
            energy = (
                f" · {stop['leg_energy_kwh']:.1f} kWh"
                if stop.get("leg_energy_kwh") is not None
                else ""
            )
            charge_band = ""
            if (
                stop.get("recommended_charge_from_pct") is not None
                and stop.get("recommended_charge_to_pct") is not None
            ):
                charge_band = (
                    f" · recarga {stop['recommended_charge_from_pct']:.0f}→"
                    f"{stop['recommended_charge_to_pct']:.0f} %"
                )
            cost = (
                f" · ~{stop['estimated_charge_cost_eur']:.2f} €"
                if stop.get("estimated_charge_cost_eur") is not None
                else ""
            )
            lines.append(
                f"- **{stop['order']}.** {stop['label']} "
                f"(km {stop['route_distance_km']:.0f}, tramo {stop['leg_distance_km']:.0f} km"
                f"{energy}) · "
                f"llegada ~{stop['soc_arrival_pct']:.0f} %{charge_text}{charge_band} · "
                f"{stop['max_power_kw']:.0f} kW · {stop['classification']}{cost}"
            )
        projected = snapshot.get("projected_soc_at_destination_with_plan")
        if projected is not None:
            lines.append(f"- SOC estimado en destino con plan: **~{projected:.0f} %**")
        lines.append("")

    if context.plan_snapshot.get("destination_stay"):
        stay = context.plan_snapshot["destination_stay"]
        lines.append("### Garantía en destino")
        lines.append(
            f"- SOC recomendado al llegar: **{stay['recommended_soc_at_arrival_pct']:.0f} %** "
            f"(mínimo {stay['minimum_soc_at_arrival_pct']:.0f} %)"
        )
        if stay.get("projected_soc_at_arrival_pct") is not None:
            lines.append(f"- Sin paradas en ruta: ~{stay['projected_soc_at_arrival_pct']:.0f} %")
        if stay.get("arrival_gap_pct") is not None and stay["arrival_gap_pct"] > 3:
            lines.append(
                f"- Falta ~{stay['arrival_gap_pct']:.0f} % respecto al objetivo; "
                "considera cargar en ruta."
            )
        lines.append(f"- {stay['charge_time_hint']}")
        lines.append("")

    if context.nearest_destination_chargers:
        lines.append("### Cargadores más cercanos al destino")
        for charger in context.nearest_destination_chargers:
            lines.append(
                f"- {charger.label} · {charger.max_power_kw:.0f} kW · "
                f"{charger.distance_km:.1f} km ({charger.power_band})"
            )
        lines.append("")

    if context.charging_while_visiting_hint:
        lines.append("### Mientras cargas")
        lines.append(context.charging_while_visiting_hint)
        lines.append("")

    if context.poi_hints:
        lines.append("### Ideas en la zona")
        lines.extend(f"- {hint}" for hint in context.poi_hints)
        lines.append("")

    if not dify_trip_guide_configured():
        lines.append(
            "_Guía generada por el motor local. Configura `DIFY_API_BASE_URL` y "
            "`DIFY_TRIP_WORKFLOW_API_KEY` para narrativa IA._"
        )

    return "\n".join(lines).strip()


def build_trip_guide_response(
    plan: ChargingPlanResponse,
    *,
    vehicle: VehicleTelemetryResult | None = None,
    destination_label: str | None = None,
    cultural_poi_enabled: bool = False,
    user_note: str | None = None,
    invoke_dify: bool = True,
    consumption_profile: ConsumptionProfileResponse | None = None,
    consumption_source: ConsumptionSource | None = None,
    consumption_kwh_per_100km: float | None = None,
    consumption_confidence: ConsumptionConfidence | None = None,
    consumption_note: str | None = None,
    consumption_bin: ConsumptionBinName | None = None,
) -> TripGuideResponse:
    summary, bullets = build_agent_narration(plan)
    context = build_trip_guide_context(
        plan,
        vehicle=vehicle,
        destination_label=destination_label,
        cultural_poi_enabled=cultural_poi_enabled,
        user_note=user_note,
        consumption_profile=consumption_profile,
        consumption_source=consumption_source,
        consumption_kwh_per_100km=consumption_kwh_per_100km,
        consumption_confidence=consumption_confidence,
        consumption_note=consumption_note,
        consumption_bin=consumption_bin,
    )

    guide_source: Literal["deterministic", "dify"] = "deterministic"
    guide_text = format_deterministic_guide(summary, bullets, context)

    if invoke_dify and dify_trip_guide_configured():
        try:
            context_dict = context.model_dump()
            guide_text = run_trip_guide_workflow(
                trip_context_json=trip_context_payload(context_dict),
                agent_summary=summary,
            )
            guide_source = "dify"
        except DifyError:
            pass

    return TripGuideResponse(
        plan=plan,
        agent_summary=summary,
        agent_bullets=bullets,
        vehicle=vehicle,
        guide_text=guide_text,
        guide_source=guide_source,
        context=context,
    )
