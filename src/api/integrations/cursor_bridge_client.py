"""Cliente HTTP al cursor-cli-bridge (chat / prompts cortos)."""

from __future__ import annotations

import httpx

from api.config import settings


class CursorBridgeError(Exception):
    pass


def cursor_bridge_configured() -> bool:
    return bool(settings.cursor_bridge_url.strip())


def run_cursor_bridge_prompt(
    prompt: str,
    *,
    timeout_seconds: float | None = None,
) -> str:
    if not cursor_bridge_configured():
        raise CursorBridgeError("CURSOR_BRIDGE_URL no configurado")

    base = settings.cursor_bridge_url.rstrip("/")
    url = f"{base}/invoke" if not base.endswith("/invoke") else base
    timeout = timeout_seconds if timeout_seconds is not None else settings.cursor_bridge_timeout_seconds
    headers = {"Content-Type": "application/json"}
    token = settings.cursor_bridge_token.strip()
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(timeout=timeout) as client:
        response = client.post(url, headers=headers, json={"prompt": prompt})

    if response.status_code != 200:
        raise CursorBridgeError(f"Puente HTTP {response.status_code}: {response.text[:300]}")

    body = response.json()
    if not isinstance(body, dict):
        raise CursorBridgeError("Respuesta del puente inválida")
    if body.get("error"):
        raise CursorBridgeError(str(body["error"]))
    output = body.get("output")
    if isinstance(output, str) and output.strip():
        return output.strip()
    raise CursorBridgeError("Puente sin texto en output")
