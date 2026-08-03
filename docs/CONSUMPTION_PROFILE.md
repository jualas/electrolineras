# Perfil de consumo histórico (Grafana / TeslaMate)

Tarea TaskBoard **#6090**. Lectura solo vía **Grafana HTTP API** → datasource PostgreSQL TeslaMate (`uid=TeslaMate`). InfluxDB2 existe en el host pero no es el datasource principal de los dashboards TeslaMate.

## Variables de entorno

| Variable | Ejemplo | Uso |
|----------|---------|-----|
| `GRAFANA_BASE_URL` | `http://host.docker.internal:3000` | API Grafana (desde contenedor API) |
| `GRAFANA_API_TOKEN` | service account Viewer | Bearer; no commitear |
| `GRAFANA_DATASOURCE_UID` | `TeslaMate` | Postgres TeslaMate |
| `CONSUMPTION_PROFILE_LOOKBACK_DAYS` | `0` | `0` = todo el histórico; `>0` limita a N días |
| `CONSUMPTION_PROFILE_MIN_DISTANCE_KM` | `20` | Excluye microtrayectos; TeslaMate parte al subir/bajar |

Token de servicio: crear en Grafana → Administration → Service accounts → Viewer. En prod del mini PC suele vivir en `/mnt/datos/docker/electrolineras/.env` (y copia de respaldo en `.grafana-token`).

## Por qué ≥20 km

TeslaMate crea un *drive* cada vez que te subes y te bajas: un viaje largo puede partirse en varios segmentos. Un umbral de ~20 km captura esos tramos útiles sin mezclar microtrayectos urbanos (mediana ~4–5 km). Se usa **todo el histórico** con ese filtro; dentro de cada bin los trayectos más largos siguen pesando más.

## Fórmula de eficiencia

TeslaMate guarda `cars.efficiency` (kWh por km de autonomía *rated*) y rangos rated al inicio/fin del viaje:

```
energy_kwh = (start_rated_range_km - end_rated_range_km) * efficiency
wh_per_km = energy_kwh * 1000 / distance
```

Solo se usan viajes con `distance >= CONSUMPTION_PROFILE_MIN_DISTANCE_KM` (default 20) y Wh/km entre 80–350. Dentro de cada bin, viajes más largos pesan más (`distance × (1 + distance/200)`).

## Bins

| Bin | Criterio | Uso en plan |
|-----|----------|-------------|
| `highway` | velocidad media ≥ 95 km/h | `route_preference=fastest` |
| `conventional` | velocidad media ≤ 70 km/h | `conventional` o `avoid_highways` |
| `mixed` | resto | `shortest` / fallback |
| `mountain` | ascent ≥ 400 m y no highway | futuro / fallback |

Agregación: media ponderada (más peso a trayectos más largos). Confianza (viajes largos escasos): `high` (≥8), `medium` (≥3), `low` (&lt;3).

## API

- `GET /api/v1/private/consumption-profile` — bins + metadatos (auth privada).
- Plan Asistente (`trip-advice-from-car` / `trip-guide-from-car`): si no se envía `consumption_kwh_per_100km`, elige bin según ruta y rellena:
  - `consumption_source`: `historical` \| `telemetry` \| `preset` \| `hybrid`
  - `consumption_kwh_per_100km`, `consumption_confidence`, `consumption_note`, `consumption_bin`

Fallback sin Grafana/viajes: consumo desde autonomía *rated* TeslaMate (`telemetry`) y nota «Sin histórico; usando autonomía nominal».

## UI Asistente

Con telemetría autenticada: se ocultan input de consumo y chips de terreno. Se muestra la nota transparente del plan.

## MCP Grafana (Cursor CLI)

Servidor local: [`tools/mcp_grafana/server.py`](../tools/mcp_grafana/server.py).

Herramientas: `grafana_health`, `grafana_list_datasources`, `grafana_query`, `grafana_consumption_summary`.

Registro en `~/.cursor/mcp.json` (o config MCP del CLI) en el mini PC:

```json
{
  "mcpServers": {
    "electrolineras-grafana": {
      "command": "/mnt/datos/Proyectos/Electrolineras/tools/mcp_grafana/run-mcp-grafana.sh",
      "env": {
        "GRAFANA_BASE_URL": "http://127.0.0.1:3000",
        "GRAFANA_DATASOURCE_UID": "TeslaMate",
        "GRAFANA_TOKEN_FILE": "/mnt/datos/docker/electrolineras/.grafana-token",
        "CONSUMPTION_PROFILE_LOOKBACK_DAYS": "0",
        "CONSUMPTION_PROFILE_MIN_DISTANCE_KM": "20"
      }
    }
  }
}
```

El script carga el token Viewer desde `GRAFANA_TOKEN_FILE` (no hace falta pegarlo en `mcp.json`) y usa el Python del `.venv` del repo.

No sustituye la API de producción: el planificador usa el backend; el MCP es para depuración desde Cursor.

## Dify (#6092)

`trip-guide-from-car` incluye `context.consumption_profile` y campos efectivos en `trip_context_json`. El puente Cursor narra el histórico sin alterar el plan. Ver [`DIFY_TRIP_GUIDE.md`](DIFY_TRIP_GUIDE.md).

## Divergencia en vivo (#6091)

El plan **no** usa `est_battery_range_km` como Wh/km de planificación. Sí se estima un consumo instantáneo:

`live_wh_per_km = capacity_kwh × 1000 × (SOC/100) / est_battery_range_km`

Si `|live − plan| / plan ≥ CONSUMPTION_DIVERGENCE_ALERT_PCT` (default 15), el Asistente alerta y ofrece recalcular (SOC/posición vivos; consumo del plan sigue siendo histórico).

## Fuera de alcance

- Escritura a Influx desde Electrolineras.
