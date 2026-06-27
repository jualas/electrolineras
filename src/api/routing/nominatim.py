from __future__ import annotations

import httpx

from api.config import settings


class GeocodingError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _fetch_nominatim_search(
    query: str,
    limit: int,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> list[dict]:
    trimmed = query.strip()
    if not trimmed:
        raise GeocodingError("La consulta de geocodificación está vacía")

    url = f"{(base_url or settings.nominatim_base_url).rstrip('/')}/search"
    params = {
        "q": trimmed,
        "format": "json",
        "limit": max(1, min(limit, 10)),
        "countrycodes": settings.nominatim_country_codes,
    }
    headers = {"User-Agent": settings.nominatim_user_agent}

    with httpx.Client(timeout=timeout_s or settings.nominatim_timeout_seconds) as client:
        response = client.get(url, params=params, headers=headers)

    if response.status_code != 200:
        raise GeocodingError(
            f"Nominatim respondió con HTTP {response.status_code}",
            status_code=response.status_code,
        )

    results = response.json()
    if not isinstance(results, list):
        raise GeocodingError("Respuesta de geocodificación inválida")
    return results


def geocode_address(
    query: str,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> tuple[float, float, str]:
    results = _fetch_nominatim_search(
        query,
        1,
        base_url=base_url,
        timeout_s=timeout_s,
    )
    if not results:
        raise GeocodingError(f"No se encontró ubicación para: {query.strip()}")

    hit = results[0]
    try:
        lat = float(hit["lat"])
        lon = float(hit["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("Respuesta de geocodificación inválida") from exc

    label = hit.get("display_name", query.strip())
    return lat, lon, label


def search_places(
    query: str,
    *,
    limit: int = 5,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> list[tuple[float, float, str]]:
    results = _fetch_nominatim_search(
        query,
        limit,
        base_url=base_url,
        timeout_s=timeout_s,
    )
    if not results:
        raise GeocodingError(f"No se encontró ubicación para: {query.strip()}")

    hits: list[tuple[float, float, str]] = []
    for hit in results:
        try:
            lat = float(hit["lat"])
            lon = float(hit["lon"])
        except (KeyError, TypeError, ValueError):
            continue
        label = hit.get("display_name", query.strip())
        hits.append((lat, lon, label))
    if not hits:
        raise GeocodingError("Respuesta de geocodificación inválida")
    return hits
