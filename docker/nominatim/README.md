# Nominatim — Electrolineras (#6046)

Geocodificación **self-hosted** para España + Portugal (mismo extracto OSM que OSRM).

| Recurso | Orientativo |
|---------|-------------|
| RAM pico import | 8–16 GB |
| Disco `NOMINATIM_DATA_DIR` | ~60–90 GB |
| Tiempo import inicial | 4–12 h (mini PC) |
| Puerto | `127.0.0.1:8092` (evitar `:8088` y `:8090`, ya ocupados) |

## Preparar datos

Reutiliza el PBF Iberia de OSRM:

```bash
bash scripts/nominatim/prepare_pbf.sh
# o, si aún no existe:
bash scripts/osrm/build_iberia.sh
```

## Arrancar

```bash
cd docker/nominatim
docker compose up -d
docker compose logs -f nominatim   # seguir importación
```

Smoke test:

```bash
curl -s 'http://127.0.0.1:8092/search?q=Granada&format=json&limit=1&countrycodes=es' | head
```

## Conectar Electrolineras

En `/mnt/datos/docker/electrolineras/.env`:

```env
NOMINATIM_BASE_URL=http://host.docker.internal:8092
NOMINATIM_FALLBACK_BASE_URL=
NOMINATIM_CACHE_ENABLED=true
NOMINATIM_CACHE_TTL_SECONDS=86400
```

Reinicia API: `docker compose up -d electrolineras`

Guía completa: [`docs/NOMINATIM.md`](../../docs/NOMINATIM.md)
