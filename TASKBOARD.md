<!-- taskboard-export: generated file; safe to edit for notes -->
<!-- taskboard-project-id: 7 -->
<!-- taskboard-exported-at: 2026-06-24T18:31:50Z -->

# TaskBoard — Electrolineras

**Proyecto:** Electrolineras (`id=7`)  
**Estado del proyecto:** `planning`  
**Workspace:** `/mnt/datos/Proyectos/Electrolineras`  
**Exportado:** 2026-06-24 18:31 UTC  
**Git:** `main` @ `032b5ea`  

> Fuente de verdad operativa: TaskBoard. Este archivo es espejo para IDE/CLI.

## Descripción del proyecto

Aplicacion (Para vehiculo tesla o aplicacion web) que nos muestre en mapas todas las electrolineras de la peninsula (En un futuro recoger si los de mas paises de la union europea publican esa informacion)
Nos tiene que dejar seleccionar por potencia de carga. (Ahora lo tengo disperso en la app de tesla prevalecen sus cargadores y en el resto tampoco estan todos juntos), (hay que recoger la informacion de la web del gobierno de españa 
donde se publica la informacion de los puntos de carga )

## Resumen por estado

| Estado | Tareas |
|--------|--------|
| En progreso (`in_progress`) | 0 |
| Pendiente (`pending`) | 7 |
| Completada (`completed`) | 9 |

---

## Pendiente (`pending`)

<a id="task-6030"></a>
### [#6030] API — búsqueda en ciudad (potencia + ubicación + acceso)

| Campo | Valor |
|-------|-------|
| ID | `6030` |
| Estado | `pending` |
| Complejidad | media |
| Horas estimadas | 8 |
| Posición Kanban | 10.0 |
| Actualizado | 2026-06-22 19:31 UTC |

Endpoint GET /api/v1/stations/nearby: lat/lon o dirección geocodificada, radio default 1 km (decisión STATUS.md), min/max kW, filtros acceso (público, ad-hoc, excluir CC). Referencia: docs/FILTERS.md.

---

<a id="task-6031"></a>
### [#6031] Frontend — scaffold web móvil (Vite + MapLibre GL)

| Campo | Valor |
|-------|-------|
| ID | `6031` |
| Estado | `pending` |
| Complejidad | media |
| Horas estimadas | 6 |
| Posición Kanban | 11.0 |
| Actualizado | 2026-06-22 19:31 UTC |

Inicializar src/web con Vite + React o Svelte (decisión pendiente; recomendado React/Vite en ARCHITECTURE.md), MapLibre GL, layout mobile-first, variables CSS para tema claro/oscuro base.

---

<a id="task-6032"></a>
### [#6032] Frontend — mapa peninsular con capa de estaciones

| Campo | Valor |
|-------|-------|
| ID | `6032` |
| Estado | `pending` |
| Complejidad | media |
| Horas estimadas | 10 |
| Posición Kanban | 12.0 |
| Actualizado | 2026-06-22 19:31 UTC |

Mapa interactivo ES+PT mostrando puntos desde API/GeoJSON con clustering o tiles según zoom, popup con operador, potencia máxima y número de conectores.

---

<a id="task-6033"></a>
### [#6033] Frontend — filtros de potencia (presets + personalizado)

| Campo | Valor |
|-------|-------|
| ID | `6033` |
| Estado | `pending` |
| Complejidad | media |
| Horas estimadas | 6 |
| Posición Kanban | 13.0 |
| Actualizado | 2026-06-22 19:31 UTC |

UI chips: Lento, Semi-rápido, Rápido, Viaje (≥100), Ultrarrápido (≥150), Personalizado (slider min-max). Perfiles En viaje / En ciudad / Todo según docs/FILTERS.md. Sincronizar con query API.

---

<a id="task-6034"></a>
### [#6034] Frontend — búsqueda en ruta (Granada→Cartagena)

| Campo | Valor |
|-------|-------|
| ID | `6034` |
| Estado | `pending` |
| Complejidad | compleja |
| Horas estimadas | 12 |
| Posición Kanban | 14.0 |
| Actualizado | 2026-06-22 19:31 UTC |

Pantalla/flujo: origen (GPS o ciudad), destino, preset potencia, resultados lista+mapa en corredor, ordenados por menor desvío. Caso de uso principal del producto.

---

<a id="task-6035"></a>
### [#6035] Frontend — búsqueda en ciudad

| Campo | Valor |
|-------|-------|
| ID | `6035` |
| Estado | `pending` |
| Complejidad | media |
| Horas estimadas | 8 |
| Posición Kanban | 15.0 |
| Actualizado | 2026-06-22 19:31 UTC |

Flujo: ubicación (GPS / dirección / toque en mapa), radio ajustable (default 1 km), potencia y acceso. Perfil «En ciudad» con preset AC lento por defecto.

---

<a id="task-6036"></a>
### [#6036] Navegación externa y envío al coche (MVP)

| Campo | Valor |
|-------|-------|
| ID | `6036` |
| Estado | `pending` |
| Complejidad | simple |
| Horas estimadas | 3 |
| Posición Kanban | 16.0 |
| Actualizado | 2026-06-22 19:31 UTC |

Botones «Navegar» con enlace Google Maps (destination=lat,lon), copiar coordenadas al portapapeles. Sin Tesla Fleet API en v1. Referencia: docs/NAVIGATION.md.

---

## Completada (`completed`)

<a id="task-6021"></a>
### [#6021] Commit inicial del repositorio

| Campo | Valor |
|-------|-------|
| ID | `6021` |
| Estado | `completed` |
| Complejidad | simple |
| Horas estimadas | 1 |
| Posición Kanban | 8.0 |
| Actualizado | 2026-06-23 23:01 UTC |

Incluir .gitignore, README.md, docs/, estructura data/scripts/src y snapshot estable del proyecto. Cierra el último ítem pendiente de Fase 0 en STATUS.md.

---

<a id="task-6022"></a>
### [#6022] Bootstrap del proyecto y entorno de desarrollo

| Campo | Valor |
|-------|-------|
| ID | `6022` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 4 |
| Posición Kanban | 9.0 |
| Actualizado | 2026-06-24 11:23 UTC |

Crear esqueleto según docs/ARCHITECTURE.md: pyproject.toml o requirements.txt (Python 3.11+, lxml, FastAPI, uvicorn), package.json para frontend (Vite), README con instrucciones de arranque local, variables de entorno (.env.example).

---

<a id="task-6029"></a>
### [#6029] API — búsqueda en ruta (corredor + anti-retroceso)

| Campo | Valor |
|-------|-------|
| ID | `6029` |
| Estado | `completed` |
| Complejidad | compleja |
| Horas estimadas | 16 |
| Posición Kanban | 9.0 |
| Actualizado | 2026-06-24 18:31 UTC |

Endpoint GET /api/v1/stations/along-route: origen, destino, min_kw, ancho corredor (km), orden por menor desvío. Integrar routing OSRM/GraphHopper para polilínea y filtrar estaciones en corredor en sentido de marcha. Reglas: docs/ROUTE_CORRIDOR_SEARCH.md.

---

<a id="task-6023"></a>
### [#6023] Script de descarga NAP España (DATEX II)

| Campo | Valor |
|-------|-------|
| ID | `6023` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 4 |
| Posición Kanban | 10.0 |
| Actualizado | 2026-06-24 11:23 UTC |

Implementar fetch_spain.py que descargue el feed XML oficial NAP DGT/MITECO, guarde raw en data/raw/es/ con timestamp y maneje errores/reintentos. Referencia: docs/DATA_SOURCES.md.

---

<a id="task-6024"></a>
### [#6024] Script de descarga NAP Portugal MOBI.E (streaming)

| Campo | Valor |
|-------|-------|
| ID | `6024` |
| Estado | `completed` |
| Complejidad | compleja |
| Horas estimadas | 8 |
| Posición Kanban | 11.0 |
| Actualizado | 2026-06-24 11:25 UTC |

Implementar fetch_portugal.py con descarga por streaming del XML ~180 MB MOBI.E NAP, escritura incremental a disco y validación de integridad básica.

---

<a id="task-6025"></a>
### [#6025] Parser DATEX II unificado (España + Portugal)

| Campo | Valor |
|-------|-------|
| ID | `6025` |
| Estado | `completed` |
| Complejidad | compleja |
| Horas estimadas | 16 |
| Posición Kanban | 12.0 |
| Actualizado | 2026-06-24 11:25 UTC |

Implementar datex_parser.py que normalice ambos feeds a un esquema común: id, nombre, operador, lat/lon, conectores (potencia kW, tipo), país, acceso, fetched_at, source_version.

---

<a id="task-6026"></a>
### [#6026] Modelo normalizado Station y persistencia SQLite

| Campo | Valor |
|-------|-------|
| ID | `6026` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 6 |
| Posición Kanban | 13.0 |
| Actualizado | 2026-06-24 11:25 UTC |

Definir station.py (Pydantic/dataclass) y capa de persistencia SQLite (+ SpatiaLite si se usa geo index). Tablas con índices por bbox, min_kw, país. Decisión MVP: SQLite según ARCHITECTURE.md.

---

<a id="task-6027"></a>
### [#6027] Pipeline de ingestión y export GeoJSON

| Campo | Valor |
|-------|-------|
| ID | `6027` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 6 |
| Posición Kanban | 14.0 |
| Actualizado | 2026-06-24 11:26 UTC |

Orquestar descarga → parse → persistencia → export data/processed/stations.geojson. CLI scripts/ingest_all.py ejecutable manualmente y preparado para cron (ES diario, PT cada 6–12 h).

---

<a id="task-6028"></a>
### [#6028] API REST FastAPI — consulta de estaciones

| Campo | Valor |
|-------|-------|
| ID | `6028` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 8 |
| Posición Kanban | 17.0 |
| Actualizado | 2026-06-24 18:28 UTC |

Levantar src/api/main.py con endpoints: GET /api/v1/stations (filtros min_kw, max_kw, country, bbox), GET /api/v1/stations/{id}, GET /api/v1/meta/stats, GET /api/v1/meta/operators. Respuesta paginada GeoJSON/JSON.

---

## Referencia rápida (agentes / CLI)

- Estados válidos: `pending`, `in_progress`, `completed`
- Para sincronizar cambios al tablero: MCP `taskboard`, API TaskBoard o modo **Planificar** en la web.
- Regenerar este archivo: `POST /api/projects/7/taskboard-md` o botón **Exportar TASKBOARD.md**.
