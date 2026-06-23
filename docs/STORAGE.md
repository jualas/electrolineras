# Persistencia y almacenamiento

Documento de diseño para la capa de datos del MVP (#6026) y la evolución hacia PostGIS si el producto crece.

## Decisión (MVP)

| Fase | Motor | Extensión geo | Motivo |
|------|-------|---------------|--------|
| **MVP (Fase 1)** | **SQLite 3** | **SpatiaLite** (opcional en v1.0; recomendado antes de #6029) | Cero infraestructura, un solo fichero, despliegue trivial |
| **Crecimiento (Fase 2–3)** | **PostgreSQL** | **PostGIS** | Más países UE, datos dinámicos REVE/OCPI, consultas espaciales pesadas en servidor |

**Regla práctica:** empezar con SQLite; migrar a PostGIS cuando aparezca al menos uno de estos disparadores:

- Más de **~100k** estaciones en el catálogo (península + varios NAP UE).
- Datos **dinámicos** con actualización frecuente (estado, precio) y necesidad de concurrencia de escritura.
- Consultas **en corredor de ruta** (#6029) con latencia objetivo &lt; 200 ms bajo carga sin depender del cálculo en memoria.
- Varios procesos de ingestión/API escribiendo a la vez (SQLite serializa escrituras).

Hasta entonces, SQLite cubre el volumen y los patrones de lectura del MVP.

---

## Escala esperada

| Fuente | Orden de magnitud | Notas |
|--------|-------------------|-------|
| NAP España (DGT) | ~15–30k EVSE / sitios | Feed diario, estático |
| NAP Portugal (MOBI.E) | ~10–25k | XML ~180 MB; muchos puntos por operador |
| **Total península (MVP)** | **~25–50k** sitios | Coherente con la alternativa «solo GeoJSON estático» en [`ARCHITECTURE.md`](ARCHITECTURE.md) |
| REVE (fase 2) | ~25k+ (solapamiento con NAP) | Merge por `raw_ref` o proximidad; no duplicar filas visibles |
| UE (fase 3) | 100k–500k+ | Disparador claro para PostGIS |

SQLite maneja cómodamente **millones de filas** en lectura; el límite real del MVP es la **complejidad de consultas geo** y la **frecuencia de actualización**, no el tamaño del fichero (~50–200 MB con índices).

---

## Ubicación de ficheros

```
data/
├── raw/                    # XML DATEX descargados (gitignore)
│   ├── es/
│   └── pt/
├── processed/
│   └── stations.geojson    # export para mapa estático / backup (#6027)
└── db/
    └── stations.db         # SQLite principal (gitignore)
```

Variable de entorno propuesta: `DATABASE_URL=sqlite:///data/db/stations.db` (compatible con SQLAlchemy si se adopta).

---

## Modelo lógico

Alineado con el esquema JSON de [`DATA_SOURCES.md`](DATA_SOURCES.md).

### Entidades

1. **`station`** — un emplazamiento (sitio / location en DATEX).
2. **`connector`** — conector físico con potencia y tipo (1:N con `station`).
3. **`ingest_run`** (opcional en MVP, útil para depuración) — metadatos de cada ejecución del pipeline.

Regla de negocio para filtros de potencia: columna denormalizada **`max_power_kw`** en `station` (máximo de sus conectores) para consultas rápidas; detalle por conector en tabla hija.

### Esquema SQL (borrador)

```sql
-- Metadatos de ingestión
CREATE TABLE ingest_run (
    id              INTEGER PRIMARY KEY,
    source          TEXT NOT NULL,          -- 'es-nap-dgt', 'pt-nap-mobie'
    started_at      TEXT NOT NULL,          -- ISO 8601 UTC
    finished_at     TEXT,
    source_version  TEXT,                   -- publicationTime del feed DATEX
    records_upserted INTEGER,
    status          TEXT NOT NULL           -- 'running', 'ok', 'error'
);

CREATE TABLE station (
    id              TEXT PRIMARY KEY,       -- es-dgt-{raw_ref} o compuesto estable
    source          TEXT NOT NULL,
    country         TEXT NOT NULL,          -- 'ES', 'PT'
    site_name       TEXT,
    operator        TEXT,
    lat             REAL NOT NULL,
    lon             REAL NOT NULL,
    address         TEXT,
    max_power_kw    REAL NOT NULL DEFAULT 0,
    access          TEXT,                   -- 'public', 'private', 'restricted', ...
    payment_methods TEXT,                   -- JSON array serializado
    opening_hours   TEXT,
    raw_ref         TEXT NOT NULL,          -- id en feed DATEX
    fetched_at      TEXT NOT NULL,
    source_version  TEXT,
    -- columnas dinámicas (fase 2; nullable en MVP)
    dynamic_status  TEXT,
    dynamic_price   REAL,
    dynamic_updated_at TEXT,
    UNIQUE (source, raw_ref)
);

CREATE TABLE connector (
    id              INTEGER PRIMARY KEY,
    station_id      TEXT NOT NULL REFERENCES station(id) ON DELETE CASCADE,
    connector_type  TEXT,                   -- CCS2, CHAdeMO, Type2, ...
    power_kw        REAL NOT NULL,
    voltage_v       INTEGER,
    current_a       INTEGER
);

-- Índices no espaciales (MVP mínimo)
CREATE INDEX idx_station_country ON station(country);
CREATE INDEX idx_station_max_power ON station(max_power_kw);
CREATE INDEX idx_station_lat_lon ON station(lat, lon);
CREATE INDEX idx_station_operator ON station(operator);
CREATE INDEX idx_connector_station ON connector(station_id);
CREATE INDEX idx_connector_power ON connector(power_kw);
```

### SpatiaLite (recomendado antes de búsqueda en ruta)

Tras `SELECT InitSpatialMetadata(1)`:

```sql
SELECT AddGeometryColumn('station', 'geom', 4326, 'POINT', 'XY');
UPDATE station SET geom = MakePoint(lon, lat, 4326);
SELECT CreateSpatialIndex('station', 'geom');
```

Consultas típicas:

- **BBox:** `MBRIntersects(geom, BuildMBR(west, south, east, north))`
- **Cercanía:** `ST_Distance(geom, MakePoint(lon, lat, 4326), 1) <= radius_m` (modo 1 = esfera)
- **Corredor (#6029):** buffer sobre polilínea de ruta (OSRM) + `ST_Intersects` / distancia al segmento

Si se retrasa SpatiaLite en la primera iteración de #6026, **bbox + Haversine en SQL** sobre `(lat, lon)` indexados es suficiente para #6028 y #6030; el corredor (#6029) puede calcularse en Python sobre un subconjunto prefiltrado por bbox ampliado.

---

## Patrones de consulta por endpoint

| Endpoint / feature | Filtros | Estrategia SQLite | Notas PostGIS futuras |
|--------------------|---------|-------------------|------------------------|
| `GET /stations` | bbox, min/max kW, country | Índice `(lat,lon)` + `max_power_kw`; SpatiaLite si hay muchos puntos en bbox | `&&` + `ST_Intersects` con índice GiST |
| `GET /stations/{id}` | PK | Lookup directo | Igual |
| `GET /stations/nearby` | punto + radio 1 km default | SpatiaLite `ST_Distance` o Haversine con límite | `ST_DWithin(geom, point, radius)` |
| `GET /stations/along-route` | polilínea + ancho corredor + min kW | Prefiltro bbox del corredor → distancia punto-segmento en app o SpatiaLite | `ST_Buffer(route, width)` + join |
| `GET /meta/stats` | agregaciones | `GROUP BY` en SQL | Materialized views opcionales |
| Mapa / clustering | tiles o bbox | Paginación + límite de features | Vector tiles con pg_tileserv (fase 3) |

La **búsqueda en corredor** es la consulta más exigente; no bloquea el MVP si se implementa en dos fases (prefiltro SQL + refinamiento en Python).

---

## Capa de acceso en código (#6026)

Estructura prevista en `src/models/` y `src/db/` (nombres orientativos):

```
src/
├── models/
│   └── station.py          # Pydantic: Station, Connector, StationCreate
└── db/
    ├── connection.py       # sqlite3 / aiosqlite; DATABASE_URL
    ├── schema.py           # CREATE TABLE + migraciones versionadas
    ├── repository.py       # StationRepository (CRUD + consultas)
    └── spatial.py          # helpers bbox / SpatiaLite (aislados)
```

### Interfaz del repositorio (contrato estable)

Operaciones mínimas para desacoplar SQLite de PostGIS:

- `upsert_stations(stations: list[Station]) -> int`
- `get_by_id(id: str) -> Station | None`
- `search(bbox, min_kw, max_kw, countries, limit, offset) -> list[Station]`
- `nearby(lat, lon, radius_m, min_kw, ...) -> list[Station]`
- `delete_by_source(source: str)` — antes de reimport completo, o preferir upsert por `(source, raw_ref)`

La implementación MVP usa **sqlite3** estándar o **aiosqlite** si FastAPI async; SQLAlchemy Core es opcional (añade dependencia pero facilita migración a Postgres).

---

## Pipeline de escritura (#6027)

Flujo acordado:

```
fetch (ES/PT) → parse DATEX → list[Station] → repository.upsert → export GeoJSON
```

Política de **upsert**:

1. Clave natural: `(source, raw_ref)`.
2. Actualizar `fetched_at`, `source_version`, conectores (borrar hijos y reinsertar, o diff simple).
3. No borrar estaciones ausentes del feed en MVP (pueden ser baja temporal); en fase 2, marcar `last_seen_at` y ocultar las no vistas en N ingestiones consecutivos.

Transacciones: **una transacción por país y ejecución** para consistencia y rendimiento.

---

## Export GeoJSON (`data/processed/stations.geojson`)

No sustituye a SQLite; complementa:

- Desarrollo frontend sin levantar API.
- Hosting **estático** (alternativa minimalista en [`ARCHITECTURE.md`](ARCHITECTURE.md)).
- Backup legible y diff en revisiones manuales.

Generación: mismo `StationRepository` o query de solo lectura tras ingest. Incluir propiedades necesarias para filtros cliente (`max_power_kw`, `country`, `operator`).

---

## SQLite vs PostGIS — comparativa

| Criterio | SQLite + SpatiaLite | PostgreSQL + PostGIS |
|----------|----------------------|----------------------|
| Despliegue | Un fichero, sin servicio | Servidor, backups, conexiones |
| Concurrencia | Una escritura a la vez; muchas lecturas OK | Lecturas/escrituras concurrentes |
| Consultas geo | Suficiente hasta ~100k puntos y corredores moderados | Mejor para buffers, joins espaciales complejos, tiles |
| Migración UE | Funciona con índices; puede ir lento en stats globales | Escala horizontal con réplicas de lectura |
| Dev local | Idéntico a prod | Docker Compose con PostGIS |
| Coste hosting | ~0 (VPS + fichero) | DB gestionada o contenedor dedicado |

---

## Camino de migración a PostGIS

1. Mantener **mismo esquema lógico** (`station`, `connector`); en Postgres: `geom geometry(Point, 4326)` + índice GiST.
2. Script `scripts/migrate_sqlite_to_postgres.py`: volcar tablas + reconstruir geometrías.
3. Sustituir `src/db/repository.py` por implementación Postgres o usar SQLAlchemy con dialecto dual.
4. Tests de paridad: mismos bbox/min_kw deben devolver mismos ids (orden puede variar).

No implementar abstracción sobre-engineered; **un repositorio, dos backends** cuando haga falta.

---

## Dependencias Python (propuesta)

| Paquete | Uso |
|---------|-----|
| `sqlite3` (stdlib) | MVP |
| `libspatialite` + cargar extensión en conexión | Índices y ST_* en SQLite |
| `geojson` o serialización manual | Export #6027 |
| `sqlalchemy[asyncio]` + `asyncpg` | Solo si se elige PostGIS en Fase 2+ |
| `alembic` | Migraciones cuando exista Postgres |

En Docker MVP: imagen con `spatialite-bin` / extensión compilada si el host no la trae.

---

## Qué queda fuera del MVP

- Réplicas, sharding, lectura geo distribuida.
- Historial temporal de precios/disponibilidad (serie temporal → Postgres o Timescale).
- Cache Redis (innecesario hasta tráfico significativo; FastAPI + SQLite in-process suele bastar).
- Datos de usuario (sin cuentas en MVP; [`ARCHITECTURE.md`](ARCHITECTURE.md)).

---

## Tareas relacionadas

| ID | Relación |
|----|----------|
| [#6026](../TASKBOARD.md#task-6026) | Implementar modelo + repositorio SQLite |
| [#6027](../TASKBOARD.md#task-6027) | Upsert tras parse + export GeoJSON |
| [#6028](../TASKBOARD.md#task-6028) | Lecturas bbox / filtros |
| [#6029](../TASKBOARD.md#task-6029) | Consultas corredor; SpatiaLite recomendado |
| [#6030](../TASKBOARD.md#task-6030) | Nearby con radio 1 km |

Implementación y estado: [`TASKBOARD.md`](../TASKBOARD.md) · [`STATUS.md`](STATUS.md).
