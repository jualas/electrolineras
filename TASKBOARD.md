<!-- taskboard-export: generated file; safe to edit for notes -->
<!-- taskboard-project-id: 7 -->
<!-- taskboard-exported-at: 2026-07-05T16:40:37Z -->

# TaskBoard — Electrolineras

**Proyecto:** Electrolineras (`id=7`)  
**Estado del proyecto:** `planning`  
**Workspace:** `/mnt/datos/Proyectos/Electrolineras`  
**Exportado:** 2026-07-05 16:40 UTC  
**Git:** `main` @ `29d20a41`  

> Fuente de verdad operativa: TaskBoard. Este archivo es espejo para IDE/CLI.

## Descripción del proyecto

Aplicacion (Para vehiculo tesla o aplicacion web) que nos muestre en mapas todas las electrolineras de la peninsula (En un futuro recoger si los de mas paises de la union europea publican esa informacion)
Nos tiene que dejar seleccionar por potencia de carga. (Ahora lo tengo disperso en la app de tesla prevalecen sus cargadores y en el resto tampoco estan todos juntos), (hay que recoger la informacion de la web del gobierno de españa 
donde se publica la informacion de los puntos de carga )

## Resumen por estado

| Estado | Tareas |
|--------|--------|
| En progreso (`in_progress`) | 0 |
| Pendiente (`pending`) | 10 |
| Completada (`completed`) | 54 |

---

## Pendiente (`pending`)

<a id="task-6064"></a>
### [#6064] Prod — Cloudflare Access subdominio privado (opcional)

| Campo | Valor |
|-------|-------|
| ID | `6064` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-30 16:47 UTC |

Opcional — capa extra de seguridad: subdominio `electro-private.jualas.es` (o ruta `/private`) protegido con Cloudflare Zero Trust (solo email autorizado), además del TOTP ya implementado. El mapa público en `electro.jualas.es` queda sin login. No bloquea el asistente actual (TOTP en misma URL). Documentar en PHASE3_PRIVATE_STACK.md y Zero Trust.

---

<a id="task-6067"></a>
### [#6067] Routing — evaluación tráfico en tiempo real

| Campo | Valor |
|-------|-------|
| ID | `6067` |
| Estado | `pending` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

OSRM no tiene tráfico; Google gana en corredores con tiempos similares. Evaluar: Google Routes API (de pago), TomTom, GraphHopper+tráfico, o documentar limitación y mantener heurística OSRM (OSRM_FASTEST_ALTERNATIVE_TOLERANCE).

---

<a id="task-6068"></a>
### [#6068] Routing — perfil convencional en multi-perfil (exclude motorway)

| Campo | Valor |
|-------|-------|
| ID | `6068` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Con OSRM_USE_MULTI_PROFILE=true el perfil conventional ya no excluye autovía como antes. Restaurar exclude=motorway o perfil OSRM dedicado; tests test_osrm_route.py conventional. Caso: rutas secundarias sin autopista.

---

<a id="task-6069"></a>
### [#6069] Routing — calibrar/exponer OSRM_FASTEST_ALTERNATIVE_TOLERANCE

| Campo | Valor |
|-------|-------|
| ID | `6069` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Ajuste fino del 5% de tolerancia en desempate fastest (velocidad media vs min duration). Calibrar con pares origen–destino reales; opcional UI avanzada o documentar en .env.

---

<a id="task-6074"></a>
### [#6074] Datos — integración Open Charge Map

| Campo | Valor |
|-------|-------|
| ID | `6074` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Integrar Open Charge Map (OCM_API_KEY en .env.example vacía) como cobertura complementaria fuera de NAP/REVE. Cliente HTTP + merge en pipeline ingest.

---

<a id="task-6075"></a>
### [#6075] UI — filtro por operador

| Campo | Valor |
|-------|-------|
| ID | `6075` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Filtro/chips por operador en UI (Tesla, Ionity, Zunder…). API ya expone operator en estaciones; mejorar visibilidad en mapa y búsqueda en ruta/ciudad.

---

<a id="task-6076"></a>
### [#6076] Fase 4 — Unión Europea (NAPCORE + DATEX genérico)

| Campo | Valor |
|-------|-------|
| ID | `6076` |
| Estado | `pending` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Fase 4 roadmap: inventariar NAPs UE (NAPCORE), conector DATEX II genérico reutilizable, ampliar mapa más allá de ES+PT. Sin implementación aún — epic.

---

<a id="task-6077"></a>
### [#6077] Agente IA — ReAct con preferencias en lenguaje natural

| Campo | Valor |
|-------|-------|
| ID | `6077` |
| Estado | `pending` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Tras validar workflow Dify fijo #6057: agent ReAct con preferencias en lenguaje natural («evita peajes», «prefiero barato»). LLM no recalcula SOC; orquesta tools API.

---

<a id="task-6078"></a>
### [#6078] Agente IA — evaluación modelo local vs remoto (Dify)

| Campo | Valor |
|-------|-------|
| ID | `6078` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Decidir y documentar modelo Dify: local (Ollama mini PC) vs API remota — latencia, coste por replanificación, privacidad.

---

<a id="task-6079"></a>
### [#6079] Roadmap producto — orden post-fix routing (Jul 2026)

| Campo | Valor |
|-------|-------|
| ID | `6079` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:04 UTC |

Roadmap producto sugerido (orden): Ops estabilidad → Routing UI 2 rutas → TeslaMate SOC → Curva carga + preferencias → Tráfico real → Fase 4 UE. Epic de seguimiento; tareas hijas #6065–#6078.

---

## Completada (`completed`)

<a id="task-6065"></a>
### [#6065] Ops — Priorización estabilidad (post-análisis routing Jul 2026)

| Campo | Valor |
|-------|-------|
| ID | `6065` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 1.0 |
| Actualizado | 2026-07-04 12:26 UTC |

Orden de ejecución acordado tras fix routing Cartagena→Zaragoza. Tareas TaskBoard existentes — no duplicar implementación:

🔴 Rápido: #6052 logrotate + webhook ingest (scripts listos; activar en mini PC)
🔴 #6041 backups SQLite + data/
🟠 #6045 monitoring (health, OSRM, ingest)
🟠 #6042 rate limiting + hardening API
🟠 #6046 Nominatim self-hosted o proveedor
🟡 #6038 compose prod con nginx
🟡 #6043 .env.production.example
🟡 #6044 CI/CD pytest + deploy automático
⚪ #6064 Cloudflare Access subdominio privado (opcional)

Nota: #6039 HTTPS/dominio — en la práctica resuelto por Cloudflare Tunnel; cerrar o adaptar documentando setup actual.

Empezar por #6052 → #6041 → #6045.

---

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

<a id="task-6030"></a>
### [#6030] API — búsqueda en ciudad (potencia + ubicación + acceso)

| Campo | Valor |
|-------|-------|
| ID | `6030` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 8 |
| Posición Kanban | 10.0 |
| Actualizado | 2026-06-24 18:44 UTC |

Endpoint GET /api/v1/stations/nearby: lat/lon o dirección geocodificada, radio default 1 km (decisión STATUS.md), min/max kW, filtros acceso (público, ad-hoc, excluir CC). Referencia: docs/FILTERS.md.

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

<a id="task-6031"></a>
### [#6031] Frontend — scaffold web móvil (Vite + MapLibre GL)

| Campo | Valor |
|-------|-------|
| ID | `6031` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 6 |
| Posición Kanban | 11.0 |
| Actualizado | 2026-06-24 18:54 UTC |

Inicializar src/web con Vite + React o Svelte (decisión pendiente; recomendado React/Vite en ARCHITECTURE.md), MapLibre GL, layout mobile-first, variables CSS para tema claro/oscuro base.

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

<a id="task-6032"></a>
### [#6032] Frontend — mapa peninsular con capa de estaciones

| Campo | Valor |
|-------|-------|
| ID | `6032` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 10 |
| Posición Kanban | 12.0 |
| Actualizado | 2026-06-24 18:59 UTC |

Mapa interactivo ES+PT mostrando puntos desde API/GeoJSON con clustering o tiles según zoom, popup con operador, potencia máxima y número de conectores.

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

<a id="task-6033"></a>
### [#6033] Frontend — filtros de potencia (presets + personalizado)

| Campo | Valor |
|-------|-------|
| ID | `6033` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 6 |
| Posición Kanban | 13.0 |
| Actualizado | 2026-06-24 19:03 UTC |

UI chips: Lento, Semi-rápido, Rápido, Viaje (≥100), Ultrarrápido (≥150), Personalizado (slider min-max). Perfiles En viaje / En ciudad / Todo según docs/FILTERS.md. Sincronizar con query API.

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

<a id="task-6034"></a>
### [#6034] Frontend — búsqueda en ruta (Granada→Cartagena)

| Campo | Valor |
|-------|-------|
| ID | `6034` |
| Estado | `completed` |
| Complejidad | compleja |
| Horas estimadas | 12 |
| Posición Kanban | 14.0 |
| Actualizado | 2026-06-24 19:12 UTC |

Pantalla/flujo: origen (GPS o ciudad), destino, preset potencia, resultados lista+mapa en corredor, ordenados por menor desvío. Caso de uso principal del producto.

---

<a id="task-6035"></a>
### [#6035] Frontend — búsqueda en ciudad

| Campo | Valor |
|-------|-------|
| ID | `6035` |
| Estado | `completed` |
| Complejidad | media |
| Horas estimadas | 8 |
| Posición Kanban | 15.0 |
| Actualizado | 2026-06-24 19:15 UTC |

Flujo: ubicación (GPS / dirección / toque en mapa), radio ajustable (default 1 km), potencia y acceso. Perfil «En ciudad» con preset AC lento por defecto.

---

<a id="task-6036"></a>
### [#6036] Navegación externa y envío al coche (MVP)

| Campo | Valor |
|-------|-------|
| ID | `6036` |
| Estado | `completed` |
| Complejidad | simple |
| Horas estimadas | 3 |
| Posición Kanban | 16.0 |
| Actualizado | 2026-06-24 19:16 UTC |

Botones «Navegar» con enlace Google Maps (destination=lat,lon), copiar coordenadas al portapapeles. Sin Tesla Fleet API en v1. Referencia: docs/NAVIGATION.md.

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

<a id="task-6037"></a>
### [#6037] Prod — OSRM self-hosted (península ibérica)

| Campo | Valor |
|-------|-------|
| ID | `6037` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-03 17:24 UTC |

Desplegar instancia OSRM propia para producción (sustituir router.project-osrm.org). Incluir: Docker con datos OSM ES+PT (Geofabrik), build del grafo driving, servicio en red interna/VPS, healthcheck, actualización trimestral del mapa. Configurar OSRM_BASE_URL en prod apuntando al servicio interno. Documentar RAM/disco estimado y tiempos de build.

---

<a id="task-6038"></a>
### [#6038] Prod — Docker Compose stack (API, web, nginx, OSRM)

| Campo | Valor |
|-------|-------|
| ID | `6038` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 11:05 UTC |

Definir docker-compose.prod.yml: FastAPI (uvicorn sin reload), build estático Vite servido por nginx, reverse proxy nginx, servicio OSRM (o referencia externa), volúmenes persistentes para data/db, data/raw y logs. Makefile/docker targets: build, up, down. Alinear con docs/ARCHITECTURE.md (Docker + nginx).

---

<a id="task-6039"></a>
### [#6039] Prod — HTTPS, dominio y reverse proxy

| Campo | Valor |
|-------|-------|
| ID | `6039` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 11:07 UTC |

Configurar dominio público, certificados TLS (Let's Encrypt / Caddy), nginx o Caddy como reverse proxy hacia API y estáticos. Forzar HTTPS, headers de seguridad básicos, redirección www. Documentar DNS y renovación certificados.

---

<a id="task-6040"></a>
### [#6040] Prod — Cron ingestión DATEX con monitoring

| Campo | Valor |
|-------|-------|
| ID | `6040` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 19:49 UTC |

Activar cron/systemd en producción para ingest-es (diario) e ingest-pt (cada 6–12 h) usando scripts/cron/electrolineras.crontab.example. Logs rotados, notificación en fallo (email/webhook), verificación post-ingest (conteos mínimos, tabla ingest_run). Sin depender de ejecución manual.

---

<a id="task-6041"></a>
### [#6041] Prod — Backups SQLite y volumen data/

| Campo | Valor |
|-------|-------|
| ID | `6041` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:13 UTC |

Estrategia de backup: stations.db + data/raw reciente + GeoJSON export. Cron de backup diario, retención (7/30 días), prueba de restauración documentada. Considerar snapshot antes de cada ingest PT (~180 MB XML).

---

<a id="task-6042"></a>
### [#6042] Prod — Rate limiting, CORS y hardening API

| Campo | Valor |
|-------|-------|
| ID | `6042` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:24 UTC |

Implementar rate limiting en FastAPI (por IP/IP+endpoint), CORS restringido al dominio prod, desactivar /docs en prod o proteger con auth básica. Timeouts OSRM, límites de payload. Alinear con ARCHITECTURE.md (seguridad API pública).

---

<a id="task-6043"></a>
### [#6043] Prod — Variables de entorno y secretos

| Campo | Valor |
|-------|-------|
| ID | `6043` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:27 UTC |

Crear .env.production.example sin valores sensibles; documentar variables obligatorias (DATABASE_URL, OSRM_BASE_URL, API_CORS_ORIGINS, VITE_API_URL). Gestión de secretos en VPS (permisos, no commitear .env). Separar config dev vs prod (API_RELOAD=false).

---

<a id="task-6044"></a>
### [#6044] Prod — CI/CD despliegue automatizado

| Campo | Valor |
|-------|-------|
| ID | `6044` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:32 UTC |

Pipeline (GitHub Actions o similar): lint + pytest en PR, build imágenes Docker, deploy a VPS (ssh/docker pull). Tag de releases, rollback simple. Opcional: deploy solo tras merge a main.

---

<a id="task-6045"></a>
### [#6045] Prod — Monitoring y alertas (health, OSRM, ingest)

| Campo | Valor |
|-------|-------|
| ID | `6045` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:16 UTC |

Checks externos o internos: /health API, OSRM route smoke test, último ingest_run por país, espacio en disco data/. Alertas si ingest falla, OSRM caído o DB corrupta. Opciones: Uptime Kuma, Prometheus+Grafana, o script cron + webhook.

---

<a id="task-6046"></a>
### [#6046] Prod — Geocodificación en producción (ciudad)

| Campo | Valor |
|-------|-------|
| ID | `6046` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:40 UTC |

Para #6030 en prod: desplegar Nominatim self-hosted (ES+PT) o definir proveedor con límites de uso y fallback. No depender del Nominatim público sin rate limit. Documentar URL, política de caché y coste si es SaaS.

---

<a id="task-6047"></a>
### [#6047] Prod — Runbook y docs/DEPLOYMENT.md

| Campo | Valor |
|-------|-------|
| ID | `6047` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-28 15:58 UTC |

Documento operativo: requisitos VPS (CPU/RAM/disco), pasos primer despliegue, actualizar OSRM mapa, restaurar backup, rotar secretos, checklist pre-go-live. Enlazar desde README y STATUS.md (Fase prod).

---

<a id="task-6048"></a>
### [#6048] Fase 2 — Cliente API pública REVE (mapareve.es)

| Campo | Valor |
|-------|-------|
| ID | `6048` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 18:35 UTC |

Implementar cliente HTTP para /api/public/v1 (markers, locations, detalle). Documentar descubrimiento, límites de uso y términos. Tests con respuestas fixture.

---

<a id="task-6049"></a>
### [#6049] Fase 2 — Sync REVE: cobertura complementaria + datos dinámicos

| Campo | Valor |
|-------|-------|
| ID | `6049` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 20:53 UTC |

Ingest paginado de emplazamientos REVE (ES). Merge con NAP: enriquecer estaciones existentes (status, precio) e insertar emplazamientos ausentes en NAP (ej. Zunder Baza). Integrar en pipeline/cron.

---

<a id="task-6050"></a>
### [#6050] Fase 2 — API y mapa: disponibilidad y precio

| Campo | Valor |
|-------|-------|
| ID | `6050` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 20:53 UTC |

Exponer dynamic_status, dynamic_price en API/GeoJSON. Popup del mapa con badge disponible/ocupado y precio €/kWh cuando exista.

---

<a id="task-6051"></a>
### [#6051] Fase 2 — UI optimizada navegador Tesla

| Campo | Valor |
|-------|-------|
| ID | `6051` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-28 15:58 UTC |

Contraste alto, targets táctiles grandes, modo conducción (pocos clics), pruebas en viewport Tesla.

---

<a id="task-6052"></a>
### [#6052] Prod — Activación host post-#6040 (logrotate + webhook)

| Campo | Valor |
|-------|-------|
| ID | `6052` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 10:10 UTC |

Pasos manuales en mini PC pendientes tras cerrar #6040 (scripts/cron ya desplegados): (1) instalar logrotate — `sudo cp scripts/cron/logrotate.electrolineras.example /etc/logrotate.d/electrolineras`; (2) configurar `INGEST_WEBHOOK_URL` en `scripts/cron/electrolineras.env` y probar POST en fallo simulado; (3) documentar en runbook (#6047). Complementa #6045 (monitoring integral). Ver DEPLOYMENT.md §5.

---

<a id="task-6053"></a>
### [#6053] Fase 2 — Perfil vehículo genérico (presets + SOC manual)

| Campo | Valor |
|-------|-------|
| ID | `6053` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 20:56 UTC |

Perfil de vehículo genérico para planificación EV (sin conectar al coche): (1) catálogo de presets (marca/modelo, capacidad útil kWh, Wh/km de referencia; default sugerido Tesla Model 3 SR 2023); (2) SOC % manual en UI; (3) ajuste consumo y factor sierra/montaña (+15–30 %); (4) persistencia local (localStorage). Sin TeslaMate, Fleet API ni telemetría en esta fase. Documentar en docs/EV_RANGE_PLAN.md. Prerrequisito de #6054.

---

<a id="task-6054"></a>
### [#6054] Fase 2 — Plan de carga viable (SOC + consumo + rutas)

| Campo | Valor |
|-------|-------|
| ID | `6054` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 20:58 UTC |

Motor de viabilidad de carga para cualquier viaje EV (no solo sierra): dado origen/posición, destino opcional, SOC %, perfil vehículo (#6053) y min_kW — estimar autonomía restante (km/SOC), SOC de llegada a candidatos en corredor (#6029), clasificar opciones (segura / ajustada / crítica) con margen mínimo configurable (p. ej. 10 %). Casos de uso: autopista convencional, rutas alternativas por vías secundarias alejadas de corredores de supercargadores u operador concreto, sierra y baja densidad de cargadores. Rankear por: menor desvío, SOC llegada, potencia, disponibilidad REVE (#6050), precio REVE. Endpoint GET /api/v1/stations/charging-plan o extensión de along-route. Modo «solo emergencia»: cargador viable más cercano sin destino final. Tests: Granada→Cartagena, ruta secundaria con desvío largo, fixture sierra (consumo elevado).

---

<a id="task-6055"></a>
### [#6055] Fase 2 — UI plan de carga (comparar opciones)

| Campo | Valor |
|-------|-------|
| ID | `6055` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-25 21:10 UTC |

UI «Plan de carga» en web móvil: origen vía GPS (navigator.geolocation, reutilizar patrón RouteSearchPanel) o manual; SOC % y preset vehículo manual (#6053); destino y preset potencia; presentar 2–3 estrategias comparables (cargar ya / siguiente parada segura / alternativa más rápida, barata o por ruta secundaria). Mapa: corredor, autonomía restante, badges crítico/ok; lista con SOC estimado al llegar, desvío km, kW, €/kWh y disponibilidad REVE. Alertas antes de quedar sin opción viable. Navegación externa (#6036). Sin conexión al coche. Sinergia con #6051 (viewport Tesla browser). Depende de #6053 y #6054.

---

<a id="task-6056"></a>
### [#6056] Fase 3 — Contrato API/tools agente plan de carga (OpenAPI)

| Campo | Valor |
|-------|-------|
| ID | `6056` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-28 15:58 UTC |

Diseñar e implementar el contrato estable para que Dify (mini PC) invoque el motor de #6054 sin recalcular SOC: endpoints/tools documentados en OpenAPI (p. ej. get_route_alternatives, score_charging_plan, list_viable_stops). Salida JSON Schema estricta (route_id, station_ids, strategy, soc_arrival_pct, classification). Prerrequisito: #6054 cerrado. Documentar en docs/EV_RANGE_PLAN.md § Fase 3. Auth: red interna o token de servicio.

---

<a id="task-6057"></a>
### [#6057] Fase 3 — Workflow Dify MVP (rutas + estrategias de carga)

| Campo | Valor |
|-------|-------|
| ID | `6057` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-28 20:43 UTC |

App/workflow en Dify (mini PC): (1) obtener 2–3 rutas (autopista vs alternativa/secundaria) vía tools HTTP; (2) puntuar cada ruta con charging-plan (#6054); (3) comparar estrategias (cargar ya / siguiente parada / cambiar ruta); (4) LLM solo redacta explicación sobre JSON validado — no inventa estaciones ni SOC. Empezar con Workflow fijo (no ReAct libre). Evaluar modelo local vs remoto. Depende de #6056.

---

<a id="task-6058"></a>
### [#6058] Fase 3 — UI agente opcional (feature flag + fallback)

| Campo | Valor |
|-------|-------|
| ID | `6058` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-30 16:47 UTC |

Integración opcional en web (#6055): modo asistente que consulta Dify y muestra comparativa enriquecida; CHARGING_AGENT_ENABLED=false usa solo motor #6054. Fallback si Dify cae. Sin bloquear planificador determinista. Depende de #6057.

---

<a id="task-6059"></a>
### [#6059] Fase 3 — Stack privado (seguridad + TeslaMate)

| Campo | Valor |
|-------|-------|
| ID | `6059` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-30 16:47 UTC |

Token PRIVATE_API_TOKEN, endpoints /api/v1/private/*, cliente TeslaMateApi, docs PHASE3_PRIVATE_STACK.md. Pendiente: Cloudflare Access subdominio privado, UI Tesla #6058.

---

<a id="task-6060"></a>
### [#6060] Planificador — opción ruta más rápida (autovía) vs más corta

| Campo | Valor |
|-------|-------|
| ID | `6060` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-06-30 17:21 UTC |

Hoy el plan usa la ruta más corta (corredor OSRM «shortest»). Añadir selector en UI y backend: **Ruta más corta** (actual) vs **Ruta más rápida** (priorizar autovía/autopista cuando reduzca tiempo). Respetar preferencia «saltarse autopistas/peajes» como filtro OSRM o post-proceso. Mostrar ambas polilíneas o la elegida en mapa; recalcular charging-plan sobre la ruta activa. Documentar en docs/EV_RANGE_PLAN.md. Prerrequisito de paradas automáticas y envío a Google Maps.

---

<a id="task-6061"></a>
### [#6061] Planificador — enviar ruta completa a Google Maps

| Campo | Valor |
|-------|-------|
| ID | `6061` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-02 18:24 UTC |

Botón «Abrir en Google Maps» con la ruta planificada: origen, destino y **waypoints** en cada parada de carga acordada. URL `https://www.google.com/maps/dir/?api=1&origin=…&destination=…&waypoints=…` (y variantes Apple Maps si ya existe patrón #6036). Funciona con ruta corta/rápida seleccionada. Si aún no hay paradas calculadas, enviar solo origen→destino. UX móvil/Tesla browser.

---

<a id="task-6062"></a>
### [#6062] Planificador — paradas automáticas en ruta (autonomía nominal −10 %)

| Campo | Valor |
|-------|-------|
| ID | `6062` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-02 18:24 UTC |

Motor multi-hop sobre la ruta activa: usar **autonomía nominal − reserva 10 %** (o perfil TeslaMate equivalente) para segmentar el viaje y proponer paradas en corredor hasta llegar al destino con margen (objetivo destino ≥30 % o configurable). Marcar en mapa polilínea + pins numerados de parada. Inspiración: planificador Tesla (paradas con cargas ~≤20 min cuando sea posible). Clasificar cada tramo (segura/ajustada). Endpoint o extensión de `charging-plan` devolviendo `planned_stops[]` ordenadas con km desde origen, SOC llegada/salida estimado y tiempo carga aprox. Tests: viaje ~741 km Cartagena→norte, ruta corta y rápida.

---

<a id="task-6063"></a>
### [#6063] Agente IA — narrativa y criterios sobre plan multi-parada

| Campo | Valor |
|-------|-------|
| ID | `6063` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 07:33 UTC |

Ajustar workflow Dify/Cursor y `agent_trip_guide` para consumir el plan multi-parada (#anterior): explicar elección ruta corta vs rápida, por qué cada parada, tiempos de carga orientativos (objetivo ~20 min estilo Tesla), margen en destino y alternativas (precio, potencia). El LLM **no recalcula** SOC ni inventa estaciones; solo redacta sobre JSON validado del motor. Actualizar DSL, docs/DIFY_TRIP_GUIDE.md y prompts. Depende de paradas automáticas y opción ruta rápida.

---

<a id="task-6066"></a>
### [#6066] Routing UI — comparar ruta corta vs rápida (polilíneas)

| Campo | Valor |
|-------|-------|
| ID | `6066` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 12:38 UTC |

Mostrar 2 rutas en la UI con polilíneas superpuestas y selector explícito; no depender solo del motor automático (select_fastest_route_payload). Recalcular charging-plan al cambiar. Relacionado #6060.

---

<a id="task-6070"></a>
### [#6070] Planificador — curva de carga DC por modelo

| Campo | Valor |
|-------|-------|
| ID | `6070` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 16:12 UTC |

Sustituir estimación lineal ~20 min por curva DC según preset vehículo (kW estación vs batería). Mejorar tiempos de parada en planned_stops[] y narrativa agente #6063.

---

<a id="task-6071"></a>
### [#6071] Planificador — SOC automático vía TeslaMate MQTT

| Campo | Valor |
|-------|-------|
| ID | `6071` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 12:45 UTC |

Conectar telemetría TeslaMate (stack privado #6059) al planificador público: SOC real en UI y recálculo de paradas sin entrada manual. MQTT ya configurado en prod.

---

<a id="task-6072"></a>
### [#6072] Planificador — preferencias blandas (operador, peajes, €/kWh)

| Campo | Valor |
|-------|-------|
| ID | `6072` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 16:25 UTC |

UI y pesos configurables: preferir Ionity/operador, evitar peajes, máximo €/kWh. Motor ya rankea por precio REVE; exponer preferencias al usuario y al agente Dify.

---

<a id="task-6073"></a>
### [#6073] Planificador — replanificación en marcha

| Campo | Valor |
|-------|-------|
| ID | `6073` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 16:33 UTC |

Flujo «estoy al X % aquí, recalcula»: origen = posición actual + SOC actual; nuevo charging-plan y paradas hasta destino. UX móvil/Tesla browser.

---

<a id="task-6080"></a>
### [#6080] Deuda — commit inicial del repositorio (#6021)

| Campo | Valor |
|-------|-------|
| ID | `6080` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 16:37 UTC |

Repositorio sin commits en main. Incluir .gitignore, README, docs/, estructura estable. Cierra subtasks pendientes de #6021.

---

<a id="task-6081"></a>
### [#6081] Deuda — arreglar tests OSRM perfil conventional

| Campo | Valor |
|-------|-------|
| ID | `6081` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-05 12:30 UTC |

Corregir test_build_osrm_exclude_param y test_conventional_route_falls_back_when_exclude_unsupported tras cambio multi-perfil OSRM. Relacionado #6068.

---

<a id="task-6082"></a>
### [#6082] Deuda — actualizar docs/STATUS.md

| Campo | Valor |
|-------|-------|
| ID | `6082` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 12:26 UTC |

Actualizar docs/STATUS.md: Fase 3 completada (#6057–#6063), Fase Prod progreso (#6037 done), nuevas tareas #6065+.

---

<a id="task-6083"></a>
### [#6083] Deuda — documentar desempate fastest en ROUTE_CORRIDOR_SEARCH.md

| Campo | Valor |
|-------|-------|
| ID | `6083` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-05 12:39 UTC |

Documentar select_fastest_route_payload: alternativas OSRM, tolerancia 5%, preferencia velocidad media (caso Cartagena→Zaragoza A-7/A-23). docs/ROUTE_CORRIDOR_SEARCH.md

---

<a id="task-6084"></a>
### [#6084] Prod — adaptar/cerrar #6039 (HTTPS vía Cloudflare Tunnel)

| Campo | Valor |
|-------|-------|
| ID | `6084` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-04 11:07 UTC |

HTTPS y dominio público ya operativos vía Cloudflare Tunnel (electro.jualas.es). Actualizar #6039: marcar completada o reescribir como «documentar arquitectura TLS Cloudflare» en DEPLOYMENT.md. No implementar nginx+Let's Encrypt duplicado.

---

## Referencia rápida (agentes / CLI)

- Estados válidos: `pending`, `in_progress`, `completed`
- Para sincronizar cambios al tablero: MCP `taskboard`, API TaskBoard o modo **Planificar** en la web.
- Regenerar este archivo: `POST /api/projects/7/taskboard-md` o botón **Exportar TASKBOARD.md**.
