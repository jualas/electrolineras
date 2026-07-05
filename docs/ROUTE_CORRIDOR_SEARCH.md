# Búsqueda de cargadores en ruta (corredor)

Caso de uso principal derivado de experiencia real: evitar paradas mal elegidas por el navegador del Tesla.

## Caso real (Granada → Cartagena, 44 % SOC)

| Paso | Qué hizo el Tesla | Por qué es mala opción |
|------|-------------------|------------------------|
| 1 | Enviar al **Supercharger de Granada** (afueras, hacia Motril) | ~20 min de desvío total antes de retomar ruta a Cartagena |
| 2 | En carretera, indicar parada en **Cullar** | Salir, **cambio de sentido**, volver a incorporarse en la dirección correcta |

Lo que el usuario necesitaba: **búsqueda rápida de cargadores ≥ 100 kW en la carretera hacia Cartagena**, sin desvíos absurdos ni paradas en sentido contrario.

---

## Problema de fondo

El navegador Tesla optimiza para **llegar al destino final** con SOC mínimo, no para:

- Minimizar **tiempo total** (desvío + carga + retorno).
- Evitar paradas que exijan **inversión de marcha** o salidas en sentido opuesto.
- Mostrar alternativas **en el corredor de la autovía** para que el usuario decida.

Con 44 % desde Granada hacia Cartagena, una parada en Granada SC puede ser “válida” para el algoritmo pero **mala en la práctica** si ya estás orientado hacia el destino.

---

## Funcionalidad objetivo

### “Cargadores en mi ruta” (≥ X kW)

Flujo en **web móvil** o **app Android** (mismo backend):

1. Usuario indica **destino** (Cartagena) — origen = posición actual o ciudad (Granada).
2. Elige **potencia mínima** (preset: Lento / Viaje ≥100 kW / Personalizado).
3. Opcional: filtros de **acceso** (excluir centros comerciales, solo ad-hoc).
4. La app calcula la **ruta por carretera** y muestra solo cargadores que cumplan:
   - Potencia ≥ umbral.
   - Dentro de un **corredor** alrededor de la ruta (p. ej. 5–15 km).
   - Preferiblemente **en sentido de marcha**, sin obligar a cambio de sentido.

4. Lista / mapa ordenado por criterio útil:
   - **Menor desvío** desde la ruta (km o minutos extra).
   - Distancia desde posición actual.
   - Potencia (mayor primero, opcional).

5. Un toque: **“Navegar aquí”** (Google Maps / enviar al Tesla en fase 2).

### Diferencia con “mapa de todos los cargadores”

| Mapa general | En ruta (esta feature) |
|--------------|-------------------------|
| Miles de puntos en pantalla | Solo los del **corredor** hacia destino |
| Sin contexto de viaje | Contexto: Granada → Cartagena, 44 % |
| Filtro kW solo | kW + **alineación con ruta** + anti-U-turn |

---

## Reglas de negocio (borrador)

### Corredor de ruta

- Obtener polilínea de la ruta (OSRM, Valhalla, GraphHopper o Directions API).
- Incluir estación si la distancia perpendicular a la ruta ≤ **R km** (R configurable, default 10 km en autopista, 5 km en convencional).

### Sentido de marcha (anti-Cullar)

Evitar cargadores que impliquen volver atrás:

1. Proyectar estación sobre la polilínea → obtener **km acumulado** en ruta (`s_station`).
2. Posición actual → `s_now`.
3. Descartar o penalizar si `s_station < s_now - margen` (ya te has pasado o está **detrás** en la ruta).
4. Opcional: comparar **rumbo** del tramo de ruta en `s_station` con vector origen→estación; penalizar si ángulo > 90° (parada al otro lado / retorno).

### Desvío mínimo

Para cada candidato:

- `desvio_km = dist(ruta, estación)` (perpendicular) + penalización por salida en sentido contrario.
- Ordenar por `desvio_km` ascendente, luego por `-power_kw`.

### Presets de potencia (UI)

| Etiqueta | kW | Uso |
|----------|-----|-----|
| Lento (AC) | 3 – 22 | Ciudad, pernocta |
| Semi-rápido | 22 – 43 | Urbano intermedio |
| Rápido (DC) | 43 – 100 | Parada media |
| Viaje | ≥ 100 | Autopista (default en ruta) |
| Ultrarrápido | ≥ 150 | HPC |
| **Personalizado** | min – max | Slider libre |

Detalle completo: [`FILTERS.md`](FILTERS.md).

---

## Wireflow (móvil / web)

```
[Destino: Cartagena]  [≥ 100 kW ▼]  [Buscar en ruta]
        │
        ▼
Mapa: ruta en azul + marcadores solo en corredor
Lista:
  1. Ionity Guadix — 350 kW — +4 min desvío — 142 km
  2. …
        │
        ▼
[Navegar]  [Añadir a mi viaje]
```

Modo **rápido**: una pantalla, sin login, origen = GPS.

---

## Datos necesarios

| Dato | Fuente |
|------|--------|
| Ubicación estaciones + kW | NAP España DATEX II, MOBI.E PT |
| Geometría ruta | OSRM (gratis self-host) / Valhalla / Google Directions* |
| Posición usuario | GPS navegador / app Android |

\* Google Directions tiene coste; OSRM/Valhalla preferible para MVP open source.

---

## Tipos de ruta OSRM (planificador y «En ruta»)

La API pide a OSRM una polilínea según **`route_preference`**. Esa geometría define el **corredor** donde se buscan cargadores. Tres modos en UI y en `GET /api/v1/stations/along-route` / `charging-plan`:

| Preferencia | Objetivo | Cómo se elige la ruta activa |
|-------------|----------|------------------------------|
| `shortest` | Menos km en carretera | Entre alternativas OSRM, minimiza distancia + penalización por desvío vs línea recta (`OSRM_SHORTEST_DIRECTNESS_PENALTY`, default 0.35). |
| `fastest` | Menor tiempo (autovía si compensa) | Ver **desempate fastest** abajo. |
| `conventional` | Nacionales/locales, sin autovía | Excluye `motorway` (y `toll` si «evitar peajes»). Con OSRM propio multi-perfil usa perfil `conventional` dedicado; con OSRM público puede ser **aproximada** (aviso en respuesta). |

Peajes: `avoid_highways=true` añade `exclude=toll` (autovías libres permitidas). Si el servidor no soporta `exclude`, se reintenta sin filtro y se avisa al usuario.

### Desempate «ruta más rápida» (`select_fastest_route_payload`)

OSRM devuelve hasta **varias alternativas** cuando `OSRM_FASTEST_REQUEST_ALTERNATIVES=true` (default). No basta con `min(duration)`: en corredores con tiempos muy parecidos, la alternativa **más larga pero con mayor velocidad media** suele ser la que un conductor (o Google Maps) elegiría por autopista.

Algoritmo (`src/api/routing/osrm.py`):

1. `min_duration` = menor `duration` entre alternativas.
2. **Ventana de tolerancia:** candidatas con `duration ≤ min_duration × (1 + T)`, donde `T = OSRM_FASTEST_ALTERNATIVE_TOLERANCE` (default **0.05** = 5 %).
3. Entre candidatas, gana la de **mayor velocidad media** `distance / duration`.

**Caso de referencia — Cartagena → Zaragoza:** OSRM a veces marca ~3 min menos por interior (N-330 / Teruel), pero la ruta por **A-7 + A-23 Mudéjar** (vía Valencia) queda dentro del 5 % de tiempo y tiene mejor velocidad media; el motor elige la segunda. Tests: `tests/test_osrm_route.py` (`test_select_fastest_route_prefers_similar_time_higher_avg_speed`).

**Limitación:** OSRM **no tiene tráfico en tiempo real** (#6067). La heurística aproxima «ruta rápida habitual», no congestión del momento.

### Variables relacionadas (`.env`)

| Variable | Default | Efecto |
|----------|---------|--------|
| `OSRM_FASTEST_REQUEST_ALTERNATIVES` | `true` | Pide `alternatives=true` al calcular la variante fastest. |
| `OSRM_FASTEST_ALTERNATIVE_TOLERANCE` | `0.05` | Ventana ±5 % sobre el mínimo tiempo para desempate por velocidad media (#6069). |
| `OSRM_SHORTEST_DIRECTNESS_PENALTY` | `0.35` | Penaliza rutas «circulares» en modo shortest. |
| `OSRM_USE_MULTI_PROFILE` | `true` en prod | Tres perfiles OSRM (`fastest` / `shortest` / `conventional`); convencionales con `exclude=motorway` en perfil propio. |
| `OSRM_PROFILE_CONVENTIONAL` | `conventional` | Nombre del perfil Lua en OSRM self-hosted (`docker/osrm/`). |

En la respuesta JSON, `route_variants_approximate=true` indica que alguna variante (típicamente convencional en OSRM público) no aplicó exclusiones estrictas. La UI muestra polilíneas de referencia **directa / rápida / convencional** (#6066).

Implementación y tests: `src/api/routing/osrm.py`, `tests/test_osrm_route.py`.

---

## MVP acotado (primera entrega útil)

1. Formulario: origen, destino, **min 100 kW**.
2. Ruta + filtro corredor 10 km.
3. Excluir estaciones **detrás** del usuario en la ruta.
4. Top 10 por menor desvío.
5. Botón abrir en Google Maps.

**No incluir en MVP Fase 1:** estimación SOC, tiempo de carga, ocupación REVE.

**Fase 2 (#6053–#6055):** plan de carga con SOC, consumo por modelo, viabilidad en corredor (principal o alternativo) y comparación de opciones — ver [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md).

---

## App Android vs web móvil

| | Web móvil (PWA) | App Android |
|--|-----------------|-------------|
| Tiempo desarrollo | Menor | Mayor |
| GPS en segundo plano | Limitado | Mejor |
| “Compartir → Tesla” | Web Share API | Intent nativo |
| Instalación | Ninguna | Play Store |

**Recomendación:** empezar con **web móvil responsive** (misma API); Android nativo solo si hace falta widget o integración profunda Tesla.

---

## Criterios de aceptación

- [ ] Granada → Cartagena, min 100 kW: **no** sugerir SC Granada si hay opciones más adelante en corredor con menor desvío (validar con datos reales).
- [ ] Ningún resultado top-5 exige **retroceder** más de X km en la ruta.
- [ ] Búsqueda usable en < 3 toques desde abrir la app.
- [ ] Tiempo respuesta < 5 s en 4G (ruta + filtro sobre dataset España).

---

## Relación con otros documentos

- Fuentes de datos: [`DATA_SOURCES.md`](DATA_SOURCES.md)
- Envío al coche: [`NAVIGATION.md`](NAVIGATION.md)
- Visión general: [`VISION.md`](VISION.md)
