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

## Criterios de aceptación (cuando implementemos)

- [ ] Desde un cargador: “Abrir en Google Maps” funciona en móvil y escritorio.
- [ ] Desde un viaje planificado: URL con ≥ 3 waypoints abre ruta correcta en Google Maps.
- [ ] (v2) Usuario Tesla vinculado: “Enviar al coche” llega en < 30 s con coche online.
- [ ] (v2) Documentar en UI que la ruta completa al Tesla puede requerir enviar paradas una a una.
- [ ] Probar en navegador Tesla: mapa usable y botones legibles.

---

## Evaluación viaje activo + handoff (#6132, 2026-08-26)

Rama: `feature/viaje-activo-6131`. Epic: TaskBoard **#6131**.

### Verificado en API / código (sin dispositivo)

| ID | Resultado | Notas |
|----|-----------|-------|
| G1 | ✅ OK | Cartagena→Irun: 3 waypoints DC; URL GMaps 186 chars (&lt;2000). Ejemplo: origen + 3 paradas + destino. |
| E2 | ❌ FAIL esperado | `ActiveTrip` solo en `sessionStorage` → se pierde al cerrar pestaña. |
| E3 | ❌ FAIL esperado | `AssistantPanel` no usa `useActiveTrip` ni `ReplanOnRouteBar`. |
| E5 | ❌ N/A | No hay progreso de paradas (`completedStopOrders`). |
| next_stop | ⚠️ Parcial | Botón «1.ª parada → Tesla» existe; no avanza a N+1 tras completar. |
| Vías A→…→A | ❌ Hueco | `ActiveTripState` guarda solo destino final, no waypoints de itinerario. |

### Pendiente en dispositivo real (Android + Tesla)

| ID | Qué probar | Criterio |
|----|------------|----------|
| E1 | Plan loop Cartagena→Tres Cantos→Cuenca→A, F5 | ¿Restaura destino? ¿Pierde vías? |
| G2 | GMaps con waypoints → Compartir → Tesla | ¿Solo destino final o también waypoints? |
| G3 | En web móvil: «1.ª parada → Tesla» | ¿Llega al coche &lt;30 s? |
| G4 | Tras “carga”, enviar parada #2 manualmente | Flujo usable parada a parada |
| G5 | Abrir electro.jualas.es en browser Tesla | Botones export / En marcha legibles |

### Fallos priorizados → tareas

1. **P1** Persistencia + vías → #6135  
2. **P1** Progreso + siguiente parada N → #6136  
3. **P1** Copy dual Maps vs Tesla → #6137  
4. **P1** Spikes G2/G3 en dispositivo → #6133, #6134  
5. **P2** Replan + Asistente → #6138
