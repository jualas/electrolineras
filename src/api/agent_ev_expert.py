"""Criterio de experto EV para el contexto de la guía IA (#6155)."""

from __future__ import annotations

from typing import Any

from api.routing.charging_plan import (
    FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT,
    MIN_WORTHWHILE_SOC_GAIN_PCT,
)
from api.schemas import ChargingPlanResponse, PlannedRouteStopResult

# Alineado con docs/agent/ev_expert_prompt.md (el puente Cursor carga el markdown).
EV_EXPERT_PROMPT_RELATIVE = "docs/agent/ev_expert_prompt.md"


def classify_charge_worthwhile(
    *,
    arrival_soc_pct: float,
    departure_soc_pct: float,
) -> tuple[bool, float, bool]:
    """(worthwhile, soc_gain_pct, micro_stop)."""
    gain = float(departure_soc_pct) - float(arrival_soc_pct)
    micro = (
        arrival_soc_pct + 1e-6 >= FIRST_STOP_COMFORT_ARRIVAL_SOC_PCT
        and gain + 1e-6 < MIN_WORTHWHILE_SOC_GAIN_PCT
    )
    return (not micro, round(gain, 1), micro)


def destination_is_rural(plan: ChargingPlanResponse) -> bool:
    stay = plan.destination_stay
    if not stay:
        return False
    return stay.infrastructure_level in {"none", "ac_slow"}


def enrich_planned_stop_snapshot(stop: PlannedRouteStopResult, base: dict[str, Any]) -> dict[str, Any]:
    worthwhile, gain, micro = classify_charge_worthwhile(
        arrival_soc_pct=stop.soc_arrival_pct,
        departure_soc_pct=stop.soc_departure_pct,
    )
    out = dict(base)
    out["wrong_side"] = stop.wrong_side
    out["soc_gain_pct"] = gain
    out["charge_worthwhile"] = worthwhile
    out["micro_stop"] = micro
    return out


def ev_expert_plan_hints(plan: ChargingPlanResponse) -> dict[str, Any]:
    summary = plan.route_trip_summary
    return {
        "eta_note": "osrm_speed_adjusted_no_live_traffic",
        "eta_includes_charge": bool(summary and summary.total_charge_minutes > 0),
        "driving_duration_minutes": summary.driving_duration_minutes if summary else plan.route_duration_minutes,
        "total_duration_minutes": summary.total_duration_minutes if summary else None,
        "total_charge_minutes": summary.total_charge_minutes if summary else None,
        "destination_rural": destination_is_rural(plan),
        "destination_infrastructure_level": (
            plan.destination_stay.infrastructure_level if plan.destination_stay else None
        ),
    }
