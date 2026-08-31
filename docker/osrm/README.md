# OSRM — Electrolineras

Dos grafos sobre mapa Geofabrik **Iberia** (ES+PT):

| Servicio | Perfil | Uso |
|----------|--------|-----|
| `:5000` `car` | `car.lua` | **Rápida** (tiempo) y **convencionales** (`exclude=motorway`) |
| `:5001` `shortest` | `shortest.lua` | **Directa** (minimiza km / rectitud) |

## Build (una vez, ~30–90 min)

```bash
./scripts/osrm/build_iberia.sh
```

Requisitos: Docker, ~8 GB RAM en el pico, ~25 GB disco en `OSRM_DATA_DIR`.

Descarga Geofabrik **España + Portugal** (fusionados con osmium) — no existe extract `iberia-latest` en Geofabrik.

## Arrancar

```bash
cd docker/osrm
docker compose up -d
```

Los servicios llevan `restart: unless-stopped`. Tras un reboot del mini PC deben
levantar solos con Docker. Si la política no está aplicada (p. ej. contenedores
antiguos):

```bash
make osrm-enable-boot
```

Opcional — oneshot systemd por si el compose quedó desincronizado:

```bash
make osrm-install-systemd
# o a mano:
sudo cp scripts/osrm/electrolineras-osrm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now electrolineras-osrm.service
```

Comprobar:

```bash
make osrm-status
# esperado: restart=unless-stopped
```

> Nota: el grafo Iberia tarda ~2–3 min en cargar en memoria tras el arranque;
> hasta entonces la API puede devolver error de routing.

## Activar en Electrolineras

En `/mnt/datos/docker/electrolineras/.env`:

```env
OSRM_BASE_URL=http://host.docker.internal:5000
OSRM_SHORTEST_BASE_URL=http://host.docker.internal:5001
OSRM_USE_MULTI_PROFILE=true
OSRM_PROFILE_FASTEST=car
OSRM_PROFILE_SHORTEST=shortest
OSRM_PROFILE_CONVENTIONAL=car
```

Reinicia la app: `docker compose up -d --build`
