from __future__ import annotations

import re

import httpx

from api.config import settings
from api.routing.nominatim_cache import cache_key, geocode_cache


PUBLIC_NOMINATIM_BASE_URL = "https://nominatim.openstreetmap.org"

# Nominatim a veces no encuentra nada con «X en el Y» (p. ej. «fuente caputa en el
# rio Mula») pero sí con «X Y» — reintenta sin la preposición locativa antes de rendirse.
_LOCATIVE_CONNECTOR_RE = re.compile(r"\s+en\s+(?:el|la|los|las)\s+", re.IGNORECASE)


def _simplify_query(query: str) -> str | None:
    simplified = _LOCATIVE_CONNECTOR_RE.sub(" ", query)
    simplified = re.sub(r"\s+", " ", simplified).strip()
    if simplified and simplified.lower() != query.strip().lower():
        return simplified
    return None


class GeocodingError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _should_try_fallback(error: GeocodingError) -> bool:
    if error.status_code is None:
        return True
    return error.status_code in {403, 404, 408, 429, 500, 502, 503, 504}


def _resolve_base_urls(base_url: str | None) -> list[str]:
    primary = (base_url or settings.nominatim_base_url).rstrip("/")
    urls = [primary]
    fallback = settings.nominatim_fallback_base_url.strip().rstrip("/")
    if fallback and fallback not in urls:
        urls.append(fallback)
    if (
        settings.nominatim_public_emergency_fallback
        and PUBLIC_NOMINATIM_BASE_URL not in urls
    ):
        urls.append(PUBLIC_NOMINATIM_BASE_URL)
    return urls


def _fetch_from_base(
    query: str,
    limit: int,
    *,
    base_url: str,
    timeout_s: float,
) -> list[dict]:
    trimmed = query.strip()
    if not trimmed:
        raise GeocodingError("La consulta de geocodificación está vacía")

    url = f"{base_url.rstrip('/')}/search"
    params = {
        "q": trimmed,
        "format": "json",
        "limit": max(1, min(limit, 10)),
        "countrycodes": settings.nominatim_country_codes,
    }
    headers = {"User-Agent": settings.nominatim_user_agent}

    try:
        with httpx.Client(timeout=timeout_s) as client:
            response = client.get(url, params=params, headers=headers)
    except httpx.TimeoutException as exc:
        raise GeocodingError("Nominatim no respondió a tiempo") from exc
    except httpx.HTTPError as exc:
        raise GeocodingError(f"Error de red con Nominatim: {exc}") from exc

    if response.status_code != 200:
        raise GeocodingError(
            f"Nominatim respondió con HTTP {response.status_code}",
            status_code=response.status_code,
        )

    content_type = response.headers.get("content-type", "")
    if "json" not in content_type.lower():
        raise GeocodingError(
            f"Nominatim devolvió tipo inesperado: {content_type or 'desconocido'}",
            status_code=502,
        )

    try:
        results = response.json()
    except ValueError as exc:
        raise GeocodingError("Respuesta de geocodificación inválida", status_code=502) from exc

    if not isinstance(results, list):
        raise GeocodingError("Respuesta de geocodificación inválida")
    return results


def _fetch_nominatim_search(
    query: str,
    limit: int,
    *,
    base_url: str | None = None,
    timeout_s: float | None = None,
) -> list[dict]:
    timeout = timeout_s or settings.nominatim_timeout_seconds
    bases = _resolve_base_urls(base_url)
    key = cache_key(query, limit, settings.nominatim_country_codes, bases[0])
    cached = geocode_cache.get(key)
    if cached is not None:
        return cached

    last_error: GeocodingError | None = None
    for index, candidate in enumerate(bases):
        try:
            results = _fetch_from_base(query, limit, base_url=candidate, timeout_s=timeout)
            geocode_cache.set(key, results)
            return results
        except GeocodingError as exc:
            last_error = exc
            if index < len(bases) - 1 and _should_try_fallback(exc):
                continue
            raise

    assert last_error is not None
    raise last_error


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
        simplified = _simplify_query(query)
        if simplified:
            results = _fetch_nominatim_search(
                simplified,
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
        simplified = _simplify_query(query)
        if simplified:
            results = _fetch_nominatim_search(
                simplified,
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
