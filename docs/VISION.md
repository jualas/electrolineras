# Visión del producto

## Resumen

Una aplicación que centralice en un **único mapa** las electrolineras de la península ibérica, permitiendo **filtrar por potencia de carga** y consultar la red completa sin depender de la app de un operador concreto (Tesla, Ionity, Iberdrola, etc.).

## Usuario objetivo

Conductores de vehículo eléctrico — especialmente Tesla — que viajan por España y Portugal y necesitan:

- Ver **todos** los cargadores públicos relevantes en un mapa.
- Filtrar por potencia (p. ej. solo ≥ 150 kW para viajes largos).
- Conocer operador, conectores compatibles y, cuando exista, disponibilidad y precio.

## Funcionalidades clave (MVP)

### Mapa

- Vista de península con clusters de puntos.
- Zoom a detalle: dirección, coordenadas, operador, conectores, potencia por punto.
- Geolocalización del usuario (con permiso).

### Filtros

| Filtro | Ejemplo |
|--------|---------|
| Potencia mínima | ≥ 43 kW (rápido), ≥ **100 kW** (viaje), ≥ 150 kW — **siempre elegible** (ver [`FILTERS.md`](FILTERS.md)) |
| Potencia máxima | Imprescindible para AC lento en ciudad (p. ej. 3–22 kW) |
| Tipo de conector | CCS2, Tipo 2, CHAdeMO, etc. |
| Operador | Tesla, Ionity, Repsol, MOBI.E, etc. |
| País | ES / PT / ambos |
| **Acceso** | Público abierto; excluir CC / parking de pago; pago ad-hoc |

### Búsqueda en ciudad

Modo «**En ciudad**» — ver [`FILTERS.md`](FILTERS.md) §2:

- Filtro por **potencia** (presets + rango custom).
- Filtro por **ubicación** (cerca de mí, dirección, zona del mapa, pin).
- Radio ajustable (500 m – 5 km); **default 1 km**.
- Resultados ordenados por distancia + filtros de acceso opcionales.

Potencia y ubicación se eligen **por separado** y se combinan en una sola búsqueda.

### Búsqueda en ruta (feature estrella)

Modo “**Cargadores en mi ruta**” — ver [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md):

- Origen + destino (ej. Granada → Cartagena).
- Potencia **elegible**: presets (lento / viaje / custom min–max).
- Solo cargadores dentro del **corredor** de la autovía (modo viaje).
- Filtros de **acceso público** (excluir CC con parking de pago cuando interese).
- Excluir paradas **detrás** o que exijan cambio de sentido (anti-U-turn).
- Ordenar por **menor desvío** + potencia.
- Un toque para abrir en Google Maps o (fase 2) enviar al Tesla.

### Datos

- **España:** feed oficial DATEX II del NAP (DGT/MITECO) como base estática.
- **España (fase 2):** enriquecer con datos dinámicos de REVE (disponibilidad, precio) si hay acceso técnico legal.
- **Portugal:** feed DATEX II de MOBI.E.

## Por qué no basta con REVE o la app de Tesla

| Herramienta | Limitación para nuestro caso |
|-------------|------------------------------|
| App Tesla | Sesgo hacia Superchargers; terceros con cobertura parcial |
| REVE | Solo España; filtros limitados respecto a nuestro objetivo; no sustituye visión peninsular unificada |
| Chargemap / Electromaps | Datos comunitarios o comerciales; no siempre alineados con NAP oficial; mezcla de calidades |

Nuestro valor: **agregación peninsular + filtro por potencia + fuente oficial como verdad de referencia**.

## Fases de desarrollo

### Fase 0 — Definición ✅ completada

- Documentar fuentes y arquitectura.
- Validar feeds DATEX II (ES + PT).
- Definir esquema de datos común.
- Tarea TaskBoard: [#6021](../TASKBOARD.md#task-6021).

### Fase 1 — MVP web (actual)

Backlog detallado en [`TASKBOARD.md`](../TASKBOARD.md) y resumen en [`STATUS.md`](STATUS.md).

- [#6022](../TASKBOARD.md#task-6022) Bootstrap del entorno de desarrollo ✅
- [#6023](../TASKBOARD.md#task-6023) Descarga NAP España ✅ · [#6024](../TASKBOARD.md#task-6024) Descarga NAP Portugal ✅
- [#6025–6027](../TASKBOARD.md#task-6025) Parser DATEX, modelo SQLite y pipeline GeoJSON (pendiente).
- [#6028–6030](../TASKBOARD.md#task-6028) API REST (listado, ruta, ciudad).
- [#6031–6036](../TASKBOARD.md#task-6031) Frontend mapa (MapLibre) con filtros, búsqueda en ruta/ciudad y navegación externa.

### Fase 2 — Datos dinámicos España

- Investigar acceso a REVE/SGV (OCPI, acuerdo con Red Eléctrica o uso de datos ya publicados).
- Mostrar disponibilidad y precio cuando existan.

### Fase 3 — Experiencia en Tesla

- UI táctil, contraste alto, pocos clics.
- Probar en navegador del vehículo.
- Enlace “Abrir en Google Maps / Waze” o coordenadas copiables.

### Fase 4 — Unión Europea

- Conforme otros estados publiquen NAP (reglamento AFIR / NAPCORE).
- Conectores por país reutilizando el mismo esquema normalizado.

## Criterios de éxito

- Un viaje Madrid–Lisboa se puede planificar viendo solo cargadores ≥ X kW en un mapa.
- Los datos de España coinciden con el NAP oficial (misma cobertura base).
- La web funciona en el navegator Tesla sin instalar nada.
