from __future__ import annotations

from typing import Any

import httpx

from api.config import settings


class GrafanaError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def grafana_configured() -> bool:
    return bool(settings.grafana_base_url.strip() and settings.grafana_api_token.strip())


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {settings.grafana_api_token.strip()}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def grafana_health() -> dict[str, Any]:
    if not settings.grafana_base_url.strip():
        raise GrafanaError("GRAFANA_BASE_URL no configurada")
    url = f"{settings.grafana_base_url.rstrip('/')}/api/health"
    with httpx.Client(timeout=settings.grafana_timeout_seconds) as client:
        response = client.get(url)
    if response.status_code != 200:
        raise GrafanaError(
            f"Grafana health HTTP {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def grafana_list_datasources() -> list[dict[str, Any]]:
    if not grafana_configured():
        raise GrafanaError("Grafana no configurada (GRAFANA_BASE_URL / GRAFANA_API_TOKEN)")
    url = f"{settings.grafana_base_url.rstrip('/')}/api/datasources"
    with httpx.Client(timeout=settings.grafana_timeout_seconds) as client:
        response = client.get(url, headers=_headers())
    if response.status_code != 200:
        raise GrafanaError(
            f"Grafana datasources HTTP {response.status_code}: {response.text[:200]}",
            status_code=response.status_code,
        )
    payload = response.json()
    if not isinstance(payload, list):
        raise GrafanaError("Respuesta de datasources inválida")
    return payload


def grafana_query_sql(
    sql: str,
    *,
    datasource_uid: str | None = None,
    datasource_type: str = "grafana-postgresql-datasource",
    lookback: str = "now-180d",
) -> list[dict[str, Any]]:
    """Ejecuta SQL vía Grafana /api/ds/query y devuelve filas como dicts."""
    if not grafana_configured():
        raise GrafanaError("Grafana no configurada (GRAFANA_BASE_URL / GRAFANA_API_TOKEN)")
    uid = (datasource_uid or settings.grafana_datasource_uid or "TeslaMate").strip()
    url = f"{settings.grafana_base_url.rstrip('/')}/api/ds/query"
    payload = {
        "queries": [
            {
                "refId": "A",
                "datasource": {"type": datasource_type, "uid": uid},
                "rawSql": sql,
                "format": "table",
            }
        ],
        "from": lookback,
        "to": "now",
    }
    with httpx.Client(timeout=settings.grafana_timeout_seconds) as client:
        response = client.post(url, headers=_headers(), json=payload)
    if response.status_code != 200:
        raise GrafanaError(
            f"Grafana query HTTP {response.status_code}: {response.text[:300]}",
            status_code=response.status_code,
        )
    data = response.json()
    result = (data.get("results") or {}).get("A") or {}
    if result.get("status") not in (None, 200):
        raise GrafanaError(f"Grafana query status {result.get('status')}: {result}")
    frames = result.get("frames") or []
    if not frames:
        return []
    return _rows_from_frame(frames[0])


def _rows_from_frame(frame: dict[str, Any]) -> list[dict[str, Any]]:
    schema = frame.get("schema") or {}
    fields = schema.get("fields") or []
    values = (frame.get("data") or {}).get("values") or []
    if not fields or not values:
        return []
    names = [str(field.get("name") or f"col{index}") for index, field in enumerate(fields)]
    row_count = max((len(column) for column in values), default=0)
    rows: list[dict[str, Any]] = []
    for row_index in range(row_count):
        row: dict[str, Any] = {}
        for col_index, name in enumerate(names):
            column = values[col_index] if col_index < len(values) else []
            row[name] = column[row_index] if row_index < len(column) else None
        rows.append(row)
    return rows
