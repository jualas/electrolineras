# Plan de carga viable (SOC, consumo y rutas)

Última actualización: 2026-06-25

## Problema

En muchos viajes en EV, el navegador del coche o de un operador concreto propone paradas **geográficamente válidas pero impracticables** para la ruta que quieres hacer:

- **Sierra y zonas con poca densidad de cargadores** — desvíos largos, llegada con SOC muy bajo.
- **Rutas alternativas por vías secundarias** — alejadas del corredor de autopista donde se concentran supercargadores u otros hubs del operador; el nav del coche suele optimizar su red, no tu desvío.
- **Autopista convencional** — comparar si conviene cargar ya, aguantar hasta la siguiente DC o tomar una alternativa con mejor precio/disponibilidad (REVE).

Necesitamos un **plan de carga genérico** (cualquier EV) que, con el **SOC actual** y el **consumo del vehículo**, evalúe candidatos a lo largo de **la ruta elegida** (principal o alternativa) y compare estrategias antes de entrar en zona crítica.

Caso de referencia: Granada → Cartagena en [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md). Este documento extiende esa búsqueda en corredor con **modelo energético**.

## Decisión de producto (2026-06-25)

| Incluido en MVP | Pospuesto |
|-----------------|-----------|
| App **genérica** (marca/modelo como preset, no cuenta Tesla) | TeslaMate, Fleet API, telemetría del coche |
| **SOC % manual** en UI (slider o input) | Auto-lectura del cuadro de instrumentos |
| **Ubicación** vía GPS del móvil (`navigator.geolocation`) | Bluetooth OBD, APIs de fabricante |
| Presets de consumo por modelo EV | Histórico personal de consumo |

Referencia de preset inicial (uso interno / default sugerido): **Tesla Model 3 Standard Range 2023** (~57 kWh útil, **420 km** al 100 % en cuadro, ~136 Wh/km calibrado).

## Objetivo Fase 2

| Entrada | Salida |
|---------|--------|
| Preset EV + SOC % manual | 2–3 estrategias comparables |
| Origen = **GPS móvil** (o ciudad/manual) + destino opcional + min kW | Cargador recomendado + alternativas |
| Ruta principal o **alternativa** (#6029 corredor) + factor consumo ajustable | Alertas si ninguna opción es segura |

## Fuentes de datos

### Ubicación (origen)

Reutilizar el patrón ya existente en `RouteSearchPanel` / `CitySearchPanel`:

- `navigator.geolocation.getCurrentPosition` con permiso explícito del usuario.
- **Plan de carga (#6055):** `watchPosition` con `enableHighAccuracy` mientras la pestaña está activa — origen prioritario = GPS del **teléfono** (Android Auto / navegador del móvil, no telemetría del coche).
- Fallback: dirección geocodificada o toque en mapa (#6034, #6035).
- Centrar mapa y usar coords como origen del plan (#6054).

### Perfil de vehículo (#6053)

Todo **manual / local** (localStorage o session; sin backend de cuentas):

1. **Catálogo de presets** genéricos (marca + modelo + capacidad útil kWh + Wh/km de referencia).
2. **SOC %** introducido por el usuario antes de planificar.
3. **Ajuste consumo** (Wh/km) y **factor terreno** (+15–30 % vs llano; p. ej. sierra).
4. Sin conexión al coche ni a TeslaMate en esta fase.

Implementación web (`src/web/src/vehicle/`):

| Preset | Capacidad útil | km al 100 % | Wh/km ref. |
|--------|----------------|-------------|------------|
| Tesla Model 3 SR (2023) — **default** | 57 kWh | 420 | 136 |
| Tesla Model Y LR | 75 kWh | 533 | 141 |
| VW ID.3 Pro | 58 kWh | 426 | 136 |
| Hyundai Kona Electric 64 kWh | 64 kWh | 484 | 132 |
| Renault Megane E-Tech | 60 kWh | 450 | 133 |
| BMW i4 eDrive40 | 81 kWh | 590 | 137 |
| MG4 Standard | 51 kWh | 435 | 117 |
| Nissan Leaf 62 kWh | 59 kWh | 385 | 153 |

`km al 100 %` = autonomía de referencia como el cuadro del coche (WLTP / estimación del fabricante). El plan de carga descuenta además la reserva SOC (10 %) y el factor de terreno.

Terreno: llano (×1), ondulado (+15 %), sierra (+25 %). Persistencia: `localStorage` clave `electrolineras.vehicleProfile`.

Estimación simplificada:

```
energía_disponible_kwh = capacidad_kwh × (soc_pct - soc_reserva) / 100
autonomía_km ≈ energía_disponible_kwh / (consumo_wh_km / 1000 × factor_terreno)
```

Para cada candidato en corredor: `distancia_ruta_km` → `soc_llegada_estimado`.

## Clasificación de opciones

| Nivel | Condición (borrador) | UI |
|-------|----------------------|-----|
| **Segura** | SOC llegada ≥ margen (p. ej. 15 %) | Verde |
| **Ajustada** | SOC llegada entre 10–15 % | Ámbar |
| **Crítica** | SOC llegada < 10 % o sin cargador en autonomía | Rojo |

Ranking adicional: desvío km (#6029), potencia kW, `dynamic_status` y precio REVE (#6050).

### API motor (#6054)

`GET /api/v1/stations/charging-plan`

Parámetros principales (además de filtros corredor `min_kw`, `corridor_km`, …):

| Parámetro | Descripción |
|-----------|-------------|
| `origin_lat`, `origin_lon` | Origen (GPS o geocodificado) |
| `dest_lat`, `dest_lon` | Destino; **omitir ambos** → modo emergencia |
| `soc_percent` | SOC actual |
| `usable_capacity_kwh` | Capacidad útil del preset |
| `consumption_wh_per_km` | Consumo base |
| `terrain_factor` | Multiplicador terreno (1.0 / 1.15 / 1.25) |
| `reserve_soc_percent` | Reserva mínima (default 10) |
| `safe_margin_pct` | Umbral «segura» (default 15) |

Respuesta: `range_km`, `stops[]` con `soc_arrival_pct` y `classification`, `strategies[]` (`charge_now`, `next_safe`, `best_value`), `warnings[]`, geometría de ruta en modo `route`.

Implementación: `src/api/routing/charging_plan.py` · tests `tests/test_charging_plan.py`, `tests/test_api_charging_plan.py`.

## Modos de uso

1. **Plan con destino** — origen (GPS), destino, SOC → paradas intermedias viables en la ruta elegida.
2. **Ruta alternativa** — misma lógica sobre un trazado por vías secundarias (corredor distinto al de la autopista / red del operador).
3. **Emergencia** — solo posición GPS + SOC → **cargador viable más cercano**.
4. **Comparar estrategias** — «cargar ya» vs «aguantar hasta la siguiente DC de 150 kW» vs alternativa con mejor precio/disponibilidad.

## Backlog TaskBoard

| Orden | Tarea | Área |
|-------|-------|------|
| 5 | [#6053](../TASKBOARD.md#task-6053) Perfil vehículo genérico (presets + SOC manual) | Frontend + API meta |
| 6 | [#6054](../TASKBOARD.md#task-6054) Motor plan de carga viable (SOC + rutas) | API |
| 7 | [#6055](../TASKBOARD.md#task-6055) UI plan de carga + GPS origen | Frontend |

Depende de: [#6029](../TASKBOARD.md#task-6029) corredor, [#6050](../TASKBOARD.md#task-6050) dinámico REVE.

## Fase 3 — Agente plan de carga (Dify, mini PC)

**Prerrequisito:** motor determinista [#6054](../TASKBOARD.md#task-6054) y UI base [#6055](../TASKBOARD.md#task-6055) cerrados.

El agente **no sustituye** los cálculos de SOC, corredor ni clasificación segura/ajustada/crítica. Dify actúa como **orquestador y explicador** sobre tools HTTP que invocan la API Electrolineras.

### Infraestructura

| Componente | Rol |
|------------|-----|
| **Mini PC — Dify** | Workflow (MVP) y, más adelante, Agent ReAct con tools |
| **FastAPI Electrolineras** | Fuente de verdad numérica (`charging-plan`, corredor, REVE) |
| **OSRM** | Rutas y alternativas (autopista vs secundaria) |
| **Web (#6058)** | Modo asistente opcional; fallback a #6054 si Dify no responde |

### Patrón recomendado (MVP)

1. **Workflow Dify fijo** (no LLM libre al inicio): rutas A/B → score por ruta → top estrategias → LLM solo redacta texto.
2. **Salida estructurada:** JSON Schema (`route_id`, `station_ids[]`, `strategy`, `soc_arrival_pct`, `classification`); el modelo no inventa coords ni estaciones.
3. **Principio:** *LLM propone narrativa, motor valida números.*

### Roles del agente (1 workflow o 3 apps Dify)

| Rol | Función | ¿LLM decide números? |
|-----|---------|----------------------|
| Explorador de rutas | 2–3 trazados (rápida / alternativa / secundaria) | No |
| Estratega de carga | Comparar «cargar ya» vs «siguiente parada» vs «cambiar ruta» | No (solo rerank blando) |
| Asistente | Explicar por qué una opción es mala (p. ej. Granada→Cartagena) | No |

### Tools previstas (#6056)

| Tool | Descripción |
|------|-------------|
| `get_route_alternatives` | Origen, destino, perfil → lista de rutas con `route_id` |
| `score_charging_plan` | Ruta + SOC + perfil EV → estrategias clasificadas |
| `list_viable_stops` | Corredor + min kW → candidatos (wrapper de along-route / charging-plan) |

Auth: red interna (LAN) o token de servicio; Dify no expuesto a internet sin protección.

### Backlog TaskBoard (Fase 3 agente)

| Orden | Tarea | Área |
|-------|-------|------|
| 1 | [#6056](../TASKBOARD.md#task-6056) Contrato API/tools OpenAPI | API |
| 2 | [#6057](../TASKBOARD.md#task-6057) Workflow Dify MVP | Dify + ops |
| 3 | [#6058](../TASKBOARD.md#task-6058) UI agente opcional + feature flag | Frontend |

Variable de entorno prevista: `CHARGING_AGENT_ENABLED` (default `true` en API; UI #6058 con flag propio).

Documentación detallada: [`CHARGING_AGENT.md`](CHARGING_AGENT.md).

### Evaluación pendiente (#6057)

- Workflow vs Agent ReAct en Dify (empezar por Workflow).
- Modelo local (Ollama en mini PC) vs API remota — latencia y coste por replanificación.
- Pesos de preferencia blanda (precio REVE vs seguridad SOC vs desvío).

## Fuera de alcance MVP (Fase 2)

- TeslaMate, Fleet API, telemetría en tiempo real del vehículo
- Tiempo de carga detallado (curva DC por modelo)
- Ocupación predictiva
- Elevación OSRM en tiempo real (fase posterior; MVP usa factor terreno fijo)

## Backlog futuro (post Fase 3 agente)

- Integración TeslaMate u OBD para SOC automático
- Calibración de consumo con histórico real del usuario
- Fleet API para envío de parada al nav del coche
- Agent ReAct Dify con preferencias en lenguaje natural (tras validar Workflow #6057)

## Criterios de aceptación

- [ ] Usuario puede fijar preset EV + SOC % manual y guardar preferencia local.
- [ ] Origen del plan = GPS móvil (con permiso) o fallback manual existente.
- [ ] Con SOC manual, API devuelve ≥ 1 opción **segura** en ruta de prueba (p. ej. Granada→Cartagena o ruta secundaria con fixture).
- [ ] Con SOC bajo, modo emergencia devuelve cargador más cercano viable.
- [ ] UI muestra 2–3 estrategias con SOC estimado al llegar.
- [ ] Documentado en UI que estimaciones son orientativas; el SOC real lo marca el conductor.

## Referencias

- [`NAVIGATION.md`](NAVIGATION.md) — Fase C planificador inteligente
- [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md) — corredor y anti-retroceso
