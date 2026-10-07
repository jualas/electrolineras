from __future__ import annotations

from api.agent_trip_chat import (
    chat_action_chips,
    handle_trip_chat_turn,
    interpret_trip_chat_message,
)


def test_chips_include_core_actions() -> None:
    ids = {chip["id"] for chip in chat_action_chips()}
    assert {"why_stop", "avoid_tolls", "fastest", "fewer_stops"} <= ids
    assert len(ids) == 4


def test_avoid_tolls_intent_replans() -> None:
    turn = interpret_trip_chat_message("Quiero evitar peajes")
    assert turn.needs_replan is True
    assert turn.overrides.avoid_highways is True
    assert turn.reply_source == "deterministic"


def test_fastest_intent() -> None:
    turn = interpret_trip_chat_message("Prefiero la ruta más rápida por autopista")
    assert turn.needs_replan is True
    assert turn.overrides.route_preference == "fastest"
    assert turn.overrides.avoid_highways is False


def test_why_stop_uses_plan_snapshot() -> None:
    snapshot = {
        "planned_stops": [
            {
                "order": 1,
                "label": "Hellín",
                "soc_gain_pct": 40.0,
                "micro_stop": False,
            }
        ],
        "charging_reach_km": 180,
    }
    turn = handle_trip_chat_turn(
        "¿Por qué elegiste estas paradas?",
        plan_snapshot=snapshot,
        allow_llm=False,
    )
    assert turn.intent_id == "why_stop"
    assert "Hellín" in turn.reply
    assert turn.needs_replan is False


def test_open_question_fallback_without_llm() -> None:
    turn = handle_trip_chat_turn("¿Hay un buen sitio para café?", allow_llm=False)
    assert turn.intent_id == "open"
    assert turn.reply_source == "fallback"
