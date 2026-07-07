from __future__ import annotations

import logging
import time
from typing import Any

import httpx

from ingest.config import settings

logger = logging.getLogger(__name__)

DEFAULT_FILTER_BODY: dict[str, Any] = {
    "filterNumber": 0,
    "selectedCpos": [],
    "cpo_ids": [],
    "only_ocpi": False,
    "available": False,
    "power_min": 0,
    "power_max": None,
    "connector_types": [],
    "energy_price_min": 0,
    "energy_price_max": None,
    "payment_methods": [],
    "facilities": [],
}

SPAIN_BBOX = {
    "latitude_ne": 44.0,
    "longitude_ne": 5.0,
    "latitude_sw": 35.0,
    "longitude_sw": -10.0,
}


class ReveClientError(Exception):
    pass


class ReveClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else settings.reve_api_key).strip()
        self.base_url = (base_url or settings.resolved_reve_base_url()).rstrip("/")
        self.timeout = timeout_seconds or settings.reve_timeout_seconds
        self.headers = {"User-Agent": user_agent or settings.reve_user_agent}
        if self.api_key:
            self.headers["x-api-key"] = self.api_key

    @property
    def uses_authenticated_api(self) -> bool:
        return bool(self.api_key)

    def test_connection(self) -> dict[str, Any]:
        """Comprueba credenciales y conectividad."""
        if self.uses_authenticated_api:
            try:
                cpos = self.fetch_cpos()
            except ReveClientError as exc:
                if "429" in str(exc):
                    return {
                        "ok": True,
                        "base_url": self.base_url,
                        "authenticated": True,
                        "rate_limited": True,
                        "message": "Clave reconocida; REVE pide esperar antes de más peticiones",
                    }
                raise
            try:
                locations, _ = self.fetch_locations_page(page=1, per_page=1)
            except ReveClientError as exc:
                if "429" in str(exc):
                    return {
                        "ok": True,
                        "base_url": self.base_url,
                        "authenticated": True,
                        "cpos_count": len(cpos),
                        "sample_locations": None,
                        "rate_limited": True,
                    }
                raise
            return {
                "ok": True,
                "base_url": self.base_url,
                "authenticated": True,
                "cpos_count": len(cpos),
                "sample_locations": len(locations),
            }

        stats = self.fetch_stats()
        return {
            "ok": True,
            "base_url": self.base_url,
            "authenticated": False,
            "stats_entries": len(stats),
        }

    def _url(self, path: str) -> str:
        return f"{self.base_url}/{path.lstrip('/')}"

    def _request(self, method: str, path: str, **kwargs: Any) -> Any:
        max_attempts = 6
        for attempt in range(max_attempts):
            with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
                response = client.request(method, self._url(path), **kwargs)
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                try:
                    wait_seconds = float(retry_after) if retry_after else 0.0
                except ValueError:
                    wait_seconds = 0.0
                wait_seconds = max(wait_seconds, 5.0 * (attempt + 1))
                wait_seconds = min(wait_seconds, 120.0)
                logger.warning(
                    "REVE 429 en %s %s; reintento %d/%d en %.0fs",
                    method,
                    path,
                    attempt + 1,
                    max_attempts,
                    wait_seconds,
                )
                time.sleep(wait_seconds)
                continue
            if response.status_code >= 400:
                msg = f"REVE HTTP {response.status_code}: {response.text[:200]}"
                raise ReveClientError(msg)
            if not response.content.strip():
                raise ReveClientError(f"REVE HTTP {response.status_code}: respuesta vacía")
            payload = response.json()
            if isinstance(payload, dict) and payload.get("status_code", 200) >= 400:
                raise ReveClientError(str(payload.get("status_message", payload)))
            return payload
        raise ReveClientError("REVE HTTP 429: límite de peticiones tras varios reintentos")

    def fetch_cpos(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/cpos")
        if not isinstance(payload, list):
            raise ReveClientError("Respuesta /cpos inesperada")
        return payload

    def fetch_stats(self) -> list[dict[str, Any]]:
        payload = self._request("GET", "/stats")
        if not isinstance(payload, list):
            raise ReveClientError("Respuesta /stats inesperada")
        return payload

    def fetch_markers(
        self,
        *,
        latitude_ne: float,
        longitude_ne: float,
        latitude_sw: float,
        longitude_sw: float,
        zoom: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        body = {
            **DEFAULT_FILTER_BODY,
            **(filters or {}),
            "latitude_ne": latitude_ne,
            "longitude_ne": longitude_ne,
            "latitude_sw": latitude_sw,
            "longitude_sw": longitude_sw,
            "zoom": zoom,
        }
        payload = self._request("POST", "/markers", json=body)
        if not isinstance(payload, list):
            raise ReveClientError("Respuesta /markers inesperada")
        return payload

    def fetch_locations_page(
        self,
        *,
        page: int,
        per_page: int,
        latitude_ne: float = SPAIN_BBOX["latitude_ne"],
        longitude_ne: float = SPAIN_BBOX["longitude_ne"],
        latitude_sw: float = SPAIN_BBOX["latitude_sw"],
        longitude_sw: float = SPAIN_BBOX["longitude_sw"],
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        if self.uses_authenticated_api:
            limit = min(per_page, settings.reve_external_page_limit)
            payload = self._request(
                "GET",
                f"/locations?page={page}&limit={limit}",
            )
            if not isinstance(payload, list):
                raise ReveClientError("Respuesta GET /locations inesperada")
            next_page = page + 1 if len(payload) >= limit else None
            return payload, {"next": next_page}

        body = {
            **DEFAULT_FILTER_BODY,
            **(filters or {}),
            "latitude_ne": latitude_ne,
            "longitude_ne": longitude_ne,
            "latitude_sw": latitude_sw,
            "longitude_sw": longitude_sw,
        }
        payload = self._request(
            "POST",
            f"/locations?page={page}&per_page={per_page}",
            json=body,
        )
        if not isinstance(payload, dict):
            raise ReveClientError("Respuesta /locations inesperada")
        data = payload.get("data")
        pagination = payload.get("pagination")
        if not isinstance(data, list) or not isinstance(pagination, dict):
            raise ReveClientError("Respuesta /locations sin data/pagination")
        return data, pagination

    def fetch_location(self, location_id: str) -> dict[str, Any]:
        payload = self._request("GET", f"/locations/{location_id}")
        if not isinstance(payload, dict) or "id" not in payload:
            raise ReveClientError(f"Detalle REVE inválido: {location_id}")
        return payload

    def iter_locations(
        self,
        *,
        per_page: int | None = None,
        max_pages: int | None = None,
    ):
        page_size = per_page or (
            settings.reve_external_page_limit
            if self.uses_authenticated_api
            else settings.reve_sync_per_page
        )
        page = 1
        pages_fetched = 0
        while True:
            data, pagination = self.fetch_locations_page(page=page, per_page=page_size)
            yield from data
            pages_fetched += 1
            next_page = pagination.get("next")
            if next_page is None:
                break
            if max_pages is not None and pages_fetched >= max_pages:
                break
            page = int(next_page)
