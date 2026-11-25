from __future__ import annotations

import logging
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

import httpx

from api.config import settings
from db.spatial import haversine_m

logger = logging.getLogger(__name__)

# FieldMask mínimo que aprovecha el SKU Enterprise + Atmosphere (evChargeOptions + rating)
# sin pedir fotos ni reseñas completas en bruto.
_PLACES_EV_FIELD_MASK = (
    "places.id,"
    "places.displayName,"
    "places.location,"
    "places.businessStatus,"
    "places.googleMapsUri,"
    "places.rating,"
    "places.userRatingCount,"
    "places.evChargeOptions"
)


class GooglePlacesEvError(Exception):
    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class GooglePlacesEvSnapshot:
    place_id: str | None
    display_name: str | None
    distance_m: float
    business_status: str | None
    google_maps_uri: str | None
    rating: float | None
    user_rating_count: int | None
    total_connectors: int | None
    available_count: int | None
    out_of_service_count: int | None
    max_charge_rate_kw: float | None
    availability_last_update: str | None


@dataclass(frozen=True)
class _CachedSnapshot:
    expires_at: float
    snapshot: GooglePlacesEvSnapshot | None


class _PlacesEvCache:
    """Caché efímera en memoria (nunca persistida en disco/BD) para ahorrar cuota."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._items: OrderedDict[tuple[float, float, int], _CachedSnapshot] = OrderedDict()

    def get(self, key: tuple[float, float, int]) -> tuple[bool, GooglePlacesEvSnapshot | None]:
        now = time.monotonic()
        with self._lock:
            entry = self._items.get(key)
            if entry is None:
                return False, None
            if entry.expires_at <= now:
                self._items.pop(key, None)
                return False, None
            self._items.move_to_end(key)
            return True, entry.snapshot

    def set(
        self,
        key: tuple[float, float, int],
        snapshot: GooglePlacesEvSnapshot | None,
        *,
        ttl_seconds: float,
        max_entries: int,
    ) -> None:
        if ttl_seconds <= 0 or max_entries <= 0:
            return
        with self._lock:
            self._items[key] = _CachedSnapshot(
                expires_at=time.monotonic() + ttl_seconds,
                snapshot=snapshot,
            )
            self._items.move_to_end(key)
            while len(self._items) > max_entries:
                self._items.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()


_places_cache = _PlacesEvCache()


def clear_google_places_ev_cache() -> None:
    """Vacía la caché en memoria (útil para tests)."""
    _places_cache.clear()


def _parse_ev_charge_options(
    raw_ev: dict[str, Any] | None,
) -> tuple[int | None, int | None, int | None, float | None, str | None]:
    if not isinstance(raw_ev, dict):
        return None, None, None, None, None

    total_connectors = (
        int(raw_ev["connectorCount"])
        if raw_ev.get("connectorCount") is not None
        else None
    )
    aggregations = raw_ev.get("connectorAggregations") or []
    if not isinstance(aggregations, list) or not aggregations:
        return total_connectors, None, None, None, None

    agg_total = 0
    available_sum = 0
    has_available = False
    out_of_service_sum = 0
    has_out_of_service = False
    max_kw: float | None = None
    latest_update: str | None = None

    for agg in aggregations:
        if not isinstance(agg, dict):
            continue
        if agg.get("count") is not None:
            agg_total += int(agg["count"])
        if agg.get("availableCount") is not None:
            available_sum += int(agg["availableCount"])
            has_available = True
        if agg.get("outOfServiceCount") is not None:
            out_of_service_sum += int(agg["outOfServiceCount"])
            has_out_of_service = True
        rate = agg.get("maxChargeRateKw")
        if rate is not None:
            rate_f = float(rate)
            if max_kw is None or rate_f > max_kw:
                max_kw = rate_f
        updated = agg.get("availabilityLastUpdateTime")
        if isinstance(updated, str) and updated.strip():
            if latest_update is None or updated > latest_update:
                latest_update = updated

    resolved_total = total_connectors if total_connectors is not None else (agg_total or None)
    return (
        resolved_total,
        available_sum if has_available else None,
        out_of_service_sum if has_out_of_service else None,
        max_kw,
        latest_update,
    )


def _select_closest_ev_place(
    places: list[dict[str, Any]],
    *,
    lat: float,
    lon: float,
    max_distance_m: float,
) -> GooglePlacesEvSnapshot | None:
    best: GooglePlacesEvSnapshot | None = None
    for place in places:
        if not isinstance(place, dict):
            continue
        loc = place.get("location") or {}
        p_lat = loc.get("latitude")
        p_lon = loc.get("longitude")
        if p_lat is None or p_lon is None:
            continue
        dist_m = haversine_m(lat, lon, float(p_lat), float(p_lon))
        if dist_m > max_distance_m:
            continue

        display_obj = place.get("displayName")
        display_name = (
            str(display_obj.get("text"))
            if isinstance(display_obj, dict) and display_obj.get("text")
            else None
        )
        total_conn, avail, out_svc, max_kw, last_upd = _parse_ev_charge_options(
            place.get("evChargeOptions")
        )
        snapshot = GooglePlacesEvSnapshot(
            place_id=str(place["id"]) if place.get("id") else None,
            display_name=display_name,
            distance_m=round(dist_m, 1),
            business_status=(
                str(place["businessStatus"]) if place.get("businessStatus") else None
            ),
            google_maps_uri=(
                str(place["googleMapsUri"]) if place.get("googleMapsUri") else None
            ),
            rating=float(place["rating"]) if place.get("rating") is not None else None,
            user_rating_count=(
                int(place["userRatingCount"])
                if place.get("userRatingCount") is not None
                else None
            ),
            total_connectors=total_conn,
            available_count=avail,
            out_of_service_count=out_svc,
            max_charge_rate_kw=max_kw,
            availability_last_update=last_upd,
        )
        if best is None or snapshot.distance_m < best.distance_m:
            best = snapshot
    return best


def fetch_google_places_ev_status(
    lat: float,
    lon: float,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    radius_m: float | None = None,
    timeout_s: float | None = None,
) -> GooglePlacesEvSnapshot | None:
    """Consulta en vivo Google Places API (New) para una estación concreta por coordenadas."""
    resolved_key = (api_key if api_key is not None else settings.google_maps_api_key).strip()
    if not resolved_key:
        return None

    resolved_radius = float(
        radius_m if radius_m is not None else settings.google_places_ev_search_radius_m
    )
    resolved_url = (base_url or settings.google_places_ev_base_url).strip()
    resolved_timeout = float(timeout_s or settings.google_places_ev_timeout_seconds)

    cache_key = (round(lat, 5), round(lon, 5), int(round(resolved_radius)))
    hit, cached = _places_cache.get(cache_key)
    if hit:
        return cached

    body: dict[str, Any] = {
        "includedTypes": ["electric_vehicle_charging_station"],
        "maxResultCount": 3,
        "rankPreference": "DISTANCE",
        "languageCode": "es",
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": resolved_radius,
            }
        },
    }
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": resolved_key,
        "X-Goog-FieldMask": _PLACES_EV_FIELD_MASK,
    }

    try:
        response = httpx.post(resolved_url, json=body, headers=headers, timeout=resolved_timeout)
    except httpx.TimeoutException as exc:
        raise GooglePlacesEvError(f"Google Places timeout ({resolved_timeout}s)") from exc
    except httpx.HTTPError as exc:
        raise GooglePlacesEvError(f"Error conectando a Google Places: {exc}") from exc

    if response.status_code != 200:
        detail = response.text[:200]
        try:
            payload = response.json()
            err = payload.get("error")
            if isinstance(err, dict) and err.get("message"):
                detail = str(err["message"])
        except Exception:
            pass
        raise GooglePlacesEvError(
            f"Google Places devolvió HTTP {response.status_code}: {detail}",
            status_code=response.status_code,
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise GooglePlacesEvError("Respuesta no JSON de Google Places") from exc

    raw_places = data.get("places") or []
    snapshot = _select_closest_ev_place(
        raw_places,
        lat=lat,
        lon=lon,
        max_distance_m=resolved_radius + 30.0,
    )

    _places_cache.set(
        cache_key,
        snapshot,
        ttl_seconds=settings.google_places_ev_cache_ttl_seconds,
        max_entries=settings.google_places_ev_cache_max_entries,
    )
    return snapshot
