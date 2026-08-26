# Docker — Electrolineras

Despliegue en el mini PC bajo `/mnt/datos/docker/electrolineras/`.

## Stacks disponibles

| Fichero | Uso |
|---------|-----|
| `docker-compose.prod.yml` | **Producción** — API + nginx (`:8015` / electro.jualas.es) |
| `docker-compose.staging.yml` | **Staging** — mismo stack en `:8016` (pruebas antes de prod) |
| `docker-compose.yml` | Monolito (API sirve estáticos); útil para pruebas rápidas |

OSRM corre aparte en `docker/osrm/` (red Docker externa `osrm_default`).

Staging: ver [`docs/STAGING.md`](../docs/STAGING.md) (`make deploy-staging`).

## Primera vez

```bash
# Datos persistentes
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/db
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/raw/es
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/raw/pt
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/processed
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/logs

# Copiar DB inicial si el volumen está vacío
if [ ! -f /mnt/datos/docker/volumes/electrolineras-data/db/stations.db ]; then
  cp /mnt/datos/Proyectos/Electrolineras/data/db/stations.db \
    /mnt/datos/docker/volumes/electrolineras-data/db/stations.db
fi

# Config despliegue (desde el repo)
make docker-sync-prod
cd /mnt/datos/docker/electrolineras
cp env.example .env
# Editar .env (CORS, dominio, token Cloudflare)
# Validar y permisos: ver docs/ENV.md
#   make env-check-prod ENV_FILE=/mnt/datos/docker/electrolineras/.env
#   make env-secure

docker compose -f docker-compose.prod.yml up -d --build
```

## Verificación

```bash
curl -s http://127.0.0.1:8015/health
curl -s http://127.0.0.1:8015/api/v1/meta/stats | head -c 200
```

Web: http://127.0.0.1:8015

## Cloudflare Tunnel

En Zero Trust, public hostname `electro.jualas.es` → `http://127.0.0.1:8015`

O activar el servicio `electrolineras-cloudflared` en `docker-compose.prod.yml` con `CLOUDFLARED_TOKEN`.

## Actualizar tras cambios en el repo

```bash
make deploy
# o manualmente:
make docker-sync-prod
cd /mnt/datos/docker/electrolineras
docker compose -f docker-compose.prod.yml up -d --build
```

## Targets Makefile (#6038)

```bash
make docker-sync-prod   # copia compose + env.example al mini PC
make docker-build       # build api + nginx (compose prod)
make docker-up          # arranca stack prod
make docker-down        # para stack prod
```

## Cron de ingestión (#6040)

La API en Docker **no** ejecuta ingestiones. Programar en el **host** (mismo volumen `electrolineras-data`):

```bash
cd /mnt/datos/Proyectos/Electrolineras
make cron-install          # crea scripts/cron/electrolineras.env si falta
crontab -e                 # pegar scripts/cron/electrolineras.crontab.example

# Probar manualmente
make cron-test-reve
tail -f /mnt/datos/docker/volumes/electrolineras-data/logs/cron/ingest-reve.log
```

| Job | Frecuencia | Comando |
|-----|------------|---------|
| NAP España | Diario 06:15 | `run_scheduled_job.sh es` |
| NAP Portugal | Cada 6 h | `run_scheduled_job.sh pt` |
| REVE dinámico | Cada 3 h | `run_scheduled_job.sh reve` |

Detalle: [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md#5-cron-de-ingestión-producción-6040).
