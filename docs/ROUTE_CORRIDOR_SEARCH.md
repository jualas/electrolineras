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

## MVP acotado (primera entrega útil)

1. Formulario: origen, destino, **min 100 kW**.
2. Ruta + filtro corredor 10 km.
3. Excluir estaciones **detrás** del usuario en la ruta.
4. Top 10 por menor desvío.
5. Botón abrir en Google Maps.

**No incluir en MVP:** estimación SOC, tiempo de carga, ocupación REVE.

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
