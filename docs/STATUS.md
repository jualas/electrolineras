# Estado del proyecto

Última actualización: 2026-09-01

## Fase actual

**Viaje activo + handoff navegación (#6131)** integrado en `develop` y prod. Staging `:8016` con smoke API (#6143). Spike dispositivo **#6133 descartado** por alcance (handoff manual + Web Share suficiente).

Siguiente foco sugerido: cierre epic **#6131** en TaskBoard; opcional hostname staging `electro-test.jualas.es` (#6142).

## Promote staging → develop → prod

Flujo acordado (#6141):

1. Desarrollar en `feature/…` (no tocar prod directamente si hay riesgo).
2. `make test` + pytest local.
3. **`make deploy-staging`** → smoke en [`STAGING.md`](STAGING.md) (API + checklist manual móvil/Tesla).
4. PR / merge a `develop`.
5. **`make deploy`** → prod `:8015` / electro.jualas.es.
6. Smoke prod + TaskBoard.

| Entorno | Puerto | Comando deploy |
|---------|--------|----------------|
| Staging | 8016 | `make deploy-staging` |
| Prod | 8015 | `make deploy` |

Detalle operativo: [`STAGING.md`](STAGING.md), [`CI_CD.md`](CI_CD.md).

## Producción (snapshot)

| Servicio | URL / notas |
|----------|-------------|
| Web + API | `https://electro.jualas.es` |
| Stack local | nginx `:8015` → FastAPI; [`docker/docker-compose.prod.yml`](../docker/docker-compose.prod.yml) |
| OSRM | `:5000` car, `:5001` shortest |
| Nominatim | `:8092` (import ~4–12 h) |
| Deploy | `make deploy` · [`CI_CD.md`](CI_CD.md) |

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
| NAP España (DATEX II) | OK | Cron diario 06:15 |
| NAP Portugal (MOBI.E) | OK | Cron cada 6 h |
| REVE (dinámico) | OK | Cron cada 3 h; API mapareve.es |
| Prod HTTPS | OK | Cloudflare Tunnel → nginx `:8015` |
| OSRM self-hosted | OK | Península ES+PT |
| Nominatim self-hosted | ⏳ | Import en curso; fallback público temporal |

## Roadmap (sincronizado con TaskBoard)

### Fase 0 — Definición ✅ completada

| Tarea | Estado | Documentación |
|-------|--------|---------------|
| [#6021](../TASKBOARD.md#task-6021) Commit inicial del repositorio | ⏳ | Repo aún sin commits en `main` — ver [#6080](../TASKBOARD.md#task-6080) |

### Fase 1 — MVP datos + mapa ✅ completada

**Resumen:** 15/15 tareas (#6022–#6036). MVP funcional cerrado.

### Fase Prod — Despliegue y operación ✅ completada (Jul 2026)

Documentación: [`DEPLOYMENT.md`](DEPLOYMENT.md), [`ENV.md`](ENV.md), [`NOMINATIM.md`](NOMINATIM.md), [`CI_CD.md`](CI_CD.md).

| Tarea | Estado | Área |
|-------|--------|------|
| [#6047](../TASKBOARD.md#task-6047) Runbook | ✅ | [`DEPLOYMENT.md`](DEPLOYMENT.md) |
| [#6043](../TASKBOARD.md#task-6043) Variables y secretos | ✅ | [`ENV.md`](ENV.md) |
| [#6037](../TASKBOARD.md#task-6037) OSRM self-hosted | ✅ | `docker/osrm/` |
| [#6038](../TASKBOARD.md#task-6038) Docker Compose prod (nginx) | ✅ | `docker/docker-compose.prod.yml` |
| [#6039](../TASKBOARD.md#task-6039) HTTPS / dominio | ✅ | Cloudflare Tunnel — [#6084](../TASKBOARD.md#task-6084) |
| [#6040](../TASKBOARD.md#task-6040) Cron ingest DATEX + REVE | ✅ | `scripts/cron/` |
| [#6052](../TASKBOARD.md#task-6052) Logrotate + webhook | ✅ | Host mini PC |
| [#6041](../TASKBOARD.md#task-6041) Backups SQLite + data/ | ✅ | `scripts/backup/` |
| [#6042](../TASKBOARD.md#task-6042) Rate limiting + hardening | ✅ | `src/api/security/` |
| [#6045](../TASKBOARD.md#task-6045) Monitoring y alertas | ✅ | `scripts/monitoring/` |
| [#6044](../TASKBOARD.md#task-6044) CI/CD | ✅ | `.github/workflows/` |
| [#6046](../TASKBOARD.md#task-6046) Geocodificación prod | ✅ | Código + import Nominatim en curso |

**Resumen Fase Prod:** 12/12 tareas TaskBoard completadas; pendiente solo **runtime** import Nominatim (automatizado con `wait_and_finish_prod`).

### Fase 2 — Datos dinámicos y UX Tesla ✅ completada

Documentación: [`PHASE2.md`](PHASE2.md).

**Resumen:** 7/7 (#6048–#6055). Comandos: `make ingest-reve`, planificador en [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md).

### Fase 3 — Agente y planificador avanzado ✅ completada

Documentación: [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md), [`CHARGING_AGENT.md`](CHARGING_AGENT.md), [`PHASE3_PRIVATE_STACK.md`](PHASE3_PRIVATE_STACK.md).

| Tarea | Estado | Área |
|-------|--------|------|
| [#6056](../TASKBOARD.md#task-6056) Contrato API/tools agente | ✅ | `agent_tools.py` |
| [#6057](../TASKBOARD.md#task-6057) Workflow Dify MVP | ✅ | Dify mini PC |
| [#6058](../TASKBOARD.md#task-6058) UI agente (feature flag) | ✅ | Frontend |
| [#6059](../TASKBOARD.md#task-6059) Stack privado + TeslaMate | ✅ | TOTP, MQTT |
| [#6060](../TASKBOARD.md#task-6060) Ruta rápida vs corta | ✅ | API + UI |
| [#6061](../TASKBOARD.md#task-6061) Ruta completa Google Maps | ✅ | Waypoints |
| [#6062](../TASKBOARD.md#task-6062) Paradas automáticas multi-hop | ✅ | `charging-plan` |
| [#6063](../TASKBOARD.md#task-6063) Narrativa agente multi-parada | ✅ | Dify DSL |

**Resumen Fase 3:** 8/8 completadas (#6056–#6063).

### Ops estabilidad post-routing — [#6065](../TASKBOARD.md#task-6065) ✅

Epic de julio 2026 tras fix Cartagena→Zaragoza. Todas las tareas infra referenciadas (#6052, #6041–#6046, #6038, #6039, #6043, #6044) cerradas. Opcional pendiente: [#6064](../TASKBOARD.md#task-6064) Cloudflare Access subdominio privado.

### Roadmap producto (Jul 2026) — pendiente

Epic [#6079](../TASKBOARD.md#task-6079). Orden sugerido:

| Prioridad | Tarea | Tema |
|-----------|-------|------|
| 1 | [#6066](../TASKBOARD.md#task-6066) | UI comparar 2 polilíneas ruta corta/rápida |
| 2 | [#6071](../TASKBOARD.md#task-6071) | SOC automático TeslaMate MQTT |
| 3 | [#6070](../TASKBOARD.md#task-6070) / [#6072](../TASKBOARD.md#task-6072) | Curva DC + preferencias blandas |
| 4 | [#6068](../TASKBOARD.md#task-6068) / [#6081](../TASKBOARD.md#task-6081) | Perfil conventional OSRM + tests |
| 5 | [#6067](../TASKBOARD.md#task-6067) | Tráfico en tiempo real (evaluación) |
| 6 | [#6076](../TASKBOARD.md#task-6076) | Fase 4 UE (epic) |

### Fase 4 — Unión Europea

Tarea epic: [#6076](../TASKBOARD.md#task-6076) — NAPCORE, DATEX genérico, ampliar mapa.

## Deuda técnica abierta

| Tarea | Tema |
|-------|------|
| [#6080](../TASKBOARD.md#task-6080) | Commit inicial git en `main` |
| [#6081](../TASKBOARD.md#task-6081) | Tests OSRM perfil conventional |
| [#6083](../TASKBOARD.md#task-6083) | Documentar desempate fastest en [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md) |

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
| Hosting producción | Mini PC + Docker + **Cloudflare Tunnel** (sin Let's Encrypt local) |
| TLS / dominio | `electro.jualas.es` — [#6039](../TASKBOARD.md#task-6039) vía Cloudflare |
| Routing prod | OSRM multi-perfil self-hosted (#6037) |
| Geocodificación prod | Nominatim self-hosted `:8092` (#6046) |
| Planificador EV | Preset + SOC manual; TeslaMate opcional vía stack privado (#6059) |
| Agente plan de carga | Dify Workflow; LLM explica, API calcula (#6056–#6063) |
| Almacenamiento MVP | SQLite 3 + SpatiaLite — [`STORAGE.md`](STORAGE.md) |
| Frontend MVP | React + Vite + TypeScript (`src/web/`) |

## Navegación y envío al coche

Documentado en [`docs/NAVIGATION.md`](NAVIGATION.md). Ruta multi-parada con waypoints: [#6061](../TASKBOARD.md#task-6061).

## Decisiones pendientes

| Tema | Opciones | Tarea relacionada |
|------|----------|-------------------|
| Tráfico en ruta | OSRM sin tráfico vs APIs de pago | [#6067](../TASKBOARD.md#task-6067) |
| Perfil sin autopista | Restaurar exclude motorway en multi-perfil | [#6068](../TASKBOARD.md#task-6068) |
| Modelo Dify | Local Ollama vs API remota | [#6078](../TASKBOARD.md#task-6078) |
| Subdominio privado | Cloudflare Access + TOTP | [#6064](../TASKBOARD.md#task-6064) (opcional) |

## Notas

REVE enriquece datos dinámicos en España, pero no sustituye el objetivo: **península unificada + filtro por potencia + neutralidad** respecto a Tesla u otros operadores.

Import Nominatim: seguir con `make nominatim-logs`; al terminar, cron `wait_and_finish_prod` configura prod y notifica por ntfy.
