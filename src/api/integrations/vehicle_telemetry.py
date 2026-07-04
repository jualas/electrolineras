from __future__ import annotations

from api.config import settings
from api.integrations.teslamate import TeslaMateClient, TeslaMateError, VehicleTelemetry
from api.integrations.teslamate_mqtt import fetch_vehicle_telemetry_mqtt, mqtt_configured


def teslamate_api_configured() -> bool:
    return TeslaMateClient.from_settings() is not None


def vehicle_telemetry_configured() -> bool:
    return mqtt_configured() or teslamate_api_configured()


def fetch_vehicle_telemetry(car_id: int | None = None) -> VehicleTelemetry:
    """Estado del vehículo: MQTT (recomendado) → TeslaMateApi (opcional)."""
    mode = settings.teslamate_data_source.strip().lower() or "auto"

    if mode in {"mqtt", "auto"} and mqtt_configured():
        try:
            return fetch_vehicle_telemetry_mqtt(car_id=car_id)
        except TeslaMateError:
            if mode == "mqtt":
                raise

    if mode in {"api", "auto"}:
        client = TeslaMateClient.from_settings()
        if client is None:
            raise TeslaMateError(
                "Telemetría no configurada. Usa MQTT (ver INTEGRACION_APPS.md) "
                "o TESLAMATE_API_BASE_URL + TESLAMATE_API_TOKEN"
            )
        return client.get_vehicle_telemetry(car_id=car_id)

    raise TeslaMateError(
        "TESLAMATE_DATA_SOURCE inválido; use auto, mqtt o api"
    )
