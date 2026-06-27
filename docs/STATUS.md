# Estado del proyecto

Última actualización: 2026-06-25

## Fase actual

**Fase 2 — Datos dinámicos España (en curso)**. Fase 1 cerrada (#6036). Fase Prod (#6037+) en paralelo cuando toque despliegue.

## Gestión de tareas (TaskBoard)

| Rol | Recurso |
|-----|---------|
| Fuente de verdad operativa | [TaskBoard — Electrolineras](https://kanban.jualas.es) (`proyecto id=7`) |
| Espejo en el repo | [`TASKBOARD.md`](../TASKBOARD.md) — exportar tras cambios en el tablero |
| Resumen de avance | Este archivo (`docs/STATUS.md`) |
| Despliegue / HTTPS / túnel | [`DEPLOYMENT.md`](DEPLOYMENT.md) |

**Convenciones:**

- Cada ítem del roadmap lleva el ID de tarea TaskBoard (`#6022`, etc.) con enlace al detalle en `TASKBOARD.md`.
- Las tareas usan etiquetas `fase-0`, `fase-1`, … alineadas con las fases de [`VISION.md`](VISION.md).
- Al completar una tarea: actualizar estado en TaskBoard → regenerar `TASKBOARD.md` → marcar aquí el checkbox correspondiente.

## Visión acordada

- App **web** (usable en Tesla) con mapa de electrolineras en la **península ibérica**.
- Filtro principal: **potencia de carga (kW)**.
- Datos base: publicación oficial del **gobierno español** (NAP DGT) + **MOBI.E** (Portugal).
- Futuro: ampliar a UE vía NAP de cada país.

## Verificaciones técnicas

| Feed | Estado | Notas |
|------|--------|-------|
| NAP España (DATEX II) | OK | XML accesible, actualizado hoy |
| NAP Portugal (MOBI.E) | OK | XML ~180 MB; requiere descarga por streaming |
| REVE (dinámico) | OK | API pública mapareve.es; sync `make ingest-reve` |

## Roadmap (sincronizado con TaskBoard)

### Fase 0 — Definición ✅ completada

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6021](../TASKBOARD.md#task-6021) Commit inicial del repositorio | ✅ | Estructura repo, `docs/`, `.gitignore` |

### Fase 1 — MVP datos + mapa

#### Infraestructura

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6022](../TASKBOARD.md#task-6022) Bootstrap del proyecto y entorno de desarrollo | ✅ | [`ARCHITECTURE.md`](ARCHITECTURE.md), [`README.md`](../README.md) |

#### Datos e ingestión

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6023](../TASKBOARD.md#task-6023) Script de descarga NAP España (DATEX II) | ✅ | [`DATA_SOURCES.md`](DATA_SOURCES.md) |
| [#6024](../TASKBOARD.md#task-6024) Script de descarga NAP Portugal MOBI.E (streaming) | ✅ | [`DATA_SOURCES.md`](DATA_SOURCES.md) |
| [#6025](../TASKBOARD.md#task-6025) Parser DATEX II unificado (España + Portugal) | ✅ | [`DATA_SOURCES.md`](DATA_SOURCES.md), `src/ingest/datex_parser.py` |
| [#6026](../TASKBOARD.md#task-6026) Modelo normalizado Station y persistencia SQLite | ✅ | [`STORAGE.md`](STORAGE.md), `src/db/` |
| [#6027](../TASKBOARD.md#task-6027) Pipeline de ingestión y export GeoJSON | ✅ | [`README.md`](../README.md), `src/ingest/pipeline.py` |

#### API backend

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6028](../TASKBOARD.md#task-6028) API REST FastAPI — consulta de estaciones | ✅ | [`ARCHITECTURE.md`](ARCHITECTURE.md), `src/api/` |
| [#6029](../TASKBOARD.md#task-6029) API — búsqueda en ruta (corredor + anti-retroceso) | ✅ | [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md), `src/api/routing/` |
| [#6030](../TASKBOARD.md#task-6030) API — búsqueda en ciudad (potencia + ubicación + acceso) | ✅ | [`FILTERS.md`](FILTERS.md), `src/api/routes/nearby.py` |

#### Frontend web

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6031](../TASKBOARD.md#task-6031) Frontend — scaffold web móvil (Vite + MapLibre GL) | ✅ | `src/web/`, [`src/web/README.md`](../src/web/README.md) |
| [#6032](../TASKBOARD.md#task-6032) Frontend — mapa peninsular con capa de estaciones | ✅ | `src/web/src/map/` |
| [#6033](../TASKBOARD.md#task-6033) Frontend — filtros de potencia (presets + personalizado) | ✅ | `src/web/src/filters/`, [`FILTERS.md`](FILTERS.md) |
| [#6034](../TASKBOARD.md#task-6034) Frontend — búsqueda en ruta (Granada→Cartagena) | ✅ | `src/web/src/search/`, [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md) |
| [#6035](../TASKBOARD.md#task-6035) Frontend — búsqueda en ciudad | ✅ | `src/web/src/search/CitySearchPanel.tsx`, [`FILTERS.md`](FILTERS.md) |
| [#6036](../TASKBOARD.md#task-6036) Navegación externa y envío al coche (MVP) | ✅ | `src/web/src/navigation/`, [`NAVIGATION.md`](NAVIGATION.md) |

**Resumen Fase 1:** 15/15 tareas completadas (sin contar #6021 de Fase 0). **MVP funcional cerrado.**

### Fase Prod — Despliegue y operación (tras MVP funcional)

Backlog creado en TaskBoard (`fase-prod`). Ejecutar cuando Fase 1 esté cerrada o en paralelo a frontend si el go-live es inminente.

| Orden sugerido | Tarea | Área |
|----------------|-------|------|
| 1 | [#6047](../TASKBOARD.md#task-6047) Runbook y `docs/DEPLOYMENT.md` | Documentación |
| 2 | [#6043](../TASKBOARD.md#task-6043) Variables de entorno y secretos | Config |
| 3 | [#6037](../TASKBOARD.md#task-6037) **OSRM self-hosted** (ES+PT) | Routing |
| 4 | [#6038](../TASKBOARD.md#task-6038) Docker Compose (API, web, nginx, OSRM) | Infra |
| 5 | [#6039](../TASKBOARD.md#task-6039) HTTPS, dominio y reverse proxy | Infra |
| 6 | [#6040](../TASKBOARD.md#task-6040) Cron ingestión DATEX + REVE ✅ | [`DEPLOYMENT.md`](DEPLOYMENT.md#5-cron-de-ingestión-producción-6040), `scripts/cron/` |
| 6b | [#6052](../TASKBOARD.md#task-6052) Activación host post-#6040 (logrotate + webhook) | Ops — pendiente en mini PC |
| 7 | [#6041](../TASKBOARD.md#task-6041) Backups SQLite y `data/` | Datos |
| 8 | [#6042](../TASKBOARD.md#task-6042) Rate limiting, CORS y hardening API | Seguridad |
| 9 | [#6046](../TASKBOARD.md#task-6046) Geocodificación en producción (ciudad) | Routing |
| 10 | [#6045](../TASKBOARD.md#task-6045) Monitoring y alertas | Ops |
| 11 | [#6044](../TASKBOARD.md#task-6044) CI/CD despliegue automatizado | Ops |

**Nota dev vs prod:** en desarrollo basta `router.project-osrm.org`; en producción usar `OSRM_BASE_URL` apuntando al servicio interno (#6037).

**Resumen Fase Prod:** 1/12 tareas completadas (#6040); 11 pendientes (incl. #6052 post-#6040).

### Fase 2 — Datos dinámicos y UX Tesla (en curso)

Documentación: [`PHASE2.md`](PHASE2.md). Descubrimiento jun 2026: API pública REVE en mapareve.es.

| Orden | Tarea | Estado | Área |
|-------|-------|--------|------|
| 1 | [#6048](../TASKBOARD.md#task-6048) Cliente API pública REVE | ✅ | Datos |
| 2 | [#6049](../TASKBOARD.md#task-6049) Sync REVE + merge NAP | ✅ | Datos |
| 3 | [#6050](../TASKBOARD.md#task-6050) API/mapa: disponibilidad y precio | ✅ | API + frontend |
| 4 | [#6051](../TASKBOARD.md#task-6051) UI optimizada navegador Tesla | ⏳ | Frontend |
| 5 | [#6053](../TASKBOARD.md#task-6053) Perfil vehículo genérico (presets + SOC manual) | ✅ | Frontend |
| 6 | [#6054](../TASKBOARD.md#task-6054) Plan de carga viable (SOC + consumo + rutas) | ✅ | API |
| 7 | [#6055](../TASKBOARD.md#task-6055) UI plan de carga (comparar opciones) | ✅ | Frontend |

**Comandos:** `make ingest-reve` · `make ingest-reve-full` · planificador: ver [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md).

**Resumen Fase 2:** 6/7 completadas (#6048, #6049, #6050, #6053, #6054, #6055); 1 pendiente (#6051).

**Ops prod vinculadas (no Fase 2):** logrotate y webhook → [#6052](../TASKBOARD.md#task-6052); rebuild Docker → [#6038](../TASKBOARD.md#task-6038); ver [`PHASE2.md`](PHASE2.md#operaciones-en-producción-no-son-tareas-fase-2).

### Fase 3 — Agente plan de carga (Dify)

Documentación: [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md#fase-3--agente-plan-de-carga-dify-mini-pc). **Prerrequisito:** #6054–#6055. Infra: Dify en mini PC; agente orquesta, no calcula SOC.

| Orden | Tarea | Estado | Área |
|-------|-------|--------|------|
| 1 | [#6056](../TASKBOARD.md#task-6056) Contrato API/tools agente (OpenAPI) | ⏳ | API |
| 2 | [#6057](../TASKBOARD.md#task-6057) Workflow Dify MVP (rutas + estrategias) | ⏳ | Dify |
| 3 | [#6058](../TASKBOARD.md#task-6058) UI agente opcional (feature flag + fallback) | ⏳ | Frontend |

**Resumen Fase 3 agente:** 0/3 completadas; 3 pendientes.

### Fase 4 — Unión Europea

Sin tareas TaskBoard creadas aún:

- [ ] Inventariar NAPs UE (NAPCORE)
- [ ] Conector genérico DATEX II reutilizable

## Decisiones tomadas

| Tema | Decisión |
|------|----------|
| Alcance geográfico inicial | España + Portugal |
| Fuente principal España | NAP DGT (DATEX II) |
| Fuente principal Portugal | MOBI.E NAP (DATEX II) |
| Cliente MVP | Web / PWA (no app nativa Tesla) |
| Filtro diferenciador | Potencia de carga (kW) |
| Radio default modo ciudad | **1 km** |
| Seguimiento de tareas | TaskBoard (`id=7`) + `TASKBOARD.md` |
| Planificador EV (Fase 2) | App genérica: preset vehículo + SOC manual + GPS móvil; sin TeslaMate/Fleet API en v1 | [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md) |
| Agente plan de carga (Fase 3) | Dify en mini PC; Workflow MVP; LLM explica, API calcula (#6056–#6058) | [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md#fase-3--agente-plan-de-carga-dify-mini-pc) |
| Almacenamiento MVP | SQLite 3 + SpatiaLite (PostGIS si crece) — [`STORAGE.md`](STORAGE.md) |
| Frontend MVP | React + Vite + TypeScript (`src/web/`) |

## Navegación y envío al coche

Documentado en [`docs/NAVIGATION.md`](NAVIGATION.md). Implementación MVP: tarea [#6036](../TASKBOARD.md#task-6036).

| Necesidad | Enfoque acordado (borrador) |
|-----------|----------------------------|
| Enviar 1 parada | MVP: enlace Google/Apple Maps (#6036); v2: Tesla Fleet API |
| Ruta multi-parada | Planificador propio + export Google Maps |
| Ruta completa al nav Tesla | No en v1; parada a parada si Fleet API |
| Uso en Tesla | Web optimizada para navegador del coche |

## Decisiones pendientes

| Tema | Opciones | Tarea relacionada |
|------|----------|-------------------|
| SpatiaLite en v1.0 | Activar extensión geo en #6026 vs solo lat/lon hasta #6029 | #6026, #6029 |
| Frontend | React vs Svelte vs vanilla | ~~#6031~~ decidido: React en #6022 |
| Filtro potencia | Por sitio (max) vs por conector | #6028, #6033 |
| Hosting | VPS propio vs cloud estático | #6038, #6039, [#6047](../TASKBOARD.md#task-6047) |
| Integración vehículo | **Genérico:** preset EV + SOC manual + GPS móvil. TeslaMate/Fleet API pospuesto (v3+) | #6053–#6055 |
| Planificador de ruta | Corredor kW (#6029) ✅; plan determinista Fase 2 (#6053–#6055); agente Dify Fase 3 (#6056–#6058) | [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md) |
| Agente plan de carga | Fase 3: Dify Workflow sobre API (#6054); motor numérico = fuente de verdad; `CHARGING_AGENT_ENABLED` opcional | #6056–#6058 |
| Filtros potencia/acceso | Ver [`FILTERS.md`](FILTERS.md) — presets + heurísticas CC | #6030, #6033 |

## Notas

REVE ya cubre gran parte del mercado español con datos dinámicos, pero no sustituye nuestro objetivo: **península unificada + filtro por potencia + neutralidad** respecto a Tesla u otros operadores.
