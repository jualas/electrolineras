# Geocodificación en producción (#6046)

Nominatim self-hosted para búsqueda de ciudades (`/api/v1/meta/geocode`, `/api/v1/stations/nearby?q=`).

## Arquitectura

```
Frontend → FastAPI → caché in-memory (TTL) → Nominatim LAN :8092
                                              ↘ (opcional) fallback público
```

| Componente | Ubicación |
|------------|-----------|
| Nominatim Docker | `docker/nominatim/` → `127.0.0.1:8092` |
| PBF OSM | Reutiliza `osrm-iberia/iberia-latest.osm.pbf` |
| Datos Postgres | `/mnt/datos/docker/volumes/nominatim-iberia` |

## Despliegue inicial

```bash
bash scripts/nominatim/prepare_pbf.sh
cd docker/nominatim
docker compose up -d
docker compose logs -f nominatim
```

Variables opcionales (`docker/nominatim/.env` o entorno):

| Variable | Default | Notas |
|----------|---------|-------|
| `NOMINATIM_DATA_DIR` | `/mnt/datos/docker/volumes/nominatim-iberia` | Postgres |
| `OSRM_DATA_DIR` | `/mnt/datos/docker/volumes/osrm-iberia` | PBF read-only |
| `NOMINATIM_PORT` | `127.0.0.1:8092:8080` | Solo LAN |
| `NOMINATIM_IMPORT_THREADS` | `4` | Bajar si RAM justa |
| `NOMINATIM_DB_PASSWORD` | (cambiar) | Postgres interno |

## Configuración API

| Variable | Desarrollo | Producción |
|----------|------------|------------|
| `NOMINATIM_BASE_URL` | `https://nominatim.openstreetmap.org` | `http://host.docker.internal:8092` |
| `NOMINATIM_FALLBACK_BASE_URL` | vacío | vacío (no depender del público) |
| `NOMINATIM_USER_AGENT` | identificador dev | URL prod + email contacto |
| `NOMINATIM_COUNTRY_CODES` | `es,pt` | `es,pt` |

### Caché (API)

Reduce llamadas repetidas (misma ciudad escrita varias veces):

| Variable | Default | Efecto |
|----------|---------|--------|
| `NOMINATIM_CACHE_ENABLED` | `true` | Activa caché en proceso API |
| `NOMINATIM_CACHE_TTL_SECONDS` | `86400` (24 h) | TTL por consulta |
| `NOMINATIM_CACHE_MAX_ENTRIES` | `2048` | Evicción LRU por expiración |

La caché es **in-memory** (se reinicia con el contenedor API). No sustituye Nominatim local.

### Fallback de emergencia

Solo si el Nominatim propio cae:

```env
NOMINATIM_FALLBACK_BASE_URL=https://nominatim.openstreetmap.org
```

Se usa ante timeout o HTTP 429/5xx del primario. Respeta [política de uso](https://operations.osmfoundation.org/policies/nominatim/) (1 req/s). No usar como primario en prod.

## Coste / alternativas SaaS

| Opción | Coste | Notas |
|--------|-------|-------|
| **Self-hosted (recomendado)** | Hardware existente + disco | Sin límite de cuota; mantenimiento import |
| OSM Nominatim público | Gratis | **1 req/s**, bloqueos; solo dev/fallback |
| LocationIQ / Geoapify / Mapbox | € / 1000 req | Evaluar si no hay RAM para import |

Para nuestro volumen (autocompletado búsqueda ruta), self-hosted en mini PC es la opción alineada con OSRM.

## Monitoring

En `scripts/cron/electrolineras.env`:

```env
MONITOR_NOMINATIM_URL=http://127.0.0.1:8092/search?q=Madrid&format=json&limit=1&countrycodes=es
```

Incluido en `make monitor-check`.

## Validación

```bash
make nominatim-status
curl -s 'http://127.0.0.1:8092/search?q=Granada&format=json&limit=1&countrycodes=es' | head
```

Cuando el import termine (contenedor **healthy**, búsqueda responde JSON):

```bash
bash scripts/nominatim/finish_prod_setup.sh
# o: make nominatim-finish-prod
```

**Automático (recomendado):** cron cada 30 min que detecta cuando Nominatim responde y ejecuta el finish + notificación ntfy:

```bash
make nominatim-install-finish-cron
# log: electrolineras-data/logs/cron/nominatim-finish.log
# quitar tras éxito: make nominatim-remove-finish-cron
```

Eso desactiva el fallback público en prod, activa `MONITOR_NOMINATIM_URL` y reinicia la API.

```bash
make env-check-prod ENV_FILE=/mnt/datos/docker/electrolineras/.env
```

En producción falla si `NOMINATIM_BASE_URL` apunta al servicio público.

## Referencias

- OSRM Iberia: [`docker/osrm/README.md`](../docker/osrm/README.md)
- Variables: [`ENV.md`](ENV.md)
- Runbook: [`DEPLOYMENT.md`](DEPLOYMENT.md)
