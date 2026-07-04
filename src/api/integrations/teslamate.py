from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from api.config import settings


class TeslaMateError(Exception):
    pass


def build_car_model_label(model: str | None, trim_badging: str | None) -> str | None:
    model = (model or "").strip()
    trim = (trim_badging or "").strip()
    if model and trim:
        return f"Model {model} {trim}"
    if trim:
        return trim
    if model:
        return f"Model {model}"
    return None


@dataclass(frozen=True)
class VehicleTelemetry:
    car_id: int
    display_name: str | None
    state: str | None
    lat: float
    lon: float
    battery_level_pct: float
    usable_battery_level_pct: float | None
    est_battery_range_km: float | None
    rated_battery_range_km: float | None = None
    ideal_battery_range_km: float | None = None
    model: str | None = None
    trim_badging: str | None = None
    car_model_label: str | None = None
    version: str | None = None
    charging_state: str | None = None
    inside_temp_c: float | None = None
    outside_temp_c: float | None = None
    odometer_km: float | None = None
    source: str = "teslamateapi"


def _as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pick_location(payload: dict[str, Any]) -> tuple[float | None, float | None]:
    for key in ("latitude", "lat"):
        lat = _as_float(payload.get(key))
        if lat is not None:
            lon = _as_float(payload.get("longitude") if key == "latitude" else payload.get("lon"))
            if lon is not None:
                return lat, lon
    location = payload.get("location")
    if isinstance(location, dict):
        lat = _as_float(location.get("latitude") or location.get("lat"))
        lon = _as_float(location.get("longitude") or location.get("lon"))
        if lat is not None and lon is not None:
            return lat, lon
    drive_details = payload.get("drive_details")
    if isinstance(drive_details, dict):
        lat = _as_float(drive_details.get("latitude"))
        lon = _as_float(drive_details.get("longitude"))
        if lat is not None and lon is not None:
            return lat, lon
    return None, None


def _parse_status(car_id: int, payload: dict[str, Any]) -> VehicleTelemetry:
    data = payload.get("data")
    status = data if isinstance(data, dict) else payload
    nested_status = status.get("status")
    if isinstance(nested_status, dict):
        status = nested_status

    lat, lon = _pick_location(status)
    if lat is None or lon is None:
        raise TeslaMateError("TeslaMate no devolvió ubicación del vehículo")

    battery_level = _as_float(status.get("battery_level"))
    if battery_level is None:
        raise TeslaMateError("TeslaMate no devolvió battery_level")

    display_name = status.get("display_name") or status.get("car_name")
    if isinstance(display_name, str):
        display_name = display_name.strip() or None
    else:
        display_name = None

    model = status.get("model") if isinstance(status.get("model"), str) else None
    trim_badging = status.get("trim_badging") if isinstance(status.get("trim_badging"), str) else None
    version = status.get("version") if isinstance(status.get("version"), str) else None
    rated = _as_float(status.get("rated_battery_range_km"))
    est = _as_float(status.get("est_battery_range_km")) or rated

    return VehicleTelemetry(
        car_id=car_id,
        display_name=display_name,
        state=status.get("state") if isinstance(status.get("state"), str) else None,
        lat=lat,
        lon=lon,
        battery_level_pct=battery_level,
        usable_battery_level_pct=_as_float(status.get("usable_battery_level")),
        est_battery_range_km=est,
        rated_battery_range_km=rated,
        ideal_battery_range_km=_as_float(status.get("ideal_battery_range_km")),
        model=model,
        trim_badging=trim_badging,
        car_model_label=build_car_model_label(model, trim_badging),
        version=version,
        charging_state=status.get("charging_state") if isinstance(status.get("charging_state"), str) else None,
        inside_temp_c=_as_float(status.get("inside_temp")),
        outside_temp_c=_as_float(status.get("outside_temp")),
        odometer_km=_as_float(status.get("odometer")),
    )


class TeslaMateClient:
    def __init__(
        self,
        *,
        base_url: str,
        api_token: str,
        timeout_seconds: float = 15.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_token = api_token.strip()
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_settings(cls) -> TeslaMateClient | None:
        base_url = settings.teslamate_api_base_url.strip()
        token = settings.teslamate_api_token.strip()
        if not base_url or not token:
            return None
        return cls(
            base_url=base_url,
            api_token=token,
            timeout_seconds=settings.teslamate_timeout_seconds,
        )

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.api_token}"}

    def _get_json(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=self._headers())
        except httpx.HTTPError as exc:
            raise TeslaMateError(f"No se pudo contactar TeslaMateApi: {exc}") from exc

        if response.status_code == 401:
            raise TeslaMateError("Token TeslaMateApi rechazado (401)")
        if response.status_code >= 400:
            raise TeslaMateError(f"TeslaMateApi error {response.status_code}: {response.text[:200]}")
        payload = response.json()
        if not isinstance(payload, dict):
            raise TeslaMateError("Respuesta TeslaMateApi inválida")
        return payload

    def list_car_ids(self) -> list[int]:
        payload = self._get_json("/api/v1/cars")
        cars = payload.get("data")
        if not isinstance(cars, list):
            cars = payload.get("cars")
        if not isinstance(cars, list):
            raise TeslaMateError("TeslaMateApi no devolvió lista de vehículos")

        ids: list[int] = []
        for item in cars:
            if not isinstance(item, dict):
                continue
            car_id = item.get("car_id") or item.get("id")
            if car_id is None:
                continue
            ids.append(int(car_id))
        return ids

    def get_vehicle_telemetry(self, car_id: int | None = None) -> VehicleTelemetry:
        resolved_id = car_id or settings.teslamate_car_id
        payload = self._get_json(f"/api/v1/cars/{resolved_id}/status")
        return _parse_status(resolved_id, payload)
