from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import httpx

from ingest.config import settings

OCM_BASE_URL = "https://api.openchargemap.io/v3"


class OcmClientError(Exception):
    pass


class OcmClient:
    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout_seconds: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.ocm_api_key
        if not self.api_key:
            msg = "OCM_API_KEY no configurada"
            raise OcmClientError(msg)
        self.base_url = (base_url or settings.ocm_base_url).rstrip("/")
        self.timeout = timeout_seconds or settings.ocm_timeout_seconds
        self.user_agent = user_agent or settings.ocm_user_agent
        self.headers = {
            "User-Agent": self.user_agent,
            "X-API-Key": self.api_key,
        }

    def _request(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        query = dict(params or {})
        query.setdefault("key", self.api_key)
        query.setdefault("client", "Electrolineras")
        with httpx.Client(timeout=self.timeout, headers=self.headers) as client:
            response = client.get(f"{self.base_url}/{path.lstrip('/')}", params=query)
        if response.status_code >= 400:
            msg = f"OCM HTTP {response.status_code}: {response.text[:200]}"
            raise OcmClientError(msg)
        return response.json()

    def fetch_reference_data(self) -> dict[str, Any]:
        payload = self._request("referencedata")
        if not isinstance(payload, dict):
            raise OcmClientError("Respuesta referencedata inesperada")
        return payload

    def fetch_pois_batch(
        self,
        *,
        country_code: str,
        greater_than_id: int = 0,
        max_results: int | None = None,
        include_comments: bool = True,
    ) -> list[dict[str, Any]]:
        page_size = max_results or settings.ocm_sync_page_size
        params: dict[str, Any] = {
            "output": "json",
            "countrycode": country_code.upper(),
            "maxresults": page_size,
            "greaterthanid": greater_than_id,
            "compact": "true",
            "verbose": "false",
        }
        if include_comments:
            params["includecomments"] = "true"
        payload = self._request("poi/", params=params)
        if not isinstance(payload, list):
            raise OcmClientError("Respuesta poi/ inesperada")
        return payload

    def iter_pois(
        self,
        *,
        country_code: str,
        include_comments: bool = True,
        max_batches: int | None = None,
    ) -> Iterator[list[dict[str, Any]]]:
        page_size = settings.ocm_sync_page_size
        greater_than_id = 0
        batches = 0
        while True:
            pois = self.fetch_pois_batch(
                country_code=country_code,
                greater_than_id=greater_than_id,
                max_results=page_size,
                include_comments=include_comments,
            )
            if not pois:
                break
            yield pois
            batches += 1
            if max_batches is not None and batches >= max_batches:
                break
            greater_than_id = max(int(poi["ID"]) for poi in pois if poi.get("ID") is not None)
            if len(pois) < page_size:
                break
