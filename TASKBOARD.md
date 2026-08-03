<!-- taskboard-export: generated file; safe to edit for notes -->
<!-- taskboard-project-id: 7 -->
<!-- taskboard-exported-at: 2026-08-03T17:52:21Z -->

# TaskBoard — Electrolineras

**Proyecto:** Electrolineras (`id=7`)  
**Estado del proyecto:** `development`  
**Workspace:** `/mnt/datos/Proyectos/Electrolineras`  
**Exportado:** 2026-08-03 17:52 UTC  
**Git:** `develop` @ `e33d5442`  

> Fuente de verdad operativa: TaskBoard. Este archivo es espejo para IDE/CLI.

## Descripción del proyecto

Aplicacion (Para vehiculo tesla o aplicacion web) que nos muestre en mapas todas las electrolineras de la peninsula (En un futuro recoger si los de mas paises de la union europea publican esa informacion)
Nos tiene que dejar seleccionar por potencia de carga. (Ahora lo tengo disperso en la app de tesla prevalecen sus cargadores y en el resto tampoco estan todos juntos), (hay que recoger la informacion de la web del gobierno de españa 
donde se publica la informacion de los puntos de carga )

## Resumen por estado

| Estado | Tareas |
|--------|--------|
| En progreso (`in_progress`) | 1 |
| Pendiente (`pending`) | 39 |
| Completada (`completed`) | 67 |

---

## En progreso (`in_progress`)

<a id="task-6088"></a>
### [#6088] Planificador REVE — métricas viaje y detalle parada en API

| Campo | Valor |
|-------|-------|
| ID | `6088` |
| Estado | `in_progress` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 16:09 UTC |

Extender `ChargingPlanResponse` / `planned_stops[]` con salida comparable a REVE.

**Resumen viaje (`route_trip_summary`):**
- `total_duration_minutes` (conducción + recarga)
- `driving_duration_minutes`
- `total_charge_minutes`
- `total_energy_kwh` (consumo estimado ruta)
- `estimated_charge_cost_eur` (suma paradas con precio REVE)
- `projected_destination_soc_pct`
- `stop_count`

**Por parada (`PlannedRouteStopResult`):**
- `leg_energy_kwh` (consumo del tramo)
- `recommended_charge_from_pct` / `recommended_charge_to_pct` (ej. 10→66%)
- `effective_charge_power_kw`
- `estimated_charge_cost_eur`
- `operator` (ya en station)

Actualizar `agent_trip_guide` snapshot y narrativa Dify con nuevos campos.
Depende de motor optimización REVE.

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

<a id="task-6089"></a>
### [#6089] Planificador REVE — UI resultado viaje (estilo mapareve)

| Campo | Valor |
|-------|-------|
| ID | `6089` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-08 18:32 UTC |

Presentar el plan como REVE en Asistente y Plan de carga.

Cabecera: «Tu ubicación → Destino», tiempo total, km, N paradas, tiempo recarga, % batería destino, kWh consumo, coste estimado €.

Por parada numerada:
- Tramo: km, tiempo conducción, kWh
- Operador, dirección
- Tiempo recarga estimado, recarga recomendada X%→Y%, potencia kW, coste €

Panel ajustes (colapsable): mismos campos que REVE (capacidad, potencia máx, consumo kWh/100km, SOC salida/mín/máx, evitar peajes, excluir lentos).

Mapa: solo pins de paradas planificadas (no corredor completo).

Depende de métricas API REVE.

---

<a id="task-6127"></a>
### [#6127] Navegación — Google Maps móvil + BT + preacond (Asistente usable)

| Campo | Valor |
|-------|-------|
| ID | `6127` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-08-03 18:20 UTC |

Redefinido: no app Android ni Fleet API ahora. Flujo: Electrolineras → Google Maps en el móvil → Bluetooth (audio). Sin promesa de «Enviar a Tesla» multi-parada.

Hecho:
- CTA primario «Abrir en Google Maps»; «Siguiente parada (preacondicionar)»; compartir enlace; QR desktop.
- Copy honesto: Maps/BT; ~30–40 min antes, nav Tesla para preacondicionar.
- Asistente móvil: panel casi fullscreen, mapa colapsado («Ver mapa»), ajustes/guía en details.
- Docs: `docs/NAVIGATION.md`.

Futuro (fuera de esta entrega): Fleet API parada a parada.

---

<a id="task-6099"></a>
### [#6099] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6099` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1000.0 |
| Actualizado | 2026-07-13 09:05 UTC |

Commit 8517baae5218: Mostrar números de parada con insignias canvas en el mapa.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6100"></a>
### [#6100] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6100` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1001.0 |
| Actualizado | 2026-07-13 09:05 UTC |

Hay 6 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6101"></a>
### [#6101] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6101` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1002.0 |
| Actualizado | 2026-07-13 09:05 UTC |

Commit 73bb719bd60c: Penalizar micro-paradas en el optimizador (#6098) y benchmark Mundaka.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6102"></a>
### [#6102] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6102` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1003.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit ae297143611f: Alinear planificador con REVE: parámetros, métricas y fix de paradas.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6103"></a>
### [#6103] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6103` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1004.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 46 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6104"></a>
### [#6104] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6104` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1005.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 11 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6105"></a>
### [#6105] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6105` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1006.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit b55f2a405c83: Evitar source completo del cron env en test-reve-api.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6106"></a>
### [#6106] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6106` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1007.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 13 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6107"></a>
### [#6107] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6107` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1008.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit 5a64f694cfa0: Arreglar mapa estilo REVE y endurecer auth y API de estaciones.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6108"></a>
### [#6108] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6108` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1009.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 7 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6109"></a>
### [#6109] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6109` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1010.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit d221bd776bac: Actualizar TASKBOARD.md tras cerrar #6080 (snapshot 4d42138).

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6110"></a>
### [#6110] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6110` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1011.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 92 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6111"></a>
### [#6111] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6111` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1012.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 52 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6112"></a>
### [#6112] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6112` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1013.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 38 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6113"></a>
### [#6113] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6113` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1014.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 15 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6114"></a>
### [#6114] Prod — Activación host post-#6040 (logrotate + webhook)

| Campo | Valor |
|-------|-------|
| ID | `6114` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1015.0 |
| Actualizado | 2026-07-13 09:06 UTC |

En el mini PC: (1) instalar logrotate — sudo cp scripts/cron/logrotate.electrolineras.example /etc/logrotate.d/electrolineras; (2) configurar INGEST_WEBHOOK_URL en scripts/cron/electrolineras.env y probar POST con fallo simulado; (3) verificar checklist en docs/DEPLOYMENT.md §5 y enlazar desde runbook (#6047).

---

<a id="task-6115"></a>
### [#6115] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6115` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1016.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit e8cb1c640ffa: Actualizar TASKBOARD.md con hash del commit 443a89c.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6116"></a>
### [#6116] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6116` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1017.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 53 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6117"></a>
### [#6117] Frontend — búsqueda en ruta (Granada→Cartagena)

| Campo | Valor |
|-------|-------|
| ID | `6117` |
| Estado | `pending` |
| Complejidad | compleja |
| Posición Kanban | 1018.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Implementar flujo UI: origen (GPS o ciudad), destino, preset de potencia, resultados en lista y mapa dentro del corredor anti-retroceso, ordenados por menor desvío. Integrar con API REST de búsqueda en ruta existente. Caso de uso principal del MVP.

---

<a id="task-6118"></a>
### [#6118] Frontend — búsqueda en ruta (Granada→Cartagena)

| Campo | Valor |
|-------|-------|
| ID | `6118` |
| Estado | `pending` |
| Complejidad | compleja |
| Posición Kanban | 1019.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Formulario origen/destino (GPS o ciudad), preset potencia Viaje, llamada a /api/v1/stations/along-route, polilínea y estaciones en corredor en MapView, lista ordenada por menor desvío. Referencia: docs/ROUTE_CORRIDOR_SEARCH.md.

---

<a id="task-6119"></a>
### [#6119] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6119` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1020.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 14 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6120"></a>
### [#6120] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6120` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1021.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit ea585e258898: Actualizar TASKBOARD.md con hash del commit 11a9314.

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6121"></a>
### [#6121] API — búsqueda en ciudad (potencia + ubicación + acceso)

| Campo | Valor |
|-------|-------|
| ID | `6121` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1022.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Exponer GET /api/v1/stations/nearby con lat/lon, radio default 1 km, min/max kW y filtros de acceso (público, ad-hoc, excluir CC) según docs/FILTERS.md. Reutilizar repository.nearby existente; respuesta GeoJSON/JSON paginada alineada con el resto de la API.

---

<a id="task-6122"></a>
### [#6122] Cerrar #6022: commitear bootstrap y sincronizar TaskBoard

| Campo | Valor |
|-------|-------|
| ID | `6122` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1023.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Consolidar en un commit el entorno de desarrollo (Python 3.11+, FastAPI, Vite+React, Makefile, .gitignore data/) y cerrar la tarea en TaskBoard con export de TASKBOARD.md y actualización de docs/STATUS.md.

---

<a id="task-6123"></a>
### [#6123] Revisar cambios del último commit

| Campo | Valor |
|-------|-------|
| ID | `6123` |
| Estado | `pending` |
| Complejidad | media |
| Posición Kanban | 1024.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Commit 1002dbec57ae: Alinear documentación del repo con backlog TaskBoard (proyecto id=7).

Comprobar coherencia con el backlog y actualizar tareas si aplica.

---

<a id="task-6124"></a>
### [#6124] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6124` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1025.0 |
| Actualizado | 2026-07-13 09:06 UTC |

Hay 5 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

---

<a id="task-6125"></a>
### [#6125] Organizar y commitear cambios pendientes

| Campo | Valor |
|-------|-------|
| ID | `6125` |
| Estado | `pending` |
| Complejidad | simple |
| Posición Kanban | 1026.0 |
| Actualizado | 2026-07-13 09:07 UTC |

Hay 6 archivo(s) con cambios sin commitear en el workspace. Agrupa el trabajo en commits coherentes con el backlog.

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

<a id="task-6085"></a>
### [#6085] Plan maestro — paridad planificador REVE + IA consumo Grafana

| Campo | Valor |
|-------|-------|
| ID | `6085` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 16:09 UTC |

Documento de referencia y hoja de ruta para alinear Electrolineras con el planificador de mapareve.es e integrar telemetría Tesla/Grafana.

## Referencia REVE (Cartagena → Irun, ~812 km)
Entradas: capacidad 60 kWh, carga máx 100 kW, consumo 17 kWh/100km, SOC salida 100%, SOC mín destino 10%, SOC mín parada 10%, SOC máx carga 80%, evitar peajes, excluir carga lenta.
Salidas: 10h38 total, 3 paradas, 50 min recarga, 10% al destino, 138 kWh consumo, paradas cada ~200 km / ~2h20 con SOC llegada ~10% y recarga recomendada hasta ~66%, ~20 min carga a 100 kW.

## Estado actual Electrolineras (gap)
| Área | Tenemos | Falta vs REVE |
|------|---------|---------------|
| Parámetros | SOC manual, capacidad, Wh/km, min kW, evitar peajes | SOC mín destino/parada/max carga configurables; consumo en kWh/100km; excluir AC |
| Motor | Greedy multi-hop, curva DC, tramos ~2h DGT, exclusión origen | Optimización global tiempo total (conducción+recarga); SOC objetivo por parada (10→66%); kWh por tramo |
| Salida viaje | range_km, warnings, planned_stops parcial | Resumen: tiempo total, min recarga, kWh total, coste €, % destino |
| Salida parada | leg_km, leg_min, SOC llegada/salida, charge_min | kWh tramo, potencia efectiva, % recarga recomendada, coste parada |
| Telemetría | TeslaMate MQTT/API, simulación salida 100% | Consumo histórico Grafana por tipo ruta; instantáneos en motor |
| IA | Dify narrativa sobre JSON motor | Consumo histórico en contexto; sugerencias adaptadas sin recalcular SOC |

## Fases propuestas
1. Parámetros y contrato API REVE (#tareas hijas)
2. Motor optimizador + métricas (#tareas hijas)
3. UI presentación REVE (#tareas hijas)
4. Telemetría Grafana → perfil consumo (#tareas hijas)
5. Dify enriquecido (#tareas hijas)
6. Benchmark Irun automatizado

Crear/actualizar docs/REVE_ROUTE_PLANNER_PLAN.md con esta especificación. Bloquea épicas #6073+.

---

<a id="task-6086"></a>
### [#6086] Planificador REVE — parámetros API/UI (SOC y consumo)

| Campo | Valor |
|-------|-------|
| ID | `6086` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 16:09 UTC |

Alinear entradas del planificador con REVE.

Añadir en API `charging-plan` y UI (Asistente + Plan de carga):
- `battery_capacity_kwh` (ya existe usable_capacity_kwh — alias/documentar)
- `max_charge_power_kw` (potencia máx aceptada por vehículo, default 100)
- `consumption_kwh_per_100km` (además de Wh/km; mostrar como REVE)
- `departure_soc_pct` (SOC salida, default 100)
- `min_destination_soc_pct` (default 10, hoy hardcoded 30)
- `min_stop_arrival_soc_pct` (default 10 — SOC mínimo al llegar a cargador)
- `max_charge_soc_pct` (default 80 — techo carga DC rápida)
- `exclude_slow_chargers` (excluir AC / <50 kW del corredor planificación)

Mantener simulación salida 100% con coche al 65% (TeslaMate) como opción avanzada, no como default del motor.

Tests: validación rangos, defaults REVE, regresión Granada→Irun.
Depende de plan maestro #6073.

---

<a id="task-6087"></a>
### [#6087] Planificador REVE — motor optimización global multi-parada

| Campo | Valor |
|-------|-------|
| ID | `6087` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-10 15:36 UTC |

Sustituir/evolucionar el greedy actual (`build_planned_route_stops`) por un optimizador estilo REVE.

Objetivo: minimizar tiempo total viaje (conducción OSRM + recarga DC) respetando:
- Tramos conducción ~2h (DGT), máx 3h
- SOC llegada parada ≥ min_stop_arrival_soc (10%)
- SOC destino ≥ min_destination_soc (10%)
- Carga hasta max_charge_soc (80%) solo si hace falta para el siguiente tramo
- Sin paradas en zona origen si SOC salida ≥10% (ya iniciado — consolidar)
- Excluir cargadores lentos si `exclude_slow_chargers`
- Ranking: potencia efectiva, precio REVE, desvío, tiempo recarga

Algoritmo propuesto (fases):
1. Segmentar ruta en ventanas ~2h por velocidad OSRM
2. Por ventana, candidatos del corredor espaciado (#planning_corridor)
3. Evaluar combinaciones (beam search / DP acotado) con curva DC (#6070)
4. Elegir secuencia que minimice tiempo total y cumpla SOC

Referencia benchmark: Cartagena→Irun debe dar ~3 paradas, ~50 min carga, ~10% destino, tramos ~200 km (como REVE jul-2026).

Archivos: `charging_plan.py`, tests `test_reve_benchmark_irun.py`.
Depende de parámetros REVE.

---

<a id="task-6090"></a>
### [#6090] Telemetría Grafana — perfil consumo histórico por tipo de ruta

| Campo | Valor |
|-------|-------|
| ID | `6090` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-31 19:35 UTC |

Integrar consumo histórico del vehículo (TeslaMate → Grafana) en el planificador.

**Fuentes:** TeslaMate DB/API, dashboards Grafana existentes con consumo por viaje (Wh/km, kWh/100km, elevación, velocidad media).

**Entregables:**
1. Servicio `consumption_profile_service.py`: agregar viajes históricos (últimos N meses) por bins: autopista, convencional, sierra, urbano
2. Endpoint privado `GET /api/v1/private/consumption-profile` (auth TOTP)
3. Ajuste automático `consumption_wh_per_km` / factor terreno según tipo ruta OSRM (perfil fastest vs conventional)
4. Campos en plan: `consumption_source: preset|telemetry|hybrid`, `confidence`

**No sustituye** el motor determinista: aporta Wh/km más realista que el preset genérico.

Documentar queries Grafana reutilizables y mapeo a bins.
Depende de stack privado #6059.

---

<a id="task-6091"></a>
### [#6091] Telemetría — consumo y SOC instantáneos en planificador

| Campo | Valor |
|-------|-------|
| ID | `6091` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-08-03 17:51 UTC |

Usar datos instantáneos del Tesla (TeslaMate MQTT/API) al planificar.

**Entradas en vivo:** SOC actual, rated_range_km, optional power draw, outside_temp, elevation trend.

**Comportamiento:**
- Origen plan = posición GPS/TeslaMate (no manual si asistente conectado)
- SOC plan = live SOC por defecto; simulación 100% solo bajo demanda explícita
- Recálculo en ruta: si desviación consumo >15% vs plan, alerta y sugerencia replanificar

Extender `vehicle_energy_from_telemetry` y `AssistantPanel` para mostrar qué dato usa el motor (live vs simulado).

Relacionado #6071 (TeslaMate en planificador).

---

<a id="task-6092"></a>
### [#6092] IA Dify — contexto consumo histórico + plan REVE en workflow

| Campo | Valor |
|-------|-------|
| ID | `6092` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-31 20:05 UTC |

Enriquecer workflow Dify con consumo histórico + plan REVE validado.

**Contexto JSON ampliado (`trip_context_json`):**
- `consumption_profile` (bins históricos Grafana)
- `route_trip_summary` estilo REVE
- `planned_stops[]` con recommended_charge_from/to, kWh tramo, coste
- `benchmark_note` si desviación vs media histórica del vehículo

**Reglas LLM (prompt):**
- NO recalcular SOC ni inventar estaciones
- Explicar por qué cada parada (tiempo, operador, precio, SOC)
- Si consumo histórico sugiere más/menos paradas que el motor, mencionarlo como consejo (no alterar JSON)
- Adaptar narrativa a preferencias usuario (peajes, operadores)

Actualizar: `agent_trip_guide.py`, `DIFY_TRIP_GUIDE.md`, workflow Dify, tools HTTP.

**Fase 2 (opcional):** dataset export Grafana → markdown para RAG Dify (entrenamiento continuo).

Depende de métricas REVE API + perfil consumo Grafana.

---

<a id="task-6093"></a>
### [#6093] Benchmark CI — Cartagena→Irun vs planificador REVE

| Campo | Valor |
|-------|-------|
| ID | `6093` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-10 15:36 UTC |

Test de regresión automatizado comparando nuestro plan con REVE.

**Caso fijo:** origen Cartagena (37.62, -0.99) → Irun (43.34, -1.79), parámetros REVE estándar (60 kWh, 17 kWh/100km, 100 kW, SOC 100/10/10/80).

**Aserciones tolerancia:**
- 3±1 paradas
- 45–60 min recarga total
- SOC destino 8–15%
- 1ª parada ≥150 km desde origen
- Tramos conducción 1h45–2h45 cada uno
- kWh total 120–150

Fixture JSON golden (actualizar manualmente si REVE cambia). CI `pytest tests/test_reve_benchmark_irun.py`.

Ejecutar tras cada cambio del motor #6087.

---

<a id="task-6094"></a>
### [#6094] Motor — paradas monótonas en ruta (km crecientes)

| Campo | Valor |
|-------|-------|
| ID | `6094` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 17:22 UTC |

Bug crítico Cartagena→Irun: secuencia km 180→198→182 (parada 3 retrocede). Causas: distance_from_origin_km relativo vs absoluto; candidatos sin filtrar route_position > current_route_km.

Entregables:
- Filtrar estrictamente stop.route_distance_km > current_route_km
- Guardar distance_from_origin_km absoluto desde salida del viaje
- leg_distance_km = stop_km - previous_stop_km
- Test CI que falle si km[i] >= km[i+1]

Prioridad P0 — bloquea planes ejecutables en mapa/Google Maps.

---

<a id="task-6095"></a>
### [#6095] Motor — estrategia carga corta 10→60-70% (Model 3 LFP / REVE)

| Campo | Valor |
|-------|-------|
| ID | `6095` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 17:22 UTC |

Sobrecarga actual: paradas 49→87% (~135 min total vs REVE ~71 min). Filosofía Tesla/REVE: más paradas, más cortas, zona rápida de la curva DC.

Regla: llegada 5-10%, salida 60-70% en paradas intermedias; solo cargar más en tramo final o parada larga (comida). Primer tramo desde 100% puede ser ~3h.

Implementar en _optimal_departure_soc_for_stop: techo ~65%, tramo objetivo ~2h (no 3h) para calcular energía mínima.

Prioridad P0.

---

<a id="task-6096"></a>
### [#6096] Motor — penalizar desvío >5 km en ranking paradas

| Campo | Valor |
|-------|-------|
| ID | `6096` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 17:22 UTC |

Parada La Puebla de Valverde con 18.9 km desvío elegida vs alternativas en corredor. Aumentar peso de deviation_km en _rank_key / _planned_stop_selection_key.

Prioridad P1.

---

<a id="task-6097"></a>
### [#6097] Tests CI — regresión Cartagena→Irun monotonía + carga ≤80 min

| Campo | Valor |
|-------|-------|
| ID | `6097` |
| Estado | `completed` |
| Complejidad | simple |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-09 17:22 UTC |

Extender test_reve_benchmark_irun.py:
- assert planned_stops[i].distance_from_origin_km estrictamente creciente
- assert total_charge_minutes en rango 45-90 min (ajustar tras motor)
- assert soc_departure_pct <= 72 en paradas intermedias

Prioridad P1.

---

<a id="task-6098"></a>
### [#6098] Penalizar micro-paradas y benchmark Cartagena→Mundaka vs Tesla

| Campo | Valor |
|-------|-------|
| ID | `6098` |
| Estado | `completed` |
| Complejidad | media |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-10 18:44 UTC |

Tras comparar Cartagena→Mundaka (882 km) con la app Tesla (3 paradas, 74 min recarga, 9h40 total) vs Electrolineras (4 paradas, 44 min, 10h22): el optimizador genera una micro-parada prematura en Albacete km 198 (llegada 53%, solo 5 min carga) que Tesla evita (1ª parada Atalaya ~280 km, 22%).

Objetivo motor (#6087):
- Penalizar o descartar paradas si SOC llegada > umbral (p.ej. 40%) o carga añade <10 min autonomía.
- Forzar progreso mínimo antes de 1ª parada en autopista (~180–200 km, alineado REVE/Tesla).
- Evitar cadenas con parada casi inútil (53%→58%).

Benchmark CI / regresión:
- Fixture Cartagena (37.625, -0.996) → Mundaka (43.407, -2.698).
- Params: Model 3 SR (57 kWh, 136 Wh/km, 170 kW), SOC 100/10/10/80, exclude_slow.
- Tolerancias: 3–4 paradas, total_charge_minutes ≤ Tesla+20%, sin parada con soc_arrival > 45% salvo emergencia, km monótonos.
- Referencia Tesla jul-2026: Atalaya, Rivas, Aranda; destino ~15%.

Criterio éxito: plan ≤4 paradas, sin micro-parada <15 min con arr>40%, tiempo total competitivo con Tesla (margen +30 min).

---

<a id="task-6126"></a>
### [#6126] Routing — alinear ruta rápida con Google Maps (tráfico / motor)

| Campo | Valor |
|-------|-------|
| ID | `6126` |
| Estado | `completed` |
| Complejidad | compleja |
| Posición Kanban | 999.0 |
| Actualizado | 2026-07-31 19:11 UTC |

Hallazgo de test usuario (2026-07-31): en ciertos viajes la ruta «rápida» OSRM no coincide con Google Maps y las diferencias de tiempo son altas.

Causa raíz probable:
- Motor actual: OSRM self-host (perfil car), sin tráfico en tiempo real.
- Google usa tráfico + velocidades históricas; elige otro corredor cuando hay empates o congestión habitual.
- «Abrir en Google Maps» recalcula la ruta en Google (solo origen/waypoints/destino); no fuerza la polilínea OSRM. El plan de carga se calcula sobre el corredor OSRM → riesgo de paradas fuera de la ruta que el usuario acaba conduciendo.

Ya existe #6067 (evaluación tráfico) y #6069 (tolerancia desempate 5%).

Entregables sugeridos:
1) Recoger 3–5 pares origen/destino reales donde falle.
2) Comparar OSRM vs Google (km, min, corredor) y decidir si ampliar OSRM_FASTEST_ALTERNATIVE_TOLERANCE, mejorar heurística, o integrar API con tráfico (Google Routes / TomTom / GraphHopper).
3) UX: avisar si la exportación a Google puede cambiar el corredor; opcionalmente planificar paradas sobre la geometría que el usuario usará.
4) Documentar limitación en UI (OSRM sin tráfico).

Prioridad: alta (preocupación principal del usuario).

---

## Referencia rápida (agentes / CLI)

- Estados válidos: `pending`, `in_progress`, `completed`
- Para sincronizar cambios al tablero: MCP `taskboard`, API TaskBoard o modo **Planificar** en la web.
- Regenerar este archivo: `POST /api/projects/7/taskboard-md` o botón **Exportar TASKBOARD.md**.
