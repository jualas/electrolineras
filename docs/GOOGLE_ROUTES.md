# Google Routes API — sustitución de OSRM

Guía operativa y decisiones de diseño (Entrega 1) para delegar el cálculo de rutas en **Google Maps Platform (Routes API)** y apagar los dos contenedores OSRM locales (`-8 GB RAM`, `-25 GB disco`).

## Variantes soportadas

| Preferencia (`route_preference`) | Cómo se calcula en Google Routes API | Uso |
|---|---|---|
| `fastest` | `DEFAULT_ROUTE` (`TRAFFIC_AWARE_OPTIMAL` por defecto) | Menor tiempo con tráfico real |
| `shortest` | `requestedReferenceRoutes: ["SHORTER_DISTANCE"]` *(con waypoints: fallback a `computeAlternativeRoutes` eligiendo la más corta)* | Menos kilómetros (más cercana a línea recta) |
| `eco` | `requestedReferenceRoutes: ["FUEL_EFFICIENT"]` + `vehicleInfo.emissionType = "ELECTRIC"` | Menor consumo energético (tiene en cuenta desniveles/sierra) |
| `conventional` | Llamada paralela con `avoidHighways: true` (+ `avoidTolls` según checkbox) | Solo carreteras nacionales/secundarias |

## Variables de entorno

```env
ROUTING_PROVIDER=google
GOOGLE_MAPS_API_KEY=CHANGE_ME
GOOGLE_ROUTES_ROUTING_PREFERENCE=TRAFFIC_AWARE_OPTIMAL
GOOGLE_ROUTES_ENABLE_ECO=true
GOOGLE_ROUTES_TIMEOUT_SECONDS=20
GOOGLE_ROUTES_CACHE_ENABLED=true
GOOGLE_ROUTES_CACHE_TTL_SECONDS=300
GOOGLE_ROUTES_FALLBACK_TO_OSRM=false
```

- Con `ROUTING_PROVIDER=auto`, usa Google automáticamente si `GOOGLE_MAPS_API_KEY` tiene valor y OSRM en caso contrario.
- Si prefieres quedarte solo en el nivel **Essentials** (10.000 peticiones/mes gratis, sin tráfico ni eco VE), cambia `GOOGLE_ROUTES_ROUTING_PREFERENCE=TRAFFIC_UNAWARE` y `GOOGLE_ROUTES_ENABLE_ECO=false`.
- La caché (`GOOGLE_ROUTES_CACHE_TTL_SECONDS=300`) es estrictamente **en memoria** y efímera para evitar peticiones repetidas al ajustar filtros de potencia o cambiar de pestaña.

## Control de costes (mantener 0 €/mes)

Google Maps Platform ofrece cuotas mensuales gratuitas por SKU:

- **Compute Routes Essentials:** 10.000 peticiones/mes gratis.
- **Compute Routes Pro** (tráfico + `FUEL_EFFICIENT` VE): 5.000 peticiones/mes gratis.

Para garantizar 0 €/mes:
1. En **Google Cloud Console → APIs y servicios → Credenciales**, restringe la clave del backend exclusivamente a **Routes API**.
2. En **Google Cloud Console → APIs y servicios → Routes API → Cuotas**, fija un límite diario conservador (p. ej. **120 peticiones/día** = ~3.600/mes, siempre por debajo de las 5.000 gratis de Pro).
3. En **Facturación → Presupuestos y alertas**, crea una alerta en 1 € / 5 €.

## Visor Google Maps JS (Entrega 2)

El frontend (`Electrolineras` y `ElectrolinerasCercanas`) cambia automáticamente de MapLibre a **Google Maps JavaScript API** cuando `VITE_GOOGLE_MAPS_JS_API_KEY` tiene valor (salvo que se fuerce `VITE_MAP_PROVIDER=maplibre`):

- **Clave separada (`electrolineras-maps-web`):** restringida por HTTP referrer (`https://electro.jualas.es/*`, `http://localhost/*`, `http://127.0.0.1/*`, `https://localhost/*`) y **únicamente a `Maps JavaScript API`**.
- **Cuota diaria:** `Map loads per day = 250` (máx. ~7.500/mes, siempre dentro de las 10.000 cargas gratis/mes) y `3D Map loads per day = 50`.
- **Capas nativas:** el control de capas usa **Tráfico en tiempo real de Google Maps** (sin clave TomTom) y **Relieve (`terrain`)** nativo.
- **Docker producción:** `docker/Dockerfile.nginx` y `docker/docker-compose.prod.yml` reciben `VITE_GOOGLE_MAPS_JS_API_KEY` como build arg desde el `.env` de producción.

## Verificación mixta de cargadores (Entrega 3 — Places API New)

Para evitar llegar a un cargador único en zona aislada/sierra y encontrarlo averiado:

- **Base y búsqueda en corredor:** siguen siendo **100 % SQLite local** (NAP DGT + MOBI.E + REVE), con 0 llamadas a Google.
- **Análisis de zona aislada (0 coste):** para cada parada planificada se buscan alternativas rápidas en un radio de **50 km** (`RELIABILITY_ISOLATION_RADIUS_KM=50`) en SQLite local y se calcula la distancia al **plan B más cercano**.
- **Verificación cruzada bajo demanda (`GET /api/v1/stations/{id}/reliability`):** combina REVE local + **Google Places API (New)** (`evChargeOptions` + `businessStatus` + valoración + enlace directo a reseñas en Google Maps), con caché efímera en memoria de 10 min (`GOOGLE_PLACES_EV_CACHE_TTL_SECONDS=600`).
- **Control de coste (0 €/mes):** `evChargeOptions` usa el SKU *Enterprise + Atmosphere* (1.000 llamadas/mes gratis). La clave `electrolineras-routes-backend` queda restringida a `Routes API` + `Places API (New)` y la cuota diaria de `Places API (New)` se limita a **25 peticiones/día** (~750/mes).

## Apagar OSRM una vez verificado

```bash
cd docker/osrm && docker compose down
```

Si quieres volver a OSRM en cualquier momento, basta cambiar `ROUTING_PROVIDER=osrm` en `.env` y levantar de nuevo el compose.
