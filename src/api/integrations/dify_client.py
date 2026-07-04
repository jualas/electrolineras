from __future__ import annotations

import json

import httpx

from api.config import settings


class DifyError(Exception):
    pass


def dify_trip_guide_configured() -> bool:
    return bool(settings.dify_api_base_url.strip() and settings.dify_trip_workflow_api_key.strip())


def run_trip_guide_workflow(
    *,
    trip_context_json: str,
    agent_summary: str,
    user: str = "electrolineras",
) -> str:
    if not dify_trip_guide_configured():
        raise DifyError("Workflow Dify de guía de viaje no configurado")

    base = settings.dify_api_base_url.rstrip("/")
    url = f"{base}/v1/workflows/run"
    headers = {
        "Authorization": f"Bearer {settings.dify_trip_workflow_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "inputs": {
            "trip_context_json": trip_context_json,
            "agent_summary": agent_summary,
        },
        "response_mode": "blocking",
        "user": user,
    }

    with httpx.Client(timeout=settings.dify_timeout_seconds) as client:
        response = client.post(url, headers=headers, json=payload)

    if response.status_code != 200:
        raise DifyError(f"Dify respondió HTTP {response.status_code}: {response.text[:300]}")

    body = response.json()
    data = body.get("data") if isinstance(body, dict) else None
    if not isinstance(data, dict):
        raise DifyError("Respuesta Dify inválida")

    outputs = data.get("outputs")
    if not isinstance(outputs, dict):
        raise DifyError("Workflow Dify sin outputs")

    for key in ("guide_text", "text", "result", "output"):
        value = outputs.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    raise DifyError("Workflow Dify sin texto de guía en outputs")


def trip_context_payload(context: dict) -> str:
    return json.dumps(context, ensure_ascii=False, separators=(",", ":"))
