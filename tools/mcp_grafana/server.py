#!/usr/bin/env python3
"""MCP Grafana (solo lectura) para Cursor CLI en el mini PC.

Variables de entorno:
  GRAFANA_BASE_URL   p.ej. http://127.0.0.1:3000
  GRAFANA_API_TOKEN  service account token
  GRAFANA_DATASOURCE_UID  default TeslaMate
  CONSUMPTION_PROFILE_LOOKBACK_DAYS  default 180
  ELECTROLINERAS_API_BASE_URL  opcional, para consumption_summary vía API privada
  PRIVATE_API_TOKEN / session cookie no; usa GRAFANA directo o endpoint privado con token
  ELECTROLINERAS_PRIVATE_TOKEN  opcional Bearer para /api/v1/private/consumption-profile
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

# Permite importar src/api si se ejecuta desde el repo
_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"
if _SRC.is_dir() and str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _grafana_get(path: str) -> Any:
    base = _env("GRAFANA_BASE_URL")
    token = _env("GRAFANA_API_TOKEN")
    if not base or not token:
        raise RuntimeError("Configura GRAFANA_BASE_URL y GRAFANA_API_TOKEN")
    url = f"{base.rstrip('/')}{path}"
    req = Request(url, headers={"Authorization": f"Bearer {token}", "Accept": "application/json"})
    with urlopen(req, timeout=float(_env("GRAFANA_TIMEOUT_SECONDS", "20"))) as resp:
        return json.loads(resp.read().decode())


def _grafana_post(path: str, payload: dict[str, Any]) -> Any:
    base = _env("GRAFANA_BASE_URL")
    token = _env("GRAFANA_API_TOKEN")
    if not base or not token:
        raise RuntimeError("Configura GRAFANA_BASE_URL y GRAFANA_API_TOKEN")
    url = f"{base.rstrip('/')}{path}"
    body = json.dumps(payload).encode()
    req = Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    with urlopen(req, timeout=float(_env("GRAFANA_TIMEOUT_SECONDS", "20"))) as resp:
        return json.loads(resp.read().decode())


def tool_grafana_health() -> dict[str, Any]:
    base = _env("GRAFANA_BASE_URL")
    if not base:
        raise RuntimeError("GRAFANA_BASE_URL no configurada")
    url = f"{base.rstrip('/')}/api/health"
    with urlopen(url, timeout=10) as resp:
        return json.loads(resp.read().decode())


def tool_grafana_list_datasources() -> list[dict[str, Any]]:
    data = _grafana_get("/api/datasources")
    return [
        {
            "id": item.get("id"),
            "uid": item.get("uid"),
            "name": item.get("name"),
            "type": item.get("type"),
        }
        for item in data
    ]


def tool_grafana_query(sql: str, lookback_days: int = 180) -> list[dict[str, Any]]:
    from api.integrations.grafana_client import _rows_from_frame

    uid = _env("GRAFANA_DATASOURCE_UID", "TeslaMate")
    # Límite de seguridad: no queries enormes
    if len(sql) > 8000:
        raise ValueError("SQL demasiado largo (máx. 8000 caracteres)")
    if any(token in sql.lower() for token in ("insert ", "update ", "delete ", "drop ", "alter ")):
        raise ValueError("Solo se permiten consultas de lectura")
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"type": "grafana-postgresql-datasource", "uid": uid},
                "rawSql": sql,
                "format": "table",
            }
        ],
        "from": f"now-{int(lookback_days)}d",
        "to": "now",
    }
    data = _grafana_post("/api/ds/query", payload)
    result = (data.get("results") or {}).get("A") or {}
    frames = result.get("frames") or []
    if not frames:
        return []
    rows = _rows_from_frame(frames[0])
    return rows[:500]


def tool_grafana_consumption_summary(car_id: int | None = None) -> dict[str, Any]:
    api_base = _env("ELECTROLINERAS_API_BASE_URL")
    private_token = _env("ELECTROLINERAS_PRIVATE_TOKEN")
    if api_base and private_token:
        path = "/api/v1/private/consumption-profile"
        if car_id is not None:
            path += f"?car_id={int(car_id)}"
        url = f"{api_base.rstrip('/')}{path}"
        req = Request(
            url,
            headers={
                "Authorization": f"Bearer {private_token}",
                "Accept": "application/json",
            },
        )
        with urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())

    # Agregador local (mismo código que la API)
    os.environ.setdefault("GRAFANA_DATASOURCE_UID", _env("GRAFANA_DATASOURCE_UID", "TeslaMate"))
    from api.integrations.consumption_profile_service import (
        fetch_consumption_profile,
        resolve_consumption_for_route,
    )

    profile = fetch_consumption_profile(car_id=car_id)
    resolved_fast = resolve_consumption_for_route(
        profile,
        route_preference="fastest",
        fallback_wh_per_km=145.0,
    )
    resolved_conv = resolve_consumption_for_route(
        profile,
        route_preference="conventional",
        fallback_wh_per_km=145.0,
    )
    return {
        "profile": profile.as_dict(),
        "for_fastest": {
            "kwh_per_100km": resolved_fast.kwh_per_100km,
            "source": resolved_fast.source,
            "confidence": resolved_fast.confidence,
            "note": resolved_fast.note,
            "bin": resolved_fast.bin,
        },
        "for_conventional": {
            "kwh_per_100km": resolved_conv.kwh_per_100km,
            "source": resolved_conv.source,
            "confidence": resolved_conv.confidence,
            "note": resolved_conv.note,
            "bin": resolved_conv.bin,
        },
    }


def _tool_result(text: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}]}


def _dispatch(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    try:
        if name == "grafana_health":
            data = tool_grafana_health()
        elif name == "grafana_list_datasources":
            data = tool_grafana_list_datasources()
        elif name == "grafana_query":
            data = tool_grafana_query(
                sql=str(arguments.get("sql") or ""),
                lookback_days=int(arguments.get("lookback_days") or 180),
            )
        elif name == "grafana_consumption_summary":
            car_id = arguments.get("car_id")
            data = tool_grafana_consumption_summary(
                car_id=int(car_id) if car_id is not None else None
            )
        else:
            return {
                "content": [{"type": "text", "text": f"Herramienta desconocida: {name}"}],
                "isError": True,
            }
        return _tool_result(json.dumps(data, ensure_ascii=False, indent=2))
    except (HTTPError, URLError, RuntimeError, ValueError, OSError) as exc:
        return {"content": [{"type": "text", "text": str(exc)}], "isError": True}


TOOLS = [
    {
        "name": "grafana_health",
        "description": "Comprueba /api/health de Grafana TeslaMate",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "grafana_list_datasources",
        "description": "Lista datasources Grafana (uid, name, type)",
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "grafana_query",
        "description": "Ejecuta SQL de solo lectura vía Grafana /api/ds/query (máx. 500 filas)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "sql": {"type": "string", "description": "SQL SELECT"},
                "lookback_days": {"type": "integer", "default": 180},
            },
            "required": ["sql"],
            "additionalProperties": False,
        },
    },
    {
        "name": "grafana_consumption_summary",
        "description": "Resumen de bins de consumo histórico (highway/mixed/conventional/mountain)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "car_id": {"type": "integer", "description": "ID TeslaMate (opcional)"},
            },
            "additionalProperties": False,
        },
    },
]


def _handle(message: dict[str, Any]) -> dict[str, Any] | None:
    method = message.get("method")
    msg_id = message.get("id")
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "electrolineras-grafana", "version": "0.1.0"},
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"tools": TOOLS}}
    if method == "tools/call":
        params = message.get("params") or {}
        result = _dispatch(str(params.get("name") or ""), dict(params.get("arguments") or {}))
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {}}
    if msg_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        }
    return None


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = _handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
