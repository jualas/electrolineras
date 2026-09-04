# Planificador de ruta — paridad REVE + telemetría

Hoja de ruta para alinear [Electrolineras](https://electro.jualas.es) con el planificador de [mapareve.es](https://www.mapareve.es/) e integrar consumo histórico (TeslaMate / Grafana).

Tareas TaskBoard: **#6085–#6093**.

---

## Referencia REVE — Cartagena → Irun (~812 km)

### Entradas típicas

| Parámetro | Valor REVE |
|-----------|------------|
| Capacidad batería | 60 kWh |
| Potencia máx. carga | 100 kW |
| Consumo | 17 kWh/100 km |
| SOC salida | 100 % |
| SOC mín. destino | 10 % |
| SOC mín. al llegar a parada | 10 % |
| SOC máx. carga DC | 80 % |
| Evitar peajes | sí |
| Excluir carga lenta (AC) | sí |

### Salida esperada (jul 2026)

| Métrica | REVE |
|---------|------|
| Distancia | ~812 km |
| Tiempo total | ~10 h 38 min |
| Paradas | 3 |
| Tiempo recarga | ~50 min |
| SOC al destino | ~10 % |
| Consumo energía | ~138 kWh |
| Tramos | ~200 km / ~2 h 20 |
| Por parada | llegada ~10 % → carga hasta ~66 %, ~20 min @ 100 kW |

---

## Estado actual vs objetivo

| Área | Tenemos | Falta vs REVE |
|------|---------|---------------|
| Parámetros | SOC, capacidad, Wh/km, min kW, peajes | SOC destino/parada/max carga configurables; kWh/100km; excluir AC |
| Motor | Greedy multi-hop, curva DC, tramos ~2 h | Optimización global tiempo (conducción + recarga); SOC objetivo por parada |
| Salida viaje | range, warnings, planned_stops | Tiempo total, kWh, coste €, resumen estilo REVE |
| Salida parada | leg km/min, SOC, charge_min | kWh tramo, kW efectivo, coste parada |
| Telemetría | TeslaMate vivo, simulación salida | Consumo histórico Grafana por tipo de ruta |
| IA | Dify sobre JSON motor | Perfil consumo real en contexto |

---

## Fases de implementación

### Fase 1 — Parámetros API/UI (#6086) ✅ en curso

Nuevos query params en `GET /api/v1/stations/charging-plan` (y stack privado/agente):

- `min_destination_soc_pct` (default **10**, antes 30 fijo en motor)
- `min_stop_arrival_soc_pct` (default **10**)
- `max_charge_soc_pct` (default **80**)
- `max_charge_power_kw` (default **100**)
- `exclude_slow_chargers` (default **false**; UI REVE marcado por defecto → suelo **≥100 kW**; si el plan no cierra, alternativa **≥50 kW** con warnings)
- Alias: `consumption_kwh_per_100km`, `battery_capacity_kwh`, `departure_soc_pct`

UI colapsable en Plan de carga y Asistente.

### Fase 2 — Motor optimizador (#6087)

Evolucionar `build_planned_route_stops` hacia minimización de **tiempo total** (OSRM + DC):

1. Ventanas ~2 h por velocidad media OSRM
2. Candidatos del corredor espaciado (`rank_stations_along_route_for_planning`)
3. Beam search / DP acotado con curva DC
4. Ranking: kW efectivo, precio REVE, desvío, minutos carga

Benchmark: Cartagena→Irun → ~3 paradas, ~50 min carga, ~10 % destino.

### Fase 3 — Métricas API (#6088)

Extender `ChargingPlanResponse` / `planned_stops[]`:

- Viaje: `total_trip_minutes`, `total_charge_minutes`, `total_energy_kwh`, `estimated_charge_cost_eur`
- Parada: `leg_energy_kwh`, `effective_charge_kw`, `charge_cost_eur`

### Fase 4 — UI estilo REVE (#6089)

Panel resumen viaje + tabla paradas como mapareve; ajustes colapsables.

### Fase 5 — Telemetría Grafana (#6090–#6091)

- Perfil consumo histórico por bins (autopista / convencional / sierra)
- SOC y consumo instantáneos Tesla en motor

### Fase 6 — Dify (#6092)

Contexto enriquecido: consumo histórico + `route_trip_summary` REVE.

### Fase 7 — Benchmark CI (#6093)

`tests/test_reve_benchmark_irun.py` — fixture golden vs REVE.

---

## Archivos principales

| Componente | Ruta |
|------------|------|
| Motor planificación | `src/api/routing/charging_plan.py` |
| Curva DC | `src/api/routing/dc_charge_curve.py` |
| Servicio API | `src/api/charging_plan_service.py` |
| Endpoint | `src/api/routes/charging_plan.py` |
| UI plan | `src/web/src/search/ChargingPlanPanel.tsx` |
| UI asistente | `src/web/src/auth/AssistantPanel.tsx` |
| Ajustes REVE UI | `src/web/src/search/RevePlanningFields.tsx` |

---

## Configuración OSRM (alternativas ruta)

Producción: `OSRM_USE_MULTI_PROFILE=true`, perfiles `car` + `shortest`, convencionales con `exclude=motorway`.

Ver [`docker/osrm/README.md`](../docker/osrm/README.md) y [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md).

---

## Enlaces

- [EV_RANGE_PLAN.md](EV_RANGE_PLAN.md) — visión plan de carga
- [DIFY_TRIP_GUIDE.md](DIFY_TRIP_GUIDE.md) — agente IA
- [TASKBOARD.md](../TASKBOARD.md#task-6085) — tareas #6085–#6093
