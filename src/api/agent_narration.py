from __future__ import annotations

from api.routing.destination_stay import DestinationStayAdvice
from api.schemas import ChargingPlanResponse, DestinationStayAdviceResult


def build_agent_narration(
    plan: ChargingPlanResponse,
    destination_stay: DestinationStayAdviceResult | None = None,
) -> tuple[str, list[str]]:
    destination_stay = destination_stay or plan.destination_stay
    bullets: list[str] = []

    if plan.mode == "route" and plan.destination:
        bullets.append(
            f"Ruta ~{plan.route_distance_km:.0f} km · autonomía útil ~{plan.range_km:.0f} km "
            f"(SOC {plan.vehicle.soc_percent:.0f} %)."
        )
        if plan.soc_at_destination_pct is not None:
            bullets.append(
                f"Sin paradas en ruta llegarías con ~{plan.soc_at_destination_pct:.0f} % al destino."
            )
    elif plan.mode == "emergency":
        bullets.append(f"Modo emergencia · autonomía ~{plan.range_km:.0f} km.")

    for strategy in plan.strategies[:4]:
        bullets.append(f"{strategy.label}: {strategy.summary}")

    if destination_stay:
        bullets.append(f"Zona destino: {destination_stay.summary}.")
        bullets.append(destination_stay.charge_time_hint)
        if destination_stay.arrival_gap_pct is not None and destination_stay.arrival_gap_pct > 3:
            bullets.append(
                f"Considera cargar en ruta o antes del último tramo: "
                f"faltan ~{destination_stay.arrival_gap_pct:.0f} % respecto al objetivo recomendado."
            )

    for warning in plan.warnings[:3]:
        bullets.append(f"⚠ {warning}")
    for warning in (destination_stay.warnings if destination_stay else [])[:2]:
        bullets.append(f"⚠ {warning}")

    summary = bullets[0] if bullets else "Plan de carga calculado."
    if destination_stay and destination_stay.infrastructure_level in {"none", "ac_slow"}:
        summary = (
            f"Destino con poca infraestructura rápida: objetivo ≥"
            f"{destination_stay.recommended_soc_at_arrival_pct:.0f} % al llegar."
        )
    return summary, bullets


def destination_stay_to_schema(advice: DestinationStayAdvice) -> DestinationStayAdviceResult:
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
    )
