# Integraciones opcionales (Fase 3)

## TeslaMate — guía en el mini PC

Documentación operativa del servidor:

**`/mnt/datos/docker/teslamate/INTEGRACION_APPS.md`**

Resumen:

| Necesidad | Canal en Electrolineras |
|-----------|-------------------------|
| Estado actual (SOC, posición) | **MQTT** (`TESLAMATE_MQTT_*`) — recomendado |
| Histórico / REST | **TeslaMateApi** opcional (`TESLAMATE_API_*`) |

Coche *The Ship*: `TESLAMATE_CAR_ID=1`, topics `teslamate/cars/1/#`.

Código:

- `teslamate_mqtt.py` — lectura snapshot MQTT
- `teslamate.py` — cliente TeslaMateApi
- `vehicle_telemetry.py` — `auto`: MQTT → API
