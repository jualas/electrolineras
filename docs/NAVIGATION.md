# Navegación y envío de rutas al coche

Documento de necesidades, opciones técnicas y desafíos para enviar **paradas** y **rutas con electrolineras** desde nuestra aplicación web.

## Preguntas clave

1. ¿Desde la web podemos mandar **una parada** al Tesla?
2. ¿Podemos crear una **ruta con varias paradas** (como Google Maps) y enviarla al coche?

Respuesta corta: **sí, parcialmente**, pero depende del canal y del nivel de integración. No hay un equivalente universal y fiable a “Google Maps → enviar ruta completa al Tesla” para cualquier usuario sin fricción.

---

## Escenarios de uso

| Escenario | Qué quiere el usuario |
|-----------|------------------------|
| A | Ver cargador en mapa → “Llévame ahí” (una parada) |
| B | Planificar viaje largo → ruta con paradas de carga elegidas por potencia |
| C | Enviar esa ruta al navegador del Tesla sin reescribir paradas a mano |

---

## Opción 1 — Enlaces externos (sin login, MVP)

Funciona para **cualquier usuario** desde la web, sin vincular cuenta Tesla.

### Una parada → Google Maps / Apple Maps

```
https://www.google.com/maps/dir/?api=1&destination=40.4168,-3.7038
https://maps.apple.com/?daddr=40.4168,-3.7038
```

En móvil abre la app nativa. En Tesla: el usuario puede abrir el enlace en el **navegador del coche** o prepararlo en el móvil antes de subir.

### Ruta con varias paradas → Google Maps (URL oficial)

```
https://www.google.com/maps/dir/?api=1
  &origin=Madrid
  &destination=Lisboa
  &travelmode=driving
  &waypoints=Salamanca|Coimbra|Ionity+Guadarrama
```

Documentación: [Google Maps URLs](https://developers.google.com/maps/documentation/urls/get-started)

| Ventaja | Limitación |
|---------|------------|
| Implementación trivial | Google **no modela batería** ni autonomía EV |
| Funciona en Android Auto / CarPlay (móvil) | Tesla **no usa** CarPlay/Android Auto para navegación principal |
| Varios waypoints | Orden geográfico, no optimización de carga por kW/SOC |
| Sin aprobación de Tesla | No activa **precondicionamiento** de batería Tesla |

**Conclusión MVP:** nuestra app puede planificar paradas (según filtros de potencia) y generar un botón **“Abrir ruta en Google Maps”**. Es el camino más rápido y universal.

---

## Opción 2 — Tesla Fleet API (integración profunda)

Tesla expone comandos oficiales en la [Fleet API](https://developer.tesla.com/docs/fleet-api/endpoints/vehicle-commands):

| Comando | Uso |
|---------|-----|
| `navigation_request` | Enviar dirección o texto (estilo “Compartir → Tesla”) |
| `navigation_gps_request` | Enviar coordenadas; `order` para varias paradas |
| `navigation_waypoints_request` | Lista de waypoints al navegador del coche |
| `navigation_sc_request` | Navegar a un Supercharger |

### Requisitos (no triviales)

- Cuenta de **desarrollador Tesla** aprobada.
- Usuario hace **OAuth** y autoriza la app.
- **Virtual Key** instalada en el vehículo (pareado).
- Comandos firmados con **Vehicle Command Protocol** (proxy/SDK).
- Vehículo despierto y con conectividad.

### Una parada → Tesla nativo

**Factible** para usuarios que vinculen su cuenta. Flujo:

1. Usuario elige electrolinera en nuestro mapa.
2. Pulsa “Enviar al Tesla”.
3. Backend llama `navigation_gps_request` con lat/lon.
4. Al entrar al coche, el destino ya está en el navegador Tesla.

Ventaja importante frente a Google Maps: el navegador Tesla puede **precondicionar la batería** si interpreta que el destino es un cargador (comportamiento deseable en viajes largos).

### Ruta completa con paradas → Tesla

Aquí está el **mayor desafío**:

| Canal | Estado real (2025–2026) |
|-------|-------------------------|
| App Tesla “Editar viaje → Enviar al coche” | Funciona en la app oficial; **no disponible** para terceros desde web sin API |
| `navigation_waypoints_request` | Documentado, pero **reportado como no funcional** vía Vehicle Command Protocol ([issue #334](https://github.com/teslamotors/vehicle-command/issues/334), [#188](https://github.com/teslamotors/vehicle-command/issues/188)) |
| ABRP “Send to Tesla” | Existe en apps premium; usuarios reportan **fallos frecuentes** |
| Foros Tesla / ABRP | Consenso: enviar **parada a parada**, no ruta entera |

Estrategia realista con Fleet API:

1. Planificar ruta completa **en nuestra app** (origen, destino, paradas filtradas por kW).
2. Enviar al Tesla **solo la siguiente parada** (`navigation_gps_request`).
3. Tras cargar, botón “Siguiente parada” o envío automático al desconectar (fase avanzada).

---

## Opción 3 — Compartir estilo “Google Maps → Tesla”

Flujo manual actual muy usado:

1. Buscar destino en Google Maps (móvil).
2. Compartir → app **Tesla**.
3. El coche recibe **un destino** (no siempre toda la ruta con waypoints).

Tesla documenta en el manual del vehículo:

- Compartir desde iOS/Android hacia la app Tesla.
- En la app Tesla: **Locations → Navigate → Edit Trip → Add Stop → Send to Car** (según región).

Nuestra web **no puede disparar el sheet nativo “Compartir”** del móvil de forma fiable en todos los navegadores. Alternativas:

- **Web Share API** (`navigator.share`) en móvil: abre el menú de compartir; el usuario elige Tesla.
- Enlace que abra Google Maps con la parada y el usuario comparte desde ahí.

---

## Opción 4 — Navegar dentro de nuestra web (navegador Tesla)

ABRP y otros usan el **navegador del coche** para mostrar el planificador.

| Ventaja | Limitación |
|---------|------------|
| No depende de API Tesla | Conexión intermitente en algunos modelos |
| Ruta completa visible en pantalla | No es turn-by-turn nativo del coche |
| Encaja con nuestro mapa + filtros kW | UX secundaria mientras conduces |

Útil como **complemento**, no como sustituto del nav Tesla.

---

## Comparativa de canales

| Canal | 1 parada | Ruta multi-parada | Precond. Tesla | Sin login | Esfuerzo |
|-------|----------|-------------------|----------------|-----------|----------|
| Enlace Google Maps | Sí | Sí (waypoints URL) | No | Sí | Bajo |
| Enlace Apple Maps | Sí | Parcial | No | Sí | Bajo |
| Web Share → Tesla app | Sí | No fiable | A veces | Sí | Bajo |
| Fleet API `navigation_gps_request` | Sí | Parada a parada | Sí | No | Alto |
| Fleet API `navigation_waypoints_request` | — | Teórico | Sí | No | Alto + **riesgo** |
| Navegación en web (Tesla browser) | N/A | Sí (visual) | No | Sí | Medio |

---

## Propuesta por fases para nuestro producto

### Fase A — Sin cuenta (todas las plataformas)

- Botón **“Navegar”** por cargador → Google Maps / Apple Maps.
- Planificador simple: origen + destino + paradas sugeridas (filtro ≥ X kW).
- Botón **“Abrir ruta completa en Google Maps”** con waypoints.
- Copiar coordenadas / QR para el móvil.

### Fase B — Cuenta Tesla opcional

- OAuth Tesla + envío **“Siguiente cargador al coche”**.
- Lista de paradas del viaje con estado (pendiente / actual / hecha).
- Recordatorio: precondicionamiento funciona mejor con nav Tesla nativo.

### Fase C — Planificador inteligente (#6053–#6055)

Ver [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md).

- Autonomía estimada (SOC manual, consumo por preset EV, factor terreno ajustable).
- Origen del plan vía **GPS del móvil** (sin telemetría del coche).
- Plan sobre ruta principal o **alternativa** (vías secundarias lejos de redes de operador); comparar 2–3 estrategias de carga.
- Selección de paradas según potencia mínima, viabilidad SOC y datos REVE dinámicos (#6050).
- Modo emergencia: cargador viable más cercano.
- Reoptimizar si una parada está ocupada (datos REVE).

**Fase 3 — Agente Dify (#6056–#6058):** ver [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md#fase-3--agente-plan-de-carga-dify-mini-pc). Workflow en mini PC; preferencias en lenguaje natural y explicaciones; cálculos delegados a la API.

### Fase D — UE

- Mismo exportador de rutas; fuentes NAP por país.

---

## Desafíos técnicos y de producto

### 1. Tesla no es un “destino de mapas” genérico

A diferencia de Android Auto, el Tesla prioriza su ecosistema. La integración profunda pasa por Fleet API o flujos manuales de compartir.

### 2. Precondicionamiento de batería

En viajes largos con Tesla, conviene que el **nav del coche** sepa que vas a un cargador. Enviar solo por Google Maps puede no dar la misma experiencia de carga rápida al llegar.

### 3. Waypoints múltiples en Tesla

Documentado ≠ operativo. No basar el MVP en `navigation_waypoints_request` hasta validarlo con vehículo real.

### 4. Planificación EV ≠ waypoints geográficos

Google Maps ordena paradas en el camino; **no** calcula:

- Si llegas con batería suficiente.
- Cuánto cargar en cada parada.
- Si un cargador de 50 kW es mejor que uno de 150 kW según tu coche.

Nuestro diferenciador: elegir paradas por **potencia y datos oficiales**, no solo por proximidad.

### 5. Permisos y privacidad (Fleet API)

- Tokens OAuth seguros.
- Consentimiento explícito del propietario.
- Política de datos clara (no vendemos ubicación).

### 6. Portugal + España en una ruta

Factible en export Google Maps y en planificador propio. Validar que waypoints largos no superen límites de URL (~2000 caracteres); si hace falta, acortar con acortador o POST + deep link propio.

---

## Decisión recomendada (borrador)

| Necesidad | Enfoque recomendado |
|-----------|---------------------|
| Mandar **una parada** al coche | MVP: Google Maps. v2: Fleet API si usuario conecta Tesla |
| **Ruta con paradas** que me interesen | Planificador propio + export Google Maps |
| Enviar ruta **al nav Tesla** completa | No prometer en v1; parada a parada vía Fleet API |
| Uso desde **Tesla browser** | Web responsive + plan de viaje en pantalla |

---

## GPS móvil y límites PWA (#6146, 2026-09-01)

Epic **#6131**. Documenta qué consigue nuestra **web móvil** con GPS y qué **no** puede igualar Android Auto, Google Maps nativo o el nav del Tesla.

### Rol de producto: copiloto EV, no navegador turn-by-turn

Electrolineras **no sustituye** la voz ni las maniobras de Google Maps, Waze ni del nav Tesla. Su trabajo en viaje activo es:

| Responsabilidad | Electrolineras | Google Maps / Waze | Nav Tesla |
|-----------------|----------------|--------------------|-----------|
| Plan de paradas DC (kW, SOC, REVE) | ✅ | ❌ | ❌ |
| Ruta completa con waypoints geográficos | Export URL | ✅ turn-by-turn | Parcial (waypoints a menudo se pierden al compartir) |
| Siguiente parada al coche | Web Share / enlace destino | Compartir → Tesla | ✅ destino nativo |
| Seguimiento posición para replan | ✅ GPS móvil o TeslaMate | ✅ | ❌ (no expone posición a la web) |
| Instrucciones «gira a la derecha» | ❌ | ✅ | ✅ |
| Precondicionamiento batería al SC | ❌ | A veces vía share | ✅ si el destino es cargador |

**Mensaje honesto en UI (ya en producto):** «La navegación turn-by-turn la hace Google Maps o el Tesla; aquí gestionamos las paradas de carga.»

### Qué hace hoy la web en prod (`feature/viaje-activo-6131`)

Implementado en código (sin ser app nativa):

| Función | Comportamiento |
|---------|----------------|
| Viaje activo | `localStorage` 48 h, vías usuario, progreso parada N de M (#6135–#6137) |
| GPS móvil | `watchPosition` al restaurar viaje; toggle «Usar GPS del móvil» (#6144) |
| Mapa | Marcador de posición + «Centrar en mí» independiente de `autoFollow` (#6145) |
| Replan | Debounce (>2 km / >5 min / ΔSOC ≥3 pp), desvío de ruta, divergencia consumo ±15 % (#6138–#6139) |
| Handoff | «Abrir ruta en Google Maps» (waypoints DC); «Parada N → Tesla» vía Web Share (#6137) |
| Origen coche | TeslaMate en zona privada: replan desde SOC/posición del vehículo |

Todo el GPS web usa la **Geolocation API del navegador** (`navigator.geolocation.watchPosition`). No hay Service Worker de posición ni `navigator.geolocation` en segundo plano real.

### GPS: primer plano vs segundo plano

| Situación | Chrome Android (pestaña abierta) | Chrome Android (pestaña en segundo plano) | iOS Safari | Tesla browser |
|-----------|----------------------------------|-------------------------------------------|------------|---------------|
| Pestaña visible, pantalla encendida | ✅ Actualización continua (~15 s `maximumAge`) | ⚠️ Throttle agresivo del SO; updates irregulares | ⚠️ Similar | ⚠️ Conexión + GPS variables |
| Pantalla apagada / bloqueada | ❌ o muy espaciado | ❌ | ❌ | N/A (pantalla del coche) |
| Pestaña cerrada | ❌ | ❌ | ❌ | ❌ |
| Permiso denegado | Mensaje en UI; origen manual / simulación | — | — | — |

**Conclusión:** el replan «en marcha» y el mapa centrado en el usuario asumen **pestaña en primer plano** (o segundo plano breve en Android). No es un tracker de flota 24/7. Para conducir horas con la app cerrada haría falta **app nativa** con foreground service (ver más abajo).

### Navegación turn-by-turn: quién hace qué

```
┌─────────────────┐     plan EV + replan      ┌──────────────────┐
│  Electrolineras │ ────────────────────────► │  Paradas DC, SOC │
│  (copiloto)     │     GPS / TeslaMate       │  progreso N de M │
└────────┬────────┘                           └──────────────────┘
         │ export ruta / share parada
         ▼
┌─────────────────┐     turn-by-turn          ┌──────────────────┐
│  Google Maps    │ ────────────────────────► │  Maniobras, ETA  │
│  (móvil)        │     Android Auto opcional │  tráfico en ruta │
└────────┬────────┘                           └──────────────────┘
         │ Compartir → Tesla (manual)
         ▼
┌─────────────────┐     nav en pantalla       ┌──────────────────┐
│  Nav Tesla      │ ────────────────────────► │  1 destino/parada│
│  (coche)        │     precond. si SC        │  (no ruta entera)│
└─────────────────┘                           └──────────────────┘
```

- **Android Auto:** proyecta **Google Maps** (u otra app aprobada), no nuestra web. No hay canal para embeber `electro.jualas.es` como app de navegación en el salpicadero sin wrapper nativo certificado por Google.
- **Electrolineras en el móvil montado:** útil con pestaña abierta (o en split screen) para ver siguiente parada, recalcular y reenviar al Tesla; Maps lleva la voz.

### Flujo híbrido recomendado (viaje largo EV)

Orden probado en producto y alineado con limitaciones Tesla:

1. **Planificar** en Electrolineras (origen GPS o coche, destino, filtro kW, preferencia de ruta).
2. **Abrir ruta en Google Maps** (todos los waypoints DC) → iniciar navegación en el móvil o Android Auto.
3. Activar **viaje activo** + **GPS del móvil** (o TeslaMate si conduces con datos del coche).
4. En marcha: Electrolineras **replanifica paradas** si te desvías, cambia el SOC o el consumo; Maps sigue la ruta que el usuario quiera recalcular allí aparte.
5. Antes de cada parada DC: **«Parada N → Tesla»** (Web Share) o abrir destino en Maps y compartir al coche.
6. Tras cargar: **Marcar parada completada** → opcional **Recalcular desde aquí** → enviar parada N+1 al Tesla.

No intentar que el usuario use solo el navegador Tesla para todo el viaje: pantalla pequeña, red irregular y sin turn-by-turn de nuestra app.

### Matriz de capacidades (web vs nativo)

| Capacidad | Web móvil (PWA-capable) | Android Auto + Maps | App Android nativa (hipotética) | Nav Tesla |
|-----------|-------------------------|---------------------|----------------------------------|-----------|
| Plan EV con paradas DC | ✅ | ❌ | ✅ | ❌ |
| GPS con pestaña abierta | ✅ | ✅ (Maps) | ✅ | ❌ |
| GPS con app en background | ❌ | ✅ (Maps) | ✅ (foreground service) | — |
| Replan automático por posición/SOC | ✅* | ❌ | ✅* | ❌ |
| Turn-by-turn + voz | ❌ | ✅ | ✅ (si integramos SDK) | ✅ |
| Enviar ruta completa al Tesla | ❌ fiable | ❌ | ⚠️ share intent / Fleet API | — |
| Enviar 1 parada al Tesla | Web Share | Manual | Intent `com.teslamotors.tesla` + share | ✅ |
| Precondicionamiento SC | ❌ | A veces | Solo vía Tesla | ✅ |
| Instalable en home (PWA) | ⚠️ sin push GPS bg | N/A | ✅ Play Store | N/A |
| Uso en browser Tesla | ✅ lectura/plan | N/A | N/A | ✅ limitado |

\*Con throttle (#6138): no en cada tick GPS; umbrales 2 km / 5 min / 3 pp SOC.

### Tesla browser vs Chrome Android

| Aspecto | Chrome Android | Navegador Tesla |
|---------|----------------|-----------------|
| Geolocalización | Permiso estándar; precisión buena con GPS del móvil | A menudo posición del **vehículo** o imprecisa; no sustituye TeslaMate |
| Web Share API | ✅ menú compartir → Tesla | ❌ o muy limitado |
| Abrir Google Maps | ✅ app nativa | Enlace web; compartir al nav es más incómodo |
| UI viaje activo | Barra En marcha, mapa, GPS | Botones deben ser grandes; probar G5 (#6132) |
| Replan en conducción | Con pestaña activa | No recomendado como canal principal |
| TeslaMate / Asistente | ✅ zona privada | Depende de sesión; mismo backend |

**Recomendación:** planificar y seguir el viaje en **móvil Android**; usar el **Tesla browser** para consultar plan o reenviar una parada si el móvil no está a mano, no como único dispositivo de copiloto.

### Cuándo tendría sentido una app Android nativa (fuera de alcance actual)

No implementada. Criterios para valorarla en el futuro:

| Necesidad de negocio | Pieza nativa |
|----------------------|--------------|
| Replan con pantalla apagada o Maps en primer plano | `ForegroundService` + `FusedLocationProvider` |
| Widget «siguiente parada / SOC» | App widget + notificación persistente |
| Share directo a Tesla sin sheet del navegador | `Intent` explícito hacia app Tesla (frágil, sin API pública estable) |
| Android Auto como “destino” de la app | Proyecto **Android for Cars** (plantilla navegación); esfuerzo alto, distinto de PWA |
| Push «te desviaste, recalcula» | FCM + última posición en servidor (implica backend de tracking) |

Hasta entonces, la **PWA / web responsive** + flujo híbrido Maps/Tesla es el equilibrio correcto coste/beneficio (#6131).

### Relación con otras tareas

| Tarea | Enlace |
|-------|--------|
| Spike Maps → Tesla en dispositivo | ~~#6133~~ **descartado** (ver abajo) |
| GPS arranque automático | #6144 ✅ |
| Mapa sigue posición | #6145 ✅ |
| Replan + consumo | #6138 ✅ |
| Evaluación manual E/G | #6132 |

---

## Decisión de producto — spike #6133 descartado (2026-09-01)

**No se ejecutará** la validación en dispositivo real Android (Google Maps → Compartir → Tesla) ni intentos de atajo nativo hacia la app Tesla.

### Motivos

1. **Fuera del alcance web:** no hay API estable para que `electro.jualas.es` envíe rutas o waypoints al nav Tesla; el único canal fiable desde navegador es **Web Share** (parada a parada) o que el usuario comparta manualmente desde Google Maps.
2. **Hipótesis ya documentada:** la comunidad Tesla y nuestra propia arquitectura asumen que el coche recibe **un destino** (coords), no la ruta multi-waypoint de GMaps; `navigation_waypoints_request` (Fleet API) sigue siendo poco fiable.
3. **Coste/beneficio:** un spike en coche real no desbloquea implementación en código; para mejorar el handoff haría falta app Android nativa o Fleet API por usuario — esfuerzo muy superior al MVP.
4. **Flujo acordado suficiente:** plan EV en Electrolineras → ruta completa en **Google Maps** → **parada N → Tesla** vía Web Share cuando toque; copy honesto ya en UI (#6137).

### Qué queda como criterio operativo (sin spike)

| ID | Tratamiento |
|----|-------------|
| G2 | **Asumido:** GMaps → Tesla pierde waypoints; no prometer ruta completa al coche |
| G3 | **Cubierto por producto:** botón «Parada N → Tesla» + Web Share; éxito depende del SO/usuario |
| G4 | **Flujo manual** documentado en [flujo híbrido](#flujo-híbrido-recomendado-viaje-largo-ev) |
| G5 | Prueba ad hoc si se usa browser Tesla; no bloquea cierre epic |

Si en el futuro hubiera demanda fuerte, la vía sería **Fleet API** (#6133 no la sustituye) o app nativa, no más spikes de share sheet.

---

## Criterios de aceptación (cuando implementemos)

- [x] Desde un viaje planificado: URL con waypoints de **cargadores** (no solo destino) abre ruta en Google Maps.
- [x] ~~Probar en dispositivo G2~~ → **descartado #6133**; asumimos solo destino final al compartir GMaps→Tesla (documentado).
- [ ] (v2) Usuario Tesla vinculado: “Enviar al coche” llega en < 30 s con coche online (Fleet API).
- [x] Documentar en UI que la ruta completa al Tesla puede requerir enviar paradas una a una.
- [ ] Probar en navegador Tesla: mapa usable y botones legibles (opcional, no bloquea epic).

---

## Evaluación viaje activo + handoff (#6132, 2026-08-26)

Rama: `feature/viaje-activo-6131`. Epic: TaskBoard **#6131**.

### Verificado en API / código (sin dispositivo)

| ID | Resultado | Notas |
|----|-----------|-------|
| G1 | ✅ OK | Cartagena→Irun: 3 waypoints DC; URL GMaps 186 chars (&lt;2000). Ejemplo: origen + 3 paradas + destino. |
| E2 | ✅ OK (#6135) | Persistencia `localStorage` + TTL 48 h; migra desde `sessionStorage`. |
| E3 | ✅ OK (#6135, #6138) | Plan y Asistente restauran viaje; `ReplanOnRouteBar` en ambos paneles. |
| E5 | ✅ OK (#6136) | `completedStopOrders`, «Parada N de M», marcar completada, share N+1. |
| next_stop | ✅ OK (#6136–#6137) | `routeExportSpecForNextStop` + progreso `currentLegIndex`. |
| Vías A→…→A | ✅ (#6135) | `ActiveTripState.waypoints[]` + restore en Plan/Asistente. |
| GPS / mapa | ✅ (#6144–#6145) | Toggle GPS, marcador en mapa, «Centrar en mí». Ver sección [GPS móvil y límites PWA](#gps-móvil-y-límites-pwa-6146-2026-09-01). |
| Replan | ✅ (#6138–#6139) | Debounce, desvío, divergencia consumo, `replanCount`. |

### Pendiente en dispositivo real (Android + Tesla)

> **#6133 descartado** (2026-09-01): no se hará spike formal GMaps→Tesla. Los ítems G2/G3 se tratan como asunciones de producto; ver [decisión #6133](#decisión-de-producto--spike-6133-descartado-2026-09-01).

| ID | Qué probar | Criterio |
|----|------------|----------|
| E1 | Plan loop Cartagena→Tres Cantos→Cuenca→A, F5 | ¿Restaura destino? ¿Pierde vías? (smoke manual opcional) |
| G2 | GMaps con waypoints → Compartir → Tesla | **Asumido:** solo destino final (#6133 descartado) |
| G3 | «Parada N → Tesla» (Web Share) | Cubierto por UI; sin SLA de &lt;30 s |
| G4 | Tras carga, parada N+1 | Flujo manual documentado |
| G5 | Browser Tesla | Opcional |

### Fallos priorizados → tareas

1. ~~**P1** Persistencia + vías → #6135~~ ✅  
2. ~~**P1** Progreso + siguiente parada N → #6136~~ ✅  
3. ~~**P1** Copy dual Maps vs Tesla → #6137~~ ✅  
4. ~~**P1** Spikes G2/G3 en dispositivo → #6133~~ **descartado** (#6134 sin ejecutar)  
5. ~~**P2** Replan + Asistente → #6138~~ ✅  
6. ~~**P1 #6140** UI tiempos Directa/Rápida~~ ✅ (rama viaje activo)  
7. ~~**P2** Límites PWA/GPS → #6146~~ ✅ (este documento)  
8. **P2** Mapa GPS en viaje → ~~#6145~~ ✅
