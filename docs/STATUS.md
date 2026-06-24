# Estado del proyecto

Última actualización: 2026-06-24

## Fase actual

**Fase 1 — MVP datos + mapa**. [#6029](../TASKBOARD.md#task-6029) completada (búsqueda en ruta). Siguiente tarea: [#6030 API búsqueda en ciudad](../TASKBOARD.md#task-6030).

## Gestión de tareas (TaskBoard)

| Rol | Recurso |
|-----|---------|
| Fuente de verdad operativa | [TaskBoard — Electrolineras](https://kanban.jualas.es) (`proyecto id=7`) |
| Espejo en el repo | [`TASKBOARD.md`](../TASKBOARD.md) — exportar tras cambios en el tablero |
| Resumen de avance | Este archivo (`docs/STATUS.md`) |

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
| REVE (dinámico) | Pendiente | Sin API pública documentada |

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
| [#6030](../TASKBOARD.md#task-6030) API — búsqueda en ciudad (potencia + ubicación + acceso) | ⏳ **siguiente** | [`FILTERS.md`](FILTERS.md) |

#### Frontend web

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6031](../TASKBOARD.md#task-6031) Frontend — scaffold web móvil (Vite + MapLibre GL) | ⏳ | [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| [#6032](../TASKBOARD.md#task-6032) Frontend — mapa peninsular con capa de estaciones | ⏳ | [`VISION.md`](VISION.md) |
| [#6033](../TASKBOARD.md#task-6033) Frontend — filtros de potencia (presets + personalizado) | ⏳ | [`FILTERS.md`](FILTERS.md) |
| [#6034](../TASKBOARD.md#task-6034) Frontend — búsqueda en ruta (Granada→Cartagena) | ⏳ | [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md) |
| [#6035](../TASKBOARD.md#task-6035) Frontend — búsqueda en ciudad | ⏳ | [`FILTERS.md`](FILTERS.md) |
| [#6036](../TASKBOARD.md#task-6036) Navegación externa y envío al coche (MVP) | ⏳ | [`NAVIGATION.md`](NAVIGATION.md) |

**Resumen Fase 1:** 8/15 tareas completadas; 7 pendientes (sin contar #6021 de Fase 0).

### Fase 2 — Datos dinámicos y UX Tesla

Sin tareas TaskBoard creadas aún. Objetivos documentados en [`VISION.md`](VISION.md):

- [ ] Investigar acceso datos REVE (disponibilidad, precio)
- [ ] UI optimizada para navegador Tesla (más allá del scaffold base)
- [ ] Tesla Fleet API (v2) — enlaces Google Maps cubiertos en #6036

### Fase 3 — Unión Europea

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
| Hosting | VPS propio vs cloud estático | — |
| Integración Tesla | Solo enlaces vs Fleet API en v2 | #6036 |
| Planificador de ruta | Solo export externo vs SOC/consumo en v3 | #6029 |
| Filtros potencia/acceso | Ver [`FILTERS.md`](FILTERS.md) — presets + heurísticas CC | #6030, #6033 |

## Notas

REVE ya cubre gran parte del mercado español con datos dinámicos, pero no sustituye nuestro objetivo: **península unificada + filtro por potencia + neutralidad** respecto a Tesla u otros operadores.
