from __future__ import annotations

import threading
import time

from api.config import settings


class GeocodeCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, list[dict]]] = {}

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    def get(self, key: str) -> list[dict] | None:
        if not settings.nominatim_cache_enabled:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, results = entry
            if now >= expires_at:
                del self._entries[key]
                return None
            return results

    def set(self, key: str, results: list[dict]) -> None:
        if not settings.nominatim_cache_enabled:
            return
        ttl = max(1.0, settings.nominatim_cache_ttl_seconds)
        expires_at = time.monotonic() + ttl
        max_entries = max(1, settings.nominatim_cache_max_entries)
        with self._lock:
            if key not in self._entries and len(self._entries) >= max_entries:
                oldest_key = min(self._entries, key=lambda item: self._entries[item][0])
                del self._entries[oldest_key]
            self._entries[key] = (expires_at, results)


geocode_cache = GeocodeCache()


def cache_key(query: str, limit: int, country_codes: str, base_url: str) -> str:
    return f"{base_url.rstrip('/')}|{country_codes}|{limit}|{query.strip().lower()}"
