from __future__ import annotations

import threading
import time
from typing import TypeVar

from api.config import settings

T = TypeVar("T")


class TeslaMateQueryCache:
    """Cache en memoria para consultas Grafana/TeslaMate (TTL configurable)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._entries: dict[str, tuple[float, object]] = {}

    def reset(self) -> None:
        with self._lock:
            self._entries.clear()

    def get(self, key: str) -> T | None:
        if not settings.teslamate_query_cache_enabled:
            return None
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if now >= expires_at:
                del self._entries[key]
                return None
            return value  # type: ignore[return-value]

    def set(self, key: str, value: object) -> None:
        if not settings.teslamate_query_cache_enabled:
            return
        ttl = max(1.0, settings.teslamate_query_cache_ttl_seconds)
        expires_at = time.monotonic() + ttl
        max_entries = max(1, settings.teslamate_query_cache_max_entries)
        with self._lock:
            if key not in self._entries and len(self._entries) >= max_entries:
                oldest_key = min(self._entries, key=lambda item: self._entries[item][0])
                del self._entries[oldest_key]
            self._entries[key] = (expires_at, value)


teslamate_query_cache = TeslaMateQueryCache()
