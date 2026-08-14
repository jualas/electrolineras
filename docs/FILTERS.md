# Filtros de potencia y acceso

Requisitos de búsqueda flexibles según contexto (viaje vs ciudad) y tipo de acceso al cargador.

---

## 1. Potencia de carga — siempre elegible

La potencia **no puede ser fija** (p. ej. solo ≥ 100 kW). El usuario elige según situación:

| Contexto | Necesidad típica | Preset sugerido |
|----------|------------------|-----------------|
| **Autopista / viaje** | Parada corta, máximo kW | ≥ 100 kW o ≥ 150 kW |
| **Ciudad / pernocta** | Carga lenta mientras cenas o duermes | 7–22 kW (AC) |
| **Parada intermedia urbana** | Semi-rápido | 22–43 kW |
| **Explorar todo** | Sin filtro de potencia | Cualquiera |

### UI propuesta

**Presets rápidos** (chips seleccionables):

| Etiqueta | Rango kW | Modo DATEX (referencia) |
|--------|----------|-------------------------|
| Lento (AC) | 3 – 22 | mode2AC1p, mode3AC3p bajo |
| Semi-rápido | 22 – 43 | mode3AC3p alto |
| Rápido (DC) | 43 – 100 | mode4DC |
| Viaje | ≥ 100 | mode4DC |
| Ultrarrápido | ≥ 150 | mode4DC |
| **Personalizado** | min – max slider | — |

- Preset **Personalizado**: slider doble (mín / máx) o inputs numéricos.
- Mostrar siempre el rango activo: *«Mostrando 22–43 kW»*.
- En **búsqueda en ruta**, recordar el último preset usado; botón *«Modo ciudad»* / *«Modo viaje»* que cambia preset + radio de búsqueda.

### Perfiles de contexto (atajo UX)

| Perfil | Potencia default | Búsqueda |
|--------|------------------|----------|
| **En viaje** | ≥ 100 kW | En corredor de ruta |
| **En ciudad** | 3 – 22 kW (ajustable) | Cerca de mí / dirección / zona mapa — **radio default 1 km** |
| **Todo** | Sin límite | Mapa general |

Un mismo usuario puede pasar de *viaje* a *ciudad* en el mismo día; el cambio de perfil debe ser **un toque**.

---

## 2. Modo ciudad — potencia **y** ubicación (ambos elegibles)

En ciudad la búsqueda debe combinar **dos ejes independientes** que el usuario configura antes de buscar:

1. **Potencia** — presets o rango personalizado (sección 1).
2. **Ubicación** — dónde buscar alrededor.

Los filtros de **acceso** (sección 3) son opcionales y se aplican encima.

### Regla de combinación

Todos los filtros activos se aplican en conjunto (**AND**):

```
Resultado = cargadores WHERE
  potencia ∈ [min_kw, max_kw]
  AND distancia/área cumple ubicación elegida
  AND acceso cumple toggles (si activos)
```

### Opciones de ubicación

| Modo | Descripción | Uso típico |
|------|-------------|------------|
| **Cerca de mí** | GPS actual + radio | Estoy aparcado / de paseo |
| **Buscar dirección o lugar** | Texto → geocodificar → radio | Hotel, restaurante, «Plaza Nueva, Granada» |
| **Zona del mapa** | Rectángulo visible o pin + radio | «Aquí donde estoy mirando» |
| **Pin en mapa** | Toque largo / botón «Marcar punto» + radio | Sitio concreto sin dirección postal |

### Radio de búsqueda (ciudad)

Presets seleccionables (slider o chips). **Default en modo ciudad: 1 km.**

| Radio | Uso |
|-------|-----|
| 500 m | Mismo barrio, a pie |
| **1 km** | **Default ciudad** — paseo corto |
| 2 km | Urbano |
| 5 km | Ciudad amplia |
| Personalizado | 200 m – 10 km |

Orden de resultados por defecto: **distancia ascendente** a la ubicación de referencia.

### Wireflow (pantalla móvil)

```
┌──────────────────────────────────────┐
│  EN CIUDAD                           │
├──────────────────────────────────────┤
│  Potencia                            │
│  [Lento] [Semi] [Rápido] [Custom ▼]  │
│  Mostrando: 3 – 22 kW                │
├──────────────────────────────────────┤
│  Ubicación                           │
│  ○ Cerca de mí                       │
│  ● Buscar dirección  [Hotel X____]   │
│  ○ Zona del mapa                     │
│  ○ Marcar en mapa                    │
│  Radio: [500m] [1km] [2km] [5km]     │
├──────────────────────────────────────┤
│  Acceso (opcional)            [▼]    │
│  ☑ Excluir centros comerciales       │
│  ☑ Solo acceso abierto               │
├──────────────────────────────────────┤
│         [ Buscar cargadores ]        │
└──────────────────────────────────────┘
         ↓
  Mapa + lista ordenada por distancia
```

### Interacción mapa ↔ filtros

- Mover el mapa con modo **«Zona del mapa»** activo → el bbox visible define el área de búsqueda.
- Pulsar **Buscar** recalcula resultados; no hace falta recargar la página entera.
- Cambiar solo potencia o solo ubicación → el usuario vuelve a pulsar Buscar (o auto-buscar con debounce, decisión UX).

### API (borrador)

```
GET /api/v1/stations/search
  ?min_kw=3&max_kw=22
  &lat=37.1773&lon=-3.5986&radius_m=2000          # cerca de mí / dirección / pin

GET /api/v1/stations/search
  ?min_kw=7&max_kw=43
  &bbox=west,south,east,north                       # zona del mapa

GET /api/v1/stations/search
  ?min_kw=3&max_kw=22
  &q=Plaza+Nueva+Granada&radius_m=1000              # geocoding servidor-side

  &access=public_open                               # opcional
  &exclude=commercial_parking                       # opcional
  &sort=distance                                    # default ciudad
```

### Ejemplos

**Hotel en Granada, carga nocturna lenta**

- Potencia: 3 – 22 kW  
- Ubicación: dirección del hotel, radio 500 m  
- Acceso: excluir CC  

**Centro histórico, semi-rápido mientras comes**

- Potencia: 22 – 43 kW  
- Ubicación: cerca de mí, 1 km  
- Acceso: solo abierto  

**Planificar antes de llegar**

- Potencia: personalizado 7 – 11 kW  
- Ubicación: pin en mapa donde aparcaréis, 300 m  

### Diferencia con modo viaje

| | Modo ciudad | Modo viaje |
|--|-------------|------------|
| Eje espacial | Punto + radio / bbox | Corredor de ruta origen→destino |
| Orden | Distancia al punto | Desvío mínimo en ruta |
| Potencia default | 3 – 22 kW | ≥ 100 kW |

---

## 3. Acceso público — evitar parkings problemáticos

### Problema del usuario

En ciudad interesa un cargador **lento**, pero no uno que implique:

- Parking de **centro comercial** con ticket de acceso o cobro por estacionar.
- Plazas con **límite de tiempo** de carga o de estancia.
- Acceso restringido a clientes / empleados del recinto.

### Qué dice la normativa

- El **NAP español** recoge puntos que los operadores remiten al MITECO; la ley exige publicar información de recarga **de acceso público**.
- **AFIR (UE):** distingue accesible al público vs restringido; los restringidos no deben figurar como públicos.
- En la práctica, un cargador en un CC puede ser «público» legalmente pero **malo en UX** (parking de pago, barreras, límite 2 h).

### Campos disponibles en NAP España (DATEX II)

Analizado el feed `electrolineras.xml`:

| Campo | Valores observados | Uso para filtros |
|-------|-------------------|------------------|
| `egi:typeOfSite` | `openSpace`, `onstreet`, `inBuilding`, `other` | Heurística de entorno |
| `fac:associatedFacility/fac:type` | `parkingSite`, `publicTransportHub` | Señal de parking asociado |
| `fac:supplementalFacility` | `foodShopping`, `petrolStation`, … | Señal de CC / gasolinera |
| `fac:operatingHours` | 24/7, horarios | Disponibilidad |
| `egi:authenticationAndIdentificationMethods` | apps, rfid, creditCard, nfc… | Pago ad-hoc vs solo app |
| `egi:chargingMode` + `maxPowerAtSocket` | mode2/3/4, vatios | Potencia real |

**Limitación:** el XML español **no trae siempre** explícitamente «parking de pago» o «máximo 2 h». Parte del filtro será **heurístico** + etiquetas honestas en UI (*«posible parking de pago»*).

### Clasificación interna (borrador)

Cada estación recibe `access_class`:

| Clase | Criterio (prioridad) | UI |
|-------|----------------------|-----|
| `public_open` | `onstreet` o `openSpace`, sin `parkingSite`+`foodShopping` | ✅ Acceso abierto |
| `public_parking` | `parkingSite` sin señales de CC | ⚠ Parking público |
| `commercial_parking` | `parkingSite` + `foodShopping` / `shopping` | ⚠ Posible CC — parking de pago |
| `indoor` | `inBuilding` | ⚠ Interior — ver acceso |
| `unknown` | Datos insuficientes | ❓ Sin clasificar |

### Filtros de acceso (UI)

Checkboxes / toggles:

| Filtro | Default viaje | Default ciudad | Efecto |
|--------|---------------|----------------|--------|
| **Solo acceso público abierto** | Off | Off | Compatibilidad API: no oculta inventario oficial NAP/REVE (tiendas/CC incluidas) |
| **Excluir centros comerciales** | Off | Off | Oculta todo `commercial_parking` (también HPC en super/CC) |
| **Excluir parking con barrera** | Off | On | Heurística + futuro campo explícito |
| **Pago ad-hoc** (tarjeta/NFC sin solo-app) | On | On | Filtra métodos de pago |
| **Mostrar advertencias** | On | On | Badge en ficha aunque no se excluya |

En **modo viaje**, muchos usuarios aceptan Ionity en área de servicio (parking asociado pero pensado para parada corta) → filtros menos agresivos por defecto.

En **modo ciudad**, filtros más estrictos por defecto.

### Evolución de datos

- Fase 1: heurísticas DATEX + iconos de advertencia.
- Fase 2: texto libre en dirección/nombre (*«Centro Comercial»*, *«Parking»*) como refuerzo.
- Fase 3: datos dinámicos REVE (precio estacionamiento si existiera).
- Fase 4: **crowdsourcing opcional** (*«Parking de pago confirmado»*) — solo si aporta valor sin falsear NAP.

---

## 4. Combinación de filtros — ejemplos

### Ejemplo A — Granada, noche en hotel

- Perfil: **En ciudad**
- Potencia: **3 – 22 kW**
- Acceso: **Solo abierto** + **Excluir CC**
- Radio: 500 m – 2 km del mapa

→ Postes en calle o parkings públicos sin shopping.

### Ejemplo B — Granada → Cartagena, 44 %

- Perfil: **En viaje**
- Potencia: **≥ 100 kW**
- Acceso: estándar (áreas de servicio OK)
- Búsqueda: **en corredor de ruta**, anti-retroceso

→ HPC en A-92 / A-7, no SC Granada ni Cullar en sentido contrario.

### Ejemplo C — Recarga lenta en CC a propósito

- Usuario **desactiva** «Excluir centros comerciales»
- Potencia: 22 kW
- Ve Leroy Merlin / IKEA con aviso ⚠ *Posible parking de pago*

---

## 5. Modelo de datos (campos extra)

Extensión del esquema en [`DATA_SOURCES.md`](DATA_SOURCES.md):

```json
{
  "max_power_kw": 50,
  "min_power_kw": 7.4,
  "charging_modes": ["mode3AC3p", "mode4DC"],
  "access_class": "commercial_parking",
  "access_warnings": ["possible_paid_parking", "indoor"],
  "payment_ad_hoc": true,
  "type_of_site": "inBuilding",
  "associated_facilities": ["parkingSite"],
  "supplemental_services": ["foodShopping"]
}
```

---

## 6. Criterios de aceptación

- [ ] Usuario puede elegir cualquier rango de potencia (presets + custom).
- [ ] Modo ciudad: potencia y ubicación son **independientes** y combinables.
- [ ] Modo ciudad: al menos 3 modos de ubicación (cerca de mí, dirección, zona mapa).
- [ ] Resultados en ciudad ordenados por **distancia** al punto de referencia.
- [ ] Perfil «En ciudad» muestra cargadores lentos por defecto.
- [ ] Perfil «En viaje» mantiene ≥ 100 kW por defecto pero es cambiable.
- [ ] Filtro «Excluir centros comerciales» reduce resultados con `foodShopping`+`parkingSite`.
- [ ] Estaciones dudosas muestran **advertencia visible**, no se ocultan silenciosamente salvo filtro activo.
- [ ] Si no hay datos de acceso, mostrar `unknown` — no asumir «público».

---

## 7. Decisiones abiertas

| Tema | Decisión / opciones |
|------|---------------------|
| Radio default modo ciudad | **1 km** ✓ |
| Default potencia modo ciudad | 3–22 kW vs 7–22 kW |
| Ionity en área de servicio | ¿Clase `public_parking` o `public_open`? |
| Crowdsourcing acceso | Sí / no / solo fase 4 |
| Portugal MOBI.E | Validar mismos campos DATEX en feed PT |
| Geocoding | Nominatim (OSM) vs Google Geocoding API |
| Auto-buscar al mover mapa | Sí (debounce) vs botón Buscar explícito |
