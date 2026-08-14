# OSRM — Electrolineras

Dos grafos sobre mapa Geofabrik **Iberia** (ES+PT):

| Servicio | Perfil | Uso |
|----------|--------|-----|
| `:5000` `car` | `car.lua` | **Rápida** (tiempo) y **convencionales** (`exclude=motorway`) |
| `:5001` `shortest` | `shortest.lua` | **Directa** (minimiza km / rectitud) |

## Modo on-demand (producción mini PC)

OSRM **no** arranca solo tras reboot (`restart: "no"`).

1. La API intenta el OSRM local.
2. Si falla (parado / cargando) → **fallback** a `router.project-osrm.org` y escribe `osrm_wake.request` en el volumen de datos.
3. Cron host (`scripts/osrm/run_osrm_lifecycle.sh`) cada 2 min:
   - arranca si hay demanda
   - mata contenedores `unhealthy` tras gracia (~12 min)
   - para por idle tras ~30 min sin uso local

Variables API relevantes: `OSRM_PUBLIC_EMERGENCY_FALLBACK`, `OSRM_WAKE_ON_FAILURE`, `OSRM_LIFECYCLE_DIR`.

## Build (una vez, ~30–90 min)

```bash
./scripts/osrm/build_iberia.sh
```

Requisitos: Docker, ~8 GB RAM en el pico, ~25 GB disco en `OSRM_DATA_DIR`.

Descarga Geofabrik **España + Portugal** (fusionados con osmium) — no existe extract `iberia-latest` en Geofabrik.

## Arrancar manualmente

```bash
cd docker/osrm
docker compose up -d
# o
./scripts/osrm/manage_osrm.sh wake
./scripts/osrm/manage_osrm.sh status
```

## Activar en Electrolineras

En `/mnt/datos/docker/electrolineras/.env`:

```env
OSRM_BASE_URL=http://electrolineras-osrm-car:5000
OSRM_SHORTEST_BASE_URL=http://electrolineras-osrm-shortest:5000
OSRM_USE_MULTI_PROFILE=true
OSRM_PROFILE_FASTEST=car
OSRM_PROFILE_SHORTEST=shortest
OSRM_PROFILE_CONVENTIONAL=car
OSRM_PUBLIC_EMERGENCY_FALLBACK=true
OSRM_PUBLIC_FALLBACK_URL=https://router.project-osrm.org
OSRM_PUBLIC_PROFILE=driving
OSRM_WAKE_ON_FAILURE=true
OSRM_LIFECYCLE_DIR=/app/data/runtime
```

Reinicia la app: `docker compose up -d --build`
