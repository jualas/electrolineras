from __future__ import annotations

import json
import time
from typing import Any

import paho.mqtt.client as mqtt

from api.config import settings
from api.integrations.teslamate import TeslaMateError, VehicleTelemetry, build_car_model_label


def mqtt_configured() -> bool:
    return bool(settings.teslamate_mqtt_host.strip() and settings.teslamate_mqtt_username.strip())


def _topic_prefix(car_id: int) -> str:
    base = settings.teslamate_mqtt_topic_prefix.strip().rstrip("/")
    return f"{base}/{car_id}/"


def _suffix(topic: str, prefix: str) -> str:
    if topic.startswith(prefix):
        return topic[len(prefix):]
    return topic


def _parse_location(values: dict[str, str], prefix: str) -> tuple[float | None, float | None]:
    location_raw = values.get(f"{prefix}location")
    if location_raw:
        try:
            payload = json.loads(location_raw)
            if isinstance(payload, dict):
                lat = payload.get("latitude") or payload.get("lat")
                lon = payload.get("longitude") or payload.get("lon")
                if lat is not None and lon is not None:
                    return float(lat), float(lon)
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    lat_raw = values.get(f"{prefix}latitude")
    lon_raw = values.get(f"{prefix}longitude")
    if lat_raw is not None and lon_raw is not None:
        try:
            return float(lat_raw), float(lon_raw)
        except ValueError:
            return None, None
    return None, None


def _build_telemetry(car_id: int, values: dict[str, str]) -> VehicleTelemetry:
    prefix = _topic_prefix(car_id)
    lat, lon = _parse_location(values, prefix)
    if lat is None or lon is None:
        raise TeslaMateError("MQTT: sin ubicación (topics location o latitude/longitude)")

    battery_raw = values.get(f"{prefix}battery_level")
    if battery_raw is None:
        raise TeslaMateError("MQTT: sin battery_level")
    try:
        battery_level = float(battery_raw)
    except ValueError as exc:
        raise TeslaMateError("MQTT: battery_level inválido") from exc

    usable_raw = values.get(f"{prefix}usable_battery_level")
    range_raw = values.get(f"{prefix}est_battery_range_km")
    rated_raw = values.get(f"{prefix}rated_battery_range_km")
    ideal_raw = values.get(f"{prefix}ideal_battery_range_km")
    model = values.get(f"{prefix}model")
    trim_badging = values.get(f"{prefix}trim_badging")
    version = values.get(f"{prefix}version")
    inside_raw = values.get(f"{prefix}inside_temp")
    outside_raw = values.get(f"{prefix}outside_temp")
    odometer_raw = values.get(f"{prefix}odometer")
    display_name = settings.teslamate_car_display_name.strip() or None

    est_km = float(range_raw) if range_raw is not None else None
    rated_km = float(rated_raw) if rated_raw is not None else None
    if est_km is None and rated_km is not None:
        est_km = rated_km

    model_str = model if isinstance(model, str) else None
    trim_str = trim_badging if isinstance(trim_badging, str) else None

    return VehicleTelemetry(
        car_id=car_id,
        display_name=display_name,
        state=values.get(f"{prefix}state"),
        lat=lat,
        lon=lon,
        battery_level_pct=battery_level,
        usable_battery_level_pct=float(usable_raw) if usable_raw is not None else None,
        est_battery_range_km=est_km,
        rated_battery_range_km=rated_km,
        ideal_battery_range_km=float(ideal_raw) if ideal_raw is not None else None,
        model=model_str,
        trim_badging=trim_str,
        car_model_label=build_car_model_label(model_str, trim_str),
        version=version if isinstance(version, str) else None,
        charging_state=values.get(f"{prefix}charging_state"),
        inside_temp_c=float(inside_raw) if inside_raw is not None else None,
        outside_temp_c=float(outside_raw) if outside_raw is not None else None,
        odometer_km=float(odometer_raw) if odometer_raw is not None else None,
        source="teslamate-mqtt",
    )


def fetch_vehicle_telemetry_mqtt(car_id: int | None = None) -> VehicleTelemetry:
    if not mqtt_configured():
        raise TeslaMateError("MQTT TeslaMate no configurado (TESLAMATE_MQTT_HOST + USERNAME)")

    resolved_id = car_id or settings.teslamate_car_id
    prefix = _topic_prefix(resolved_id)
    collected: dict[str, str] = {}
    connected = False

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1)

    def on_connect_v1(client: mqtt.Client, userdata: Any, flags: Any, rc: int) -> None:
        nonlocal connected
        if rc == 0:
            connected = True
            client.subscribe(f"{prefix}#")

    def on_message(client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            collected[msg.topic] = msg.payload.decode("utf-8")
        except UnicodeDecodeError:
            collected[msg.topic] = msg.payload.decode("utf-8", errors="replace")

    client.username_pw_set(
        settings.teslamate_mqtt_username.strip(),
        settings.teslamate_mqtt_password,
    )
    client.on_connect = on_connect_v1
    client.on_message = on_message

    try:
        client.connect(
            settings.teslamate_mqtt_host.strip(),
            settings.teslamate_mqtt_port,
            keepalive=30,
        )
        client.loop_start()
        deadline = time.monotonic() + settings.teslamate_mqtt_timeout_seconds
        while time.monotonic() < deadline:
            if connected and f"{prefix}battery_level" in collected:
                lat, lon = _parse_location(collected, prefix)
                if lat is not None and lon is not None:
                    est = collected.get(f"{prefix}est_battery_range_km") or collected.get(
                        f"{prefix}rated_battery_range_km"
                    )
                    if est is not None:
                        break
            time.sleep(0.05)
    except OSError as exc:
        raise TeslaMateError(f"No se pudo conectar al broker MQTT: {exc}") from exc
    finally:
        client.loop_stop()
        client.disconnect()

    if not collected:
        raise TeslaMateError(
            f"MQTT: sin mensajes en {prefix}# (¿TeslaMate publicando en {settings.teslamate_mqtt_host}?)"
        )

    return _build_telemetry(resolved_id, collected)
