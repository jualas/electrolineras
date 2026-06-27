# Docker — Electrolineras

Despliegue en el mini PC bajo `/mnt/datos/docker/electrolineras/`.

## Primera vez

```bash
# Datos persistentes
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/db
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/raw/es
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/raw/pt
mkdir -p /mnt/datos/docker/volumes/electrolineras-data/processed

# Copiar DB inicial si el volumen está vacío
if [ ! -f /mnt/datos/docker/volumes/electrolineras-data/db/stations.db ]; then
  cp /mnt/datos/Proyectos/Electrolineras/data/db/stations.db \
    /mnt/datos/docker/volumes/electrolineras-data/db/stations.db
fi

# Config despliegue
mkdir -p /mnt/datos/docker/electrolineras
cp /mnt/datos/Proyectos/Electrolineras/docker/docker-compose.yml \
   /mnt/datos/docker/electrolineras/docker-compose.yml
cp /mnt/datos/Proyectos/Electrolineras/docker/env.example \
   /mnt/datos/docker/electrolineras/env.example
cd /mnt/datos/docker/electrolineras
cp env.example .env
# Editar .env (CORS, dominio, token Cloudflare)

docker compose up -d --build
```

## Verificación

```bash
curl -s http://127.0.0.1:8015/health
curl -s http://127.0.0.1:8015/api/v1/meta/stats | head -c 200
```

Web: http://127.0.0.1:8015

## Cloudflare Tunnel

En Zero Trust, public hostname `electro.jualas.es` → `http://127.0.0.1:8015`

O activar el servicio `electrolineras-cloudflared` en `docker-compose.yml` con `CLOUDFLARED_TOKEN`.

## Actualizar tras cambios en el repo

```bash
cd /mnt/datos/docker/electrolineras
docker compose up -d --build
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
