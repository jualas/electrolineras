# Fase 2 — Datos dinámicos y cobertura complementaria (España)

Última actualización: 2026-06-25

## Objetivo

Completar el mapa peninsular con estaciones que faltan en el NAP oficial, mostrar **disponibilidad** y **precio** cuando existan, y ofrecer un **plan de carga viable** (SOC + consumo sobre la ruta elegida, incluidas alternativas por vías secundarias) sin depender de una app de operador concreto.

## Problema que motiva la fase

El NAP DGT (DATEX II) es la fuente legal de referencia, pero:

- Algunos emplazamientos operativos **no aparecen** en el NAP (p. ej. Zunder Hotel Mirasierra — Baza, 360 kW en A-92).
- El NAP es **estático** (actualización diaria); no incluye disponibilidad ni tarifas en tiempo real.
- El nav del coche u operador suele optimizar **su red de cargadores** (p. ej. supercargadores en autopista), no rutas alternativas por vías secundarias ni el **SOC restante** en sierra o zonas con pocos puntos de carga.

REVE (mapareve.es), operado por Red Eléctrica como SGV, agrega datos OCPI de los CPOs y expone una **API pública de lectura** descubierta en esta fase.

## Fuentes Fase 2

| Fuente | Rol | Acceso |
|--------|-----|--------|
| NAP DGT (DATEX II) | Verdad estática oficial ES | Feed XML (Fase 1) |
| MOBI.E (DATEX II) | Verdad estática PT | Feed XML (Fase 1) |
| **REVE API pública** | Cobertura complementaria + dinámico ES (sin clave) | `https://www.mapareve.es/api/public/v1` |
| **REVE API oficial** | Misma cobertura con clave (`REVE_API_KEY`) | `https://www.mapareve.es/api/external/v1` |
| OCPI directo (CPO) | Futuro si REVE no basta | Portal clientes REE (solo CPOs) |

Ver detalle técnico REVE en [`DATA_SOURCES.md`](DATA_SOURCES.md#españa--reve-api-pública-maparevees).

## Estrategia de merge

```
NAP (ES) ──► SQLite (estaciones base, id es-dgt-*)
                    ▲
                    │ enrich: dynamic_status, dynamic_price
                    │ insert: emplazamientos solo en REVE
REVE sync ──────────┘
```

Reglas:

1. **Coincidencia** NAP ↔ REVE: misma estación si distancia ≤ 150 m (Haversine).
2. **Si hay match**: se conserva el registro NAP; se actualizan columnas dinámicas.
3. **Si no hay match**: se inserta estación nueva `es-reve-{uuid}` con datos REVE.
4. Portugal no cambia en esta fase (MOBI.E + estado dinámico PT en backlog).

## Backlog TaskBoard (Fase 2)

| Orden | Tarea | Área |
|-------|-------|------|
| 1 | [#6048](../TASKBOARD.md#task-6048) Cliente API pública REVE | Datos |
| 2 | [#6049](../TASKBOARD.md#task-6049) Sync REVE + merge NAP | Datos |
| 3 | [#6050](../TASKBOARD.md#task-6050) API/mapa: disponibilidad y precio | API + frontend |
| 4 | [#6051](../TASKBOARD.md#task-6051) UI optimizada navegador Tesla | Frontend |
| 5 | [#6053](../TASKBOARD.md#task-6053) Perfil vehículo genérico (presets + SOC manual) | Frontend |
| 6 | [#6054](../TASKBOARD.md#task-6054) Plan de carga viable (SOC + consumo + rutas) | API |
| 7 | [#6055](../TASKBOARD.md#task-6055) UI plan de carga (comparar opciones) | Frontend |

Documentación del planificador energético: [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md).

**Fase 3 (agente Dify):** tras cerrar #6054–#6055, capa opcional de orquestación en mini PC — [#6056](../TASKBOARD.md#task-6056)–[#6058](../TASKBOARD.md#task-6058). Ver [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md#fase-3--agente-plan-de-carga-dify-mini-pc).

**Fase Prod** (#6037–#6047, #6052) sigue siendo paralela/despliegue; no sustituye Fase 2.

### Operaciones en producción (no son tareas Fase 2)

Pasos opcionales o de despliegue que **no** van en el backlog funcional de Fase 2, sino en Fase Prod:

| Acción | Tarea TaskBoard | Bloquea cierre Fase 2 |
|--------|-----------------|------------------------|
| Instalar logrotate en el host | [#6052](../TASKBOARD.md#task-6052) (post-#6040) · checklist [#6047](../TASKBOARD.md#task-6047) | No |
| Configurar `INGEST_WEBHOOK_URL` | [#6052](../TASKBOARD.md#task-6052) · alertas ingest [#6045](../TASKBOARD.md#task-6045) | No |
| `docker compose up -d --build` tras cambios API/frontend | [#6038](../TASKBOARD.md#task-6038) · [`DEPLOYMENT.md`](DEPLOYMENT.md#5-cron-de-ingestión-producción-6040) | Sí para **verificar** [#6050](../TASKBOARD.md#task-6050) en `:8015` |
| Sync REVE completo + COALESCE (DATEX no borra precios) | Criterio de [#6049](../TASKBOARD.md#task-6049) | Sí para cerrar [#6049](../TASKBOARD.md#task-6049) |

## Comandos

```bash
# Sync REVE sobre la BD existente (requiere red)
make ingest-reve

# Pipeline DATEX + REVE
make ingest-reve-full

# Solo probar parser (sin red)
pytest tests/test_reve_sync.py -q
```

Variables opcionales (`.env`):

| Variable | Default | Descripción |
|----------|---------|-------------|
| `REVE_API_KEY` | *(vacío)* | Clave API oficial REE; activa `/api/external/v1` |
| `REVE_BASE_URL` | *(auto)* | Override de base URL; por defecto public o external según clave |
| `REVE_SYNC_PER_PAGE` | `25` | Página en POST `/locations` (máx. 25 en API REVE) |
| `REVE_MATCH_RADIUS_M` | `150` | Radio merge NAP ↔ REVE |

## Criterios de éxito Fase 2

- [x] Zunder Baza (360 kW) visible en mapa tras `make ingest-reve`.
- [x] Popup muestra disponibilidad y precio €/kWh cuando REVE los aporta.
- [x] Panel vehículo: presets EV, SOC manual, consumo y factor terreno; persistencia `localStorage` (#6053).
- [x] Pestaña «Plan de carga»: GPS del teléfono (watchPosition), estrategias, mapa con autonomía y clasificación (#6055).
- [x] Listas búsqueda ruta/ciudad muestran badge REVE cuando exista (#6050).
- [x] Estaciones NAP existentes enriquecidas sin duplicar marcadores.
- [x] Upsert DATEX **no borra** `dynamic_*` ya poblados por REVE (COALESCE en `repository.py`; test en `tests/test_repository.py`).
- [ ] Tras ingest ES en prod, conteo REVE con precio se mantiene (verificar con `verify_ingest.py reve`).
- [x] Documentación y tests del cliente/sync (`tests/test_reve_sync.py`).
- [ ] **Verificación prod** (#6050): rebuild Docker (#6038) y comprobar popup en `:8015` — no bloquea merge de código, sí el cierre operativo en prod.

## Riesgos y límites

- La API pública de mapareve.es no estaba documentada para terceros; con **clave oficial** (`REVE_API_KEY`) usar la API external y respetar los términos REE.
- Términos de uso: revisar aviso legal REE/MITECO antes de producción intensiva.
- Acceso OCPI directo al SGV requiere registro como CPO en portal REE (no aplica a consumidores de mapa).
