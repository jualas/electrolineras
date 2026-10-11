"""Cliente HTTP al cursor-cli-bridge (chat / prompts cortos)."""

from __future__ import annotations

import logging
import time

import httpx

from api.config import settings

logger = logging.getLogger(__name__)


class CursorBridgeError(Exception):
    pass


def cursor_bridge_configured() -> bool:
    return bool(settings.cursor_bridge_url.strip())


def run_cursor_bridge_prompt(
    prompt: str,
    *,
    timeout_seconds: float | None = None,
) -> str:
    """Llama al puente y deja una línea de log por llamada (duración y tamaños, sin contenido)."""
    started = time.monotonic()
    try:
        output = _call_bridge(prompt, timeout_seconds=timeout_seconds)
    except CursorBridgeError as e:
        logger.warning(
            "puente_cursor resultado=error ms=%d prompt_chars=%d motivo=%s",
            (time.monotonic() - started) * 1000,
            len(prompt),
            str(e)[:80],
        )
        raise
    logger.info(
        "puente_cursor resultado=ok ms=%d prompt_chars=%d output_chars=%d",
        (time.monotonic() - started) * 1000,
        len(prompt),
        len(output),
    )
    return output


def _call_bridge(prompt: str, *, timeout_seconds: float | None) -> str:
    if not cursor_bridge_configured():
        raise CursorBridgeError("CURSOR_BRIDGE_URL no configurado")

    base = settings.cursor_bridge_url.rstrip("/")
    url = f"{base}/invoke" if not base.endswith("/invoke") else base
    timeout = (
        timeout_seconds if timeout_seconds is not None else settings.cursor_bridge_timeout_seconds
    )
    headers = {"Content-Type": "application/json"}
    token = settings.cursor_bridge_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Cualquier fallo del puente (caído, tiempo agotado, JSON roto) es CursorBridgeError:
    # el chat cae entonces en la respuesta local en vez de devolver 500.
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, headers=headers, json={"prompt": prompt})
    except httpx.HTTPError as e:
        raise CursorBridgeError(f"Puente no disponible: {type(e).__name__}") from e

    if response.status_code != 200:
        # Sin el cuerpo: puede llevar salida del modelo y este mensaje acaba en el log
        raise CursorBridgeError(f"Puente HTTP {response.status_code}")

    try:
        body = response.json()
    except ValueError as e:
        raise CursorBridgeError("Respuesta del puente no es JSON") from e
    if not isinstance(body, dict):
        raise CursorBridgeError("Respuesta del puente inválida")
    if body.get("error"):
        raise CursorBridgeError(str(body["error"]))
    output = body.get("output")
    if isinstance(output, str) and output.strip():
        return output.strip()
    raise CursorBridgeError("Puente sin texto en output")
