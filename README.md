# Electrolineras de la Península Ibérica

Mapa unificado de **puntos de recarga de vehículos eléctricos** en España y Portugal, con filtro por potencia y datos agregados de fuentes oficiales.

## Problema que resolvemos

Hoy la información está dispersa y el **navegador del coche** (p. ej. Tesla) elige paradas que en la práctica son malas:

- Desvíos largos a Superchargers “de paso” cuando ya vas orientado al destino.
- Paradas que obligan a **salir, cambiar de sentido y volver a incorporarse** (ej. Granada → Cartagena con parada en Cullar).

**Caso típico:** desde Granada con 44 % hacia Cartagena, buscar en segundos cargadores **≥ 100 kW en la carretera**, en sentido de marcha, con el menor desvío posible — desde el móvil (web o Android).

Detalle del caso de uso: [`docs/ROUTE_CORRIDOR_SEARCH.md`](docs/ROUTE_CORRIDOR_SEARCH.md).

## Objetivo del producto

**Aplicación web móvil** (y opcionalmente Android) que permita:

1. **Búsqueda rápida en ruta:** cargadores ≥ X kW **en el corredor de la carretera** hacia un destino, sin paradas en sentido contrario ni desvíos absurdos.
2. **Mapa peninsular** con filtro por potencia y operador (datos oficiales NAP).

En una fase posterior, ampliar a **otros países de la UE** cuando publiquen su NAP (reglamento AFIR).

## Fuentes de datos principales

| País | Fuente oficial | Formato | Actualización |
|------|----------------|---------|---------------|
| España (estático) | [NAP DGT / MITECO](https://nap.dgt.es/dataset/puntos-de-recarga-electrica-para-vehiculos) | DATEX II v3 | ~24 h |
| España (dinámico) | [REVE / mapareve.es](https://www.mapareve.es/) (Red Eléctrica) | Web + app; protocolo OCPI entre operadores | Tiempo real |
| Portugal | [MOBI.E NAP](https://pgm.mobie.pt/integration/nap/evChargingInfra) | DATEX II | Tiempo real |

Detalle técnico en [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md).

## Clientes previstos

1. **Web / PWA** — mapa interactivo en móvil y escritorio (MVP).
2. **Navegador Tesla** — misma web optimizada para pantalla del coche (sin instalar app nativa).
3. **Futuro** — app nativa o integración con planificadores de ruta si aporta valor.

> Tesla no permite sustituir su navegación nativa por apps de terceros. La vía realista es una **web usable en el coche** o enviar destinos al navegador del vehículo.

## Documentación

### Producto y diseño

- [`docs/VISION.md`](docs/VISION.md) — visión, funcionalidades y fases
- [`docs/DATA_SOURCES.md`](docs/DATA_SOURCES.md) — URLs, formatos y estrategia de ingestión
- [`docs/FILTERS.md`](docs/FILTERS.md) — potencia elegible y acceso público
- [`docs/NAVIGATION.md`](docs/NAVIGATION.md) — envío de paradas y rutas al coche (Tesla, Google Maps)
- [`docs/ROUTE_CORRIDOR_SEARCH.md`](docs/ROUTE_CORRIDOR_SEARCH.md) — búsqueda en corredor de ruta
- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) — arquitectura propuesta
- [`docs/STORAGE.md`](docs/STORAGE.md) — persistencia SQLite / SpatiaLite / PostGIS

### Seguimiento

- [`docs/STATUS.md`](docs/STATUS.md) — fase actual, roadmap con IDs de tarea
- [`TASKBOARD.md`](TASKBOARD.md) — espejo del backlog en [TaskBoard](https://kanban.jualas.es) (proyecto `id=7`)

## Estructura del repo

```
Electrolineras/
├── data/
│   ├── raw/           # XML DATEX descargados (gitignore)
│   ├── processed/     # GeoJSON exportado
│   └── db/            # stations.db (gitignore)
├── docs/
├── scripts/           # ingest_all.py, etc.
├── src/
│   ├── api/           # FastAPI
│   ├── db/            # persistencia (#6026)
│   ├── ingest/        # fetch + parser DATEX
│   ├── models/
│   └── web/           # Frontend Vite + React
├── tests/
├── pyproject.toml
├── Makefile
└── .env.example
```

## Requisitos

- **Python 3.11+**
- **Node.js 20+** (frontend)
- `make` (opcional, atajos de desarrollo)

## Arranque local

```bash
# 1. Variables de entorno
cp .env.example .env

# 2. Backend (venv + dependencias + tests)
make install-dev

# 3. Terminal A — API
make api
# → http://127.0.0.1:8000/health
# → http://127.0.0.1:8000/docs (OpenAPI / Swagger)

# 4. Terminal B — frontend
make web
# → http://127.0.0.1:5173
```

Comandos útiles:

| Comando | Descripción |
|---------|-------------|
| `make install` | Solo Python (venv + `pip install -e .`) |
| `make install-dev` | Python + dependencias dev + `npm install` en `src/web` |
| `make api` | Uvicorn con recarga (`electrolineras-api`) |
| `make web` | Vite dev server (`src/web`, proxy API) |
| `make web-build` | Build estático → `src/web/dist/` |
| `make test` | pytest |
| `make lint` | ruff sobre `src/` y `tests/` |
| `make fetch-es` | Descarga feed NAP España → `data/raw/es/` |
| `make fetch-pt` | Descarga feed NAP Portugal (streaming ~180 MB) → `data/raw/pt/` |
| `make parse-es` / `make parse-pt` | Parsear último XML DATEX → resumen JSON |
| `make load-db` | Re-parsear XML existente → SQLite + GeoJSON (sin descargar) |
| `make ingest` | Pipeline completo: descarga ES+PT → SQLite → GeoJSON |
| `make ingest-es` / `make ingest-pt` | Pipeline de un solo país (ideal para cron) |

### Pipeline de ingestión

Flujo: **descarga DATEX → parse → SQLite → GeoJSON**.

```bash
make ingest              # ES + PT completo
make ingest-es           # solo España (cron diario)
make ingest-pt           # solo Portugal (cron cada 6 h)
.venv/bin/electrolineras-ingest --skip-fetch   # sin red, usa XML en data/raw/
.venv/bin/electrolineras-ingest --summary      # resumen JSON
```

Salidas: `data/raw/{es,pt}/`, `data/db/stations.db`, `data/processed/stations.geojson`.

Cron de ejemplo: [`scripts/cron/electrolineras.crontab.example`](scripts/cron/electrolineras.crontab.example)

Pasos individuales (depuración):

```bash
make fetch-es && make fetch-pt && make load-db
```

### API REST (#6028)

Documentación interactiva: `http://127.0.0.1:8000/docs`

| Endpoint | Descripción |
|----------|-------------|
| `GET /health` | Estado del servicio |
| `GET /api/v1/stations` | Lista paginada (`format=json\|geojson`, `min_kw`, `max_kw`, `country`, `bbox`, `limit`, `offset`) |
| `GET /api/v1/stations/{id}` | Detalle de una estación |
| `GET /api/v1/stations/nearby` | Ciudad: `lat/lon`, `q` (geocode), `bbox`, `radius_m` (default 1 km), kW, filtros acceso |
| `GET /api/v1/stations/along-route` | Búsqueda en corredor (`origin_lat/lon`, `dest_lat/lon`, `min_kw`, `corridor_km`, `behind_margin_km`) |
| `GET /api/v1/meta/stats` | Conteos por país y bandas de potencia |
| `GET /api/v1/meta/operators` | Top operadores (`country`, `limit`) |

Ejemplos:

```bash
curl 'http://127.0.0.1:8000/api/v1/stations?min_kw=100&country=ES&format=geojson&limit=50'
curl 'http://127.0.0.1:8000/api/v1/stations/along-route?origin_lat=37.18&origin_lon=-3.60&dest_lat=37.60&dest_lon=-0.99&min_kw=100&corridor_km=10'
curl 'http://127.0.0.1:8000/api/v1/meta/stats'
```

## Estado

**Fase 1 — MVP datos + mapa**. Completadas [#6022](TASKBOARD.md#task-6022)–[#6031](TASKBOARD.md#task-6031). Siguiente: [#6032 mapa con estaciones](TASKBOARD.md#task-6032).

Detalle del avance: [`docs/STATUS.md`](docs/STATUS.md) · backlog completo: [`TASKBOARD.md`](TASKBOARD.md)
