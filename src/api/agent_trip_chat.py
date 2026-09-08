"""Chat interactivo sobre el plan (#6166): intents + respuesta corta (sin monólogo)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from api.integrations.cursor_bridge_client import (
    CursorBridgeError,
    cursor_bridge_configured,
    run_cursor_bridge_prompt,
)

ReplySource = Literal["deterministic", "llm", "fallback"]

CHAT_PROMPT_RELATIVE = "docs/agent/ev_chat_prompt.md"

_CHIP_MESSAGES: dict[str, str] = {
    "why_stop": "¿Por qué elegiste estas paradas?",
    "avoid_tolls": "Quiero evitar peajes",
    "fastest": "Prefiero la ruta más rápida por autopista",
    "cheaper": "Prioriza cargadores más baratos",
    "fewer_stops": "Quiero parar menos veces, aunque cargue más en cada parada",
    "less_charge": "Carga menos en cada parada (zona rápida DC)",
}


@dataclass
class PlanningOverrides:
    route_preference: str | None = None
    avoid_highways: bool | None = None
    max_charge_soc_pct: float | None = None
    max_price_eur_kwh: float | None = None
    preferred_operators: list[str] | None = None

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        if self.route_preference is not None:
            out["route_preference"] = self.route_preference
        if self.avoid_highways is not None:
            out["avoid_highways"] = self.avoid_highways
        if self.max_charge_soc_pct is not None:
            out["max_charge_soc_pct"] = self.max_charge_soc_pct
        if self.max_price_eur_kwh is not None:
            out["max_price_eur_kwh"] = self.max_price_eur_kwh
        if self.preferred_operators is not None:
            out["preferred_operators"] = self.preferred_operators
        return out

    def needs_replan(self) -> bool:
        return bool(self.as_dict())


@dataclass
class ChatTurnResult:
    reply: str
    reply_source: ReplySource
    intent_id: str | None = None
    overrides: PlanningOverrides = field(default_factory=PlanningOverrides)
    needs_replan: bool = False


def chat_action_chips() -> list[dict[str, str]]:
    return [
        {"id": "avoid_tolls", "label": "Sin peajes", "message": _CHIP_MESSAGES["avoid_tolls"]},
        {"id": "fastest", "label": "Más rápida", "message": _CHIP_MESSAGES["fastest"]},
        {"id": "fewer_stops", "label": "Parar menos", "message": _CHIP_MESSAGES["fewer_stops"]},
        {"id": "why_stop", "label": "¿Por qué estas?", "message": _CHIP_MESSAGES["why_stop"]},
    ]


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _load_chat_prompt_rules() -> str:
    root = Path(__file__).resolve().parents[2]
    path = root / CHAT_PROMPT_RELATIVE
    try:
        text = path.read_text(encoding="utf-8").strip()
        if text:
            return text
    except OSError:
        pass
    return (
        "Eres copiloto EV. No reexpliques el plan. Respuestas cortas en español. "
        "Usa solo plan_snapshot y el mensaje del usuario."
    )


def _explain_stops(plan_snapshot: dict[str, Any] | None) -> str:
    if not plan_snapshot:
        return "Aún no hay plan cargado. Calcula el plan en el mapa y vuelve a preguntar."
    stops = plan_snapshot.get("planned_stops") or []
    if not stops:
        reach = plan_snapshot.get("charging_reach_km")
        if plan_snapshot.get("reachable_without_stop"):
            return "El motor estima que llegas sin parar; no hay paradas de carga en el plan."
        return (
            f"No hay paradas planificadas (alcance ~{reach:.0f} km)."
            if isinstance(reach, (int, float))
            else "No hay paradas planificadas en este momento."
        )
    first = stops[0]
    label = first.get("label") or first.get("station_id") or "la primera"
    bits = [
        f"La app elige paradas por batería (no por reloj). Primera útil: {label}",
    ]
    if first.get("micro_stop"):
        bits.append("hay alguna marcada como micro-parada: no compensa como carga de viaje.")
    else:
        gain = first.get("soc_gain_pct")
        if isinstance(gain, (int, float)):
            bits.append(f"ganancia ~{gain:.0f} % SOC en esa parada.")
    n = len(stops)
    bits.append(f"En total {n} parada{'s' if n != 1 else ''} (detalle en el panel).")
    return " ".join(bits)


def interpret_trip_chat_message(
    message: str,
    *,
    plan_snapshot: dict[str, Any] | None = None,
) -> ChatTurnResult:
    """Intents deterministas; si no hay match → LLM opcional o fallback corto."""
    raw = (message or "").strip()
    if not raw:
        return ChatTurnResult(
            reply="Escribe qué quieres cambiar o pulsa un chip.",
            reply_source="deterministic",
            intent_id="empty",
        )

    text = _norm(raw)
    overrides = PlanningOverrides()

    # Chips / frases exactas primero
    for chip_id, chip_msg in _CHIP_MESSAGES.items():
        if text == _norm(chip_msg) or text == chip_id.replace("_", " "):
            return _result_for_chip(chip_id, plan_snapshot)

    if any(k in text for k in ("por qué", "porque", "motivo", "estas paradas", "esta parada")):
        return ChatTurnResult(
            reply=_explain_stops(plan_snapshot),
            reply_source="deterministic",
            intent_id="why_stop",
        )

    if any(k in text for k in ("evitar peaje", "sin peaje", "no peaje", "evitar peajes")):
        overrides.avoid_highways = True
        return ChatTurnResult(
            reply="De acuerdo: recalculo evitando peajes. El mapa se actualizará.",
            reply_source="deterministic",
            intent_id="avoid_tolls",
            overrides=overrides,
            needs_replan=True,
        )

    if any(k in text for k in ("más rápida", "mas rapida", "autopista", "con peaje", "rápida")):
        overrides.avoid_highways = False
        overrides.route_preference = "fastest"
        return ChatTurnResult(
            reply="Paso a ruta más rápida (autopista). Recalculo el plan.",
            reply_source="deterministic",
            intent_id="fastest",
            overrides=overrides,
            needs_replan=True,
        )

    if any(k in text for k in ("más corta", "mas corta", "menos km", "ruta corta")):
        overrides.route_preference = "shortest"
        return ChatTurnResult(
            reply="Priorizo la ruta más corta. Recalculo el plan.",
            reply_source="deterministic",
            intent_id="shortest",
            overrides=overrides,
            needs_replan=True,
        )

    if any(k in text for k in ("más barat", "mas barat", "precio", "barato", "€/kwh", "eur/kwh")):
        overrides.max_price_eur_kwh = 0.45
        return ChatTurnResult(
            reply="Filtro hacia cargadores ≤0,45 €/kWh cuando haya dato de precio. Recalculo.",
            reply_source="deterministic",
            intent_id="cheaper",
            overrides=overrides,
            needs_replan=True,
        )

    if any(k in text for k in ("parar menos", "menos paradas", "menos parada", "pocas paradas")):
        overrides.max_charge_soc_pct = 80.0
        return ChatTurnResult(
            reply="Subo el techo de carga a ~80 % para intentar menos paradas. Recalculo.",
            reply_source="deterministic",
            intent_id="fewer_stops",
            overrides=overrides,
            needs_replan=True,
        )

    if any(
        k in text
        for k in ("cargar menos", "carga menos", "menos carga", "zona rápida", "hasta 65", "sweet")
    ):
        overrides.max_charge_soc_pct = 65.0
        return ChatTurnResult(
            reply="Limito la carga por parada a ~65 % (zona DC más rápida). Recalculo.",
            reply_source="deterministic",
            intent_id="less_charge",
            overrides=overrides,
            needs_replan=True,
        )

    for op in ("ionity", "atlante", "zunder", "tesla", "wenea", "electra"):
        if op in text and any(k in text for k in ("prefer", "solo", "prioriz", "quiero")):
            overrides.preferred_operators = [op.capitalize() if op != "tesla" else "Tesla"]
            return ChatTurnResult(
                reply=f"Priorizo operador {overrides.preferred_operators[0]} en el ranking. Recalculo.",
                reply_source="deterministic",
                intent_id="prefer_operator",
                overrides=overrides,
                needs_replan=True,
            )

    return ChatTurnResult(
        reply=(
            "Puedo aplicar cambios del plan (peajes, ruta rápida/corta, precio, techo de carga) "
            "o explicar las paradas. Usa un chip o reformula en una frase."
        ),
        reply_source="fallback",
        intent_id="open",
    )


def _result_for_chip(chip_id: str, plan_snapshot: dict[str, Any] | None) -> ChatTurnResult:
    overrides = PlanningOverrides()
    if chip_id == "why_stop":
        return ChatTurnResult(
            reply=_explain_stops(plan_snapshot),
            reply_source="deterministic",
            intent_id="why_stop",
        )
    if chip_id == "avoid_tolls":
        overrides.avoid_highways = True
        return ChatTurnResult(
            reply="De acuerdo: recalculo evitando peajes. El mapa se actualizará.",
            reply_source="deterministic",
            intent_id="avoid_tolls",
            overrides=overrides,
            needs_replan=True,
        )
    if chip_id == "fastest":
        overrides.avoid_highways = False
        overrides.route_preference = "fastest"
        return ChatTurnResult(
            reply="Paso a ruta más rápida (autopista). Recalculo el plan.",
            reply_source="deterministic",
            intent_id="fastest",
            overrides=overrides,
            needs_replan=True,
        )
    if chip_id == "cheaper":
        overrides.max_price_eur_kwh = 0.45
        return ChatTurnResult(
            reply="Filtro hacia cargadores ≤0,45 €/kWh cuando haya dato de precio. Recalculo.",
            reply_source="deterministic",
            intent_id="cheaper",
            overrides=overrides,
            needs_replan=True,
        )
    if chip_id == "fewer_stops":
        overrides.max_charge_soc_pct = 80.0
        return ChatTurnResult(
            reply="Subo el techo de carga a ~80 % para intentar menos paradas. Recalculo.",
            reply_source="deterministic",
            intent_id="fewer_stops",
            overrides=overrides,
            needs_replan=True,
        )
    if chip_id == "less_charge":
        overrides.max_charge_soc_pct = 65.0
        return ChatTurnResult(
            reply="Limito la carga por parada a ~65 % (zona DC más rápida). Recalculo.",
            reply_source="deterministic",
            intent_id="less_charge",
            overrides=overrides,
            needs_replan=True,
        )
    return ChatTurnResult(
        reply="Chip no reconocido.",
        reply_source="fallback",
        intent_id=chip_id,
    )


def _compact_plan_for_llm(plan_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not plan_snapshot:
        return {}
    stops = plan_snapshot.get("planned_stops") or []
    compact_stops = [
        {
            "order": s.get("order"),
            "label": s.get("label"),
            "operator": s.get("operator"),
            "kw": s.get("max_power_kw"),
            "soc_in": s.get("soc_arrival_pct"),
            "soc_out": s.get("soc_departure_pct"),
            "micro_stop": s.get("micro_stop"),
            "wrong_side": s.get("wrong_side"),
        }
        for s in stops[:6]
    ]
    return {
        "route_km": plan_snapshot.get("route_distance_km"),
        "route_preference": plan_snapshot.get("route_preference"),
        "avoid_highways": plan_snapshot.get("avoid_highways"),
        "proj_soc_dest": plan_snapshot.get("projected_soc_at_destination_with_plan"),
        "warnings": (plan_snapshot.get("warnings") or [])[:3],
        "planned_stops": compact_stops,
        "ev_expert": plan_snapshot.get("ev_expert"),
    }


def _try_llm_chat_reply(
    message: str,
    *,
    plan_snapshot: dict[str, Any] | None,
    history: list[dict[str, str]] | None = None,
) -> str | None:
    if not cursor_bridge_configured():
        return None
    hist_lines: list[str] = []
    for item in (history or [])[-6:]:
        role = item.get("role", "user")
        content = (item.get("content") or "").strip()
        if content:
            hist_lines.append(f"{role}: {content}")
    prompt = (
        f"{_load_chat_prompt_rules()}\n\n"
        f"plan_snapshot (compacto):\n{json.dumps(_compact_plan_for_llm(plan_snapshot), ensure_ascii=False)}\n\n"
    )
    if hist_lines:
        prompt += "Historial reciente:\n" + "\n".join(hist_lines) + "\n\n"
    prompt += f"Mensaje del usuario:\n{message.strip()}\n"
    try:
        return run_cursor_bridge_prompt(prompt)
    except CursorBridgeError:
        return None


def handle_trip_chat_turn(
    message: str,
    *,
    plan_snapshot: dict[str, Any] | None = None,
    history: list[dict[str, str]] | None = None,
    allow_llm: bool = True,
) -> ChatTurnResult:
    """Entrada principal del endpoint de chat."""
    result = interpret_trip_chat_message(message, plan_snapshot=plan_snapshot)
    if allow_llm and result.intent_id == "open" and result.reply_source == "fallback":
        llm = _try_llm_chat_reply(message, plan_snapshot=plan_snapshot, history=history)
        if llm:
            return ChatTurnResult(reply=llm, reply_source="llm", intent_id="open")
    return result
