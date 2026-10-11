"""Fallos del puente Cursor: siempre CursorBridgeError, nunca excepciones de httpx."""

from __future__ import annotations

import httpx
import pytest

from api import agent_trip_chat
from api.config import settings
from api.integrations import cursor_bridge_client
from api.integrations.cursor_bridge_client import CursorBridgeError, run_cursor_bridge_prompt


@pytest.fixture
def bridge(monkeypatch):
    """Sustituye el transporte HTTP por un manejador de prueba."""
    monkeypatch.setattr(settings, "cursor_bridge_url", "http://puente.test:18765")
    monkeypatch.setattr(settings, "cursor_bridge_token", "t" * 40)
    real_client = httpx.Client

    def use(handler):
        monkeypatch.setattr(
            cursor_bridge_client.httpx,
            "Client",
            lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw),
        )

    return use


def _raise(exc):
    def handler(request):
        raise exc

    return handler


@pytest.mark.parametrize(
    "handler",
    [
        _raise(httpx.ConnectError("caído")),
        _raise(httpx.ReadTimeout("lento")),
        lambda request: httpx.Response(403, json={"error": "forbidden"}),
        lambda request: httpx.Response(200, text="<html>no es json</html>"),
        lambda request: httpx.Response(200, json={"output": "", "error": "cli_nonzero"}),
    ],
    ids=["caido", "tiempo_agotado", "403", "json_roto", "error_cli"],
)
def test_fallos_del_puente_son_cursor_bridge_error(bridge, handler):
    bridge(handler)
    with pytest.raises(CursorBridgeError):
        run_cursor_bridge_prompt("hola")


def test_chat_cae_en_respuesta_local_si_el_puente_esta_caido(bridge):
    bridge(_raise(httpx.ConnectError("caído")))
    assert agent_trip_chat._try_llm_chat_reply("¿paro a comer?", plan_snapshot={}) is None


def test_respuesta_correcta(bridge):
    bridge(lambda request: httpx.Response(200, json={"output": " OK \n", "error": None}))
    assert run_cursor_bridge_prompt("hola") == "OK"


def test_log_por_llamada_sin_contenido(bridge, caplog):
    caplog.set_level("INFO", logger="api.integrations.cursor_bridge_client")
    bridge(
        lambda request: httpx.Response(
            200, json={"output": "respuesta secreta del modelo", "error": None}
        )
    )
    run_cursor_bridge_prompt("pregunta privada del usuario")
    bridge(
        lambda request: httpx.Response(
            502, json={"output": "", "stderr": "detalle interno", "error": "cli_nonzero"}
        )
    )
    with pytest.raises(CursorBridgeError):
        run_cursor_bridge_prompt("otra pregunta privada")

    lines = [r.getMessage() for r in caplog.records]
    assert len(lines) == 2
    assert "resultado=ok" in lines[0] and "output_chars=28" in lines[0]
    assert "resultado=error" in lines[1] and "Puente HTTP 502" in lines[1]
    texto = " ".join(lines)
    for privado in ("pregunta privada", "respuesta secreta", "detalle interno"):
        assert privado not in texto
