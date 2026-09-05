# Guía de viaje con Dify (agente IA)

Integración del asistente de planificación con workflow Dify: números del motor determinista + narrativa LLM (paradas, garantía SOC en destino, visitas mientras cargas).

## Flujo

1. **Asistente web** → `GET /api/v1/private/trip-guide-from-car` (sesión TOTP o token).
2. **API** calcula plan (`charging_plan` + `destination_stay`) con telemetría TeslaMate.
3. Se arma **contexto JSON** (`TripGuideContext`) con SOC, paradas, cargadores cercanos al destino y POIs (Nominatim).
4. Si `DIFY_*` está configurado → workflow Dify redacta `guide_text`; si falla o no hay config → guía markdown local.

## Variables de entorno

```env
# Dify solo en LAN del minipc (sin túnel). Desde el contenedor electrolineras:
DIFY_API_BASE=http://<IP-LAN-SERVIDOR>:8590/v1
DIFY_TRIP_WORKFLOW_API_KEY=app-xxxxxxxx
DIFY_TIMEOUT_SECONDS=90
```

Consola web (solo LAN): `http://<IP-LAN-SERVIDOR>:8590/` — no hay `dify.jualas.es` ni exposición pública.

`GET /api/v1/private/status` expone `dify_trip_guide_configured`.

## Workflow Dify (MVP #6057)

**App en consola:** `Electrolineras — guía de viaje EV`  
**App ID:** `ea5deb84-d738-4dba-b4c2-6babc50b400f`  
**DSL en repo:** `docs/dify/electrolineras-trip-guide.yml` (reimportar con `dify_import_app` si hace falta).  
**Publicado:** versión `v3-multi-parada-e2e` (nodo Code → cursor-cli-bridge; prompt multi-parada en el puente).

Detalle del puente Cursor: [DIFY_CURSOR.md](./DIFY_CURSOR.md).

### Obtener API key y conectar Electrolineras

1. En el minipc, abre **solo en LAN**: `http://<IP-LAN-SERVIDOR>:8590` → app **Electrolineras — guía de viaje EV** → **API Access** → crear clave (`app-…`).
2. En `/mnt/datos/docker/electrolineras/.env`:

```env
DIFY_API_BASE_URL=http://<IP-LAN-SERVIDOR>:8590/v1
DIFY_TRIP_WORKFLOW_API_KEY=app-xxxxxxxx
```

(Alternativa si prefieres `host.docker.internal`: añade `extra_hosts` en compose y usa `http://host.docker.internal:8590/v1`.)

3. `docker compose up -d --force-recreate electrolineras`

Comprobar desde el contenedor:

```bash
docker exec electrolineras python -c "import urllib.request; print(urllib.request.urlopen('http://<IP-LAN-SERVIDOR>:8590/').status)"
```

Prueba del workflow (desde el minipc, con la clave):

```bash
curl -s -X POST "http://<IP-LAN-SERVIDOR>:8590/v1/workflows/run" \
  -H "Authorization: Bearer $DIFY_TRIP_WORKFLOW_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"inputs":{"trip_context_json":"{\"destination_label\":\"Barcelona\"}","agent_summary":"Ruta de prueba"},"response_mode":"blocking","user":"test"}' \
  | jq '.data.outputs.guide_text[:400]'
```

### Entradas del workflow

| Variable | Tipo | Descripción |
|----------|------|-------------|
| `trip_context_json` | string | JSON de `TripGuideContext` + `plan_snapshot` (incluye rutas, `planned_stops[]`, SOC) |
| `agent_summary` | string | Resumen rule-based del motor |

### Campos clave en `plan_snapshot`

El LLM debe usar **solo** estos datos; no recalcular SOC ni inventar estaciones.

| Campo | Descripción |
|-------|-------------|
| `geodesic_distance_km` | Distancia en línea recta origen→destino |
| `route_distance_km` | Ruta activa elegida por el usuario |
| `route_shortest_distance_km` / `route_fastest_distance_km` / `route_conventional_distance_km` | Referencias OSRM (directa, rápida, convencionales) |
| `route_variants_approximate` | `true` si las refs son aproximadas (fallback) |
| `route_preference` | `fastest` \| `shortest` \| `conventional` |
| `planned_stops[]` | Paradas ordenadas: `order`, `label`, `route_distance_km`, `leg_distance_km`, `soc_arrival_pct`, `soc_departure_pct`, `charge_minutes`, `max_power_kw`, `classification` |
| `projected_soc_at_destination_with_plan` | SOC estimado al destino **con** el plan multi-parada |
| `soc_at_destination_pct` | SOC al destino **sin** paradas en ruta |
| `destination_stay` | Objetivo recomendado, gap, cargadores cercanos al destino |

### Salida esperada

| Variable | Tipo |
|----------|------|
| `guide_text` | string (markdown) |

### Prompt del LLM (experto EV #6155)

Canonical: [`docs/agent/ev_expert_prompt.md`](agent/ev_expert_prompt.md) (el puente Cursor lo carga).  
Playbook / knowledge: [`docs/agent/ev_travel_playbook.md`](agent/ev_travel_playbook.md).  
Dataset Dify: `electrolineras-ev-travel-expert` (`9fd6aa22-117c-4d65-9810-2c1fd69c12a5`). El workflow actual redacta vía Cursor (prompt); el dataset sirve para RAG si se enlaza en consola.

El LLM **interpreta** el plan como conductor EV (micro-paradas, buffer en destino, ETA OSRM vs Google). No recalcula.

Campos extra en `plan_snapshot`:

| Campo | Uso |
|-------|-----|
| `planned_stops[].wrong_side` | Cambio de sentido / lado de vía |
| `planned_stops[].soc_gain_pct` | Ganancia de carga |
| `planned_stops[].charge_worthwhile` / `micro_stop` | Criterio #6154 |
| `ev_expert.eta_note` | OSRM sin tráfico, velocidad ajustada |
| `ev_expert.eta_includes_charge` | El total suma recarga |
| `ev_expert.destination_rural` | Destino con poca DC |

```
(ver docs/agent/ev_expert_prompt.md)
```

### Nodos HTTP opcionales en Dify

Para recalcular sin telemetría del coche:

- `GET /api/v1/agent/trip-advice` — plan + bullets
- `GET /api/v1/agent/score-charging-plan` — alias reducido
- `GET /api/v1/agent/trip-guide` — contexto + guía (`invoke_dify=false` recomendado en HTTP; el LLM del workflow redacta)

Auth: `Authorization: Bearer PRIVATE_API_TOKEN` o header `X-Private-Token`.

## Knowledge base Grafana (opcional)

Si en Dify tienes dataset con histórico de consumo / cargas (export Grafana → markdown):

- Conecta knowledge retrieval al nodo LLM.
- Instrucción: usar solo para matices de consumo real vs nominal; **nunca** sustituir SOC del JSON en vivo.

## UI

Pestaña **Asistente** → «Planificar desde el coche» genera plan en mapa + bloque **Guía de viaje** (badge «Motor local» o «IA»).

Checkbox: incluir ideas culturales y gastronomía (`cultural_poi`).

## Prueba local

```bash
curl -s -H "X-Private-Token: $PRIVATE_API_TOKEN" \
  "http://127.0.0.1:8000/api/v1/private/trip-guide-from-car?dest_lat=41.39&dest_lon=2.17&dest_label=Barcelona&include_route=true&invoke_dify=false" \
  | jq '.guide_source, .guide_text[:200]'
```
