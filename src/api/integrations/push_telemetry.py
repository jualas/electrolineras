from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from api.config import settings
from api.integrations.teslamate import VehicleTelemetry


@dataclass(frozen=True)
class _StoredTelemetry:
    expires_at: float
    telemetry: VehicleTelemetry


class _PushTelemetryStore:
    """Almacén en memoria con TTL para telemetría enviada desde el vehículo (Android Auto/AAOS/OBD-II)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_car_id: dict[int, _StoredTelemetry] = {}
        self._latest_car_id: int | None = None

    def store(self, telemetry: VehicleTelemetry, *, ttl_seconds: float | None = None) -> VehicleTelemetry:
        ttl = float(
            ttl_seconds
            if ttl_seconds is not None
            else settings.vehicle_telemetry_push_ttl_seconds
        )
        expires_at = time.monotonic() + max(1.0, ttl)
        with self._lock:
            self._by_car_id[telemetry.car_id] = _StoredTelemetry(
                expires_at=expires_at,
                telemetry=telemetry,
            )
            self._latest_car_id = telemetry.car_id
        return telemetry

    def get(self, *, car_id: int | None = None) -> VehicleTelemetry | None:
        now = time.monotonic()
        with self._lock:
            target_id = car_id if car_id is not None else self._latest_car_id
            if target_id is None:
                return None
            entry = self._by_car_id.get(target_id)
            if entry is None:
                return None
            if entry.expires_at <= now:
                self._by_car_id.pop(target_id, None)
                if self._latest_car_id == target_id:
                    self._latest_car_id = None
                return None
            return entry.telemetry

    def has_active(self) -> bool:
        now = time.monotonic()
        with self._lock:
            expired = [cid for cid, entry in self._by_car_id.items() if entry.expires_at <= now]
            for cid in expired:
                self._by_car_id.pop(cid, None)
                if self._latest_car_id == cid:
                    self._latest_car_id = None
            return bool(self._by_car_id)

    def clear(self) -> None:
        with self._lock:
            self._by_car_id.clear()
            self._latest_car_id = None


_store = _PushTelemetryStore()


def store_push_telemetry(
    telemetry: VehicleTelemetry,
    *,
    ttl_seconds: float | None = None,
) -> VehicleTelemetry:
    return _store.store(telemetry, ttl_seconds=ttl_seconds)


def get_push_telemetry(*, car_id: int | None = None) -> VehicleTelemetry | None:
    return _store.get(car_id=car_id)


def push_telemetry_active() -> bool:
    return _store.has_active()


def clear_push_telemetry() -> None:
    _store.clear()
