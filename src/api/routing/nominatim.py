from __future__ import annotations

import httpx

from api.config import settings


class GeocodingError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def geocode_address(
    query: str,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> tuple[float, float, str]:
    trimmed = query.strip()
    if not trimmed:
        raise GeocodingError("La consulta de geocodificación está vacía")

    url = f"{(base_url or settings.nominatim_base_url).rstrip('/')}/search"
    params = {
        "q": trimmed,
        "format": "json",
        "limit": 1,
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
    if not results:
        raise GeocodingError(f"No se encontró ubicación para: {trimmed}")

    hit = results[0]
    try:
        lat = float(hit["lat"])
        lon = float(hit["lon"])
    except (KeyError, TypeError, ValueError) as exc:
        raise GeocodingError("Respuesta de geocodificación inválida") from exc

    label = hit.get("display_name", trimmed)
    return lat, lon, label
