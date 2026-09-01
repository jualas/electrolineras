# Entorno de staging (pruebas antes de producción)

Última actualización: 2026-09-01 · rama `feature/viaje-activo-6131` · TaskBoard **#6141** / smoke **#6143**

## Por qué existe

Prod (`https://electro.jualas.es` → `:8015`) debe quedarse estable. Staging permite validar una rama (p. ej. viaje activo, fix de tramos) **sin tocar prod**.

| Entorno | URL | Puerto | Compose | Cuándo |
|---------|-----|--------|---------|--------|
| **Dev Vite** | `http://127.0.0.1:5173` | 5173 | — | UI rápida; API en `:8000` |
| **Staging** | `http://127.0.0.1:8016` (LAN `<IP-LAN-SERVIDOR>:8016`) | **8016** | `docker-compose.staging.yml` | Probar build Docker + motor + UI como en prod |
| **Prod** | `https://electro.jualas.es` | **8015** | `docker-compose.prod.yml` | Solo tras validar en staging |

> Lo que antes se usaba como “prueba” en **`:5173`** sigue siendo el modo desarrollo (hot reload). Staging es el **mismo tipo de stack que prod**, en paralelo.

## Arquitectura

```text
feature branch (working tree)
        │
        ▼
 deploy-staging.sh ──► electrolineras-staging-api
                   ──► electrolineras-staging-nginx :8016
                   ──► BD copia en volumes/electrolineras-staging-data
                   ──► OSRM / Nominatim compartidos con prod
```

- **No** despliega cloudflared (prod sigue con el túnel actual).
- Contenedores y volúmenes **separados** de prod.
- Alias de red `electrolineras-api` para reutilizar el nginx conf.

## Arranque / actualización

Desde la rama a probar (ej. `feature/viaje-activo-6131`):

```bash
cd /mnt/datos/Proyectos/Electrolineras
git status   # confirma la rama
make deploy-staging
```

Refrescar `stations.db` desde prod antes del build:

```bash
STAGING_REFRESH_DB=1 make deploy-staging
```

Smoke:

```bash
curl -s http://127.0.0.1:8016/health
curl -s 'http://127.0.0.1:8016/api/v1/meta/stats' | head -c 200
```

En el móvil / Tesla (WiFi casa): **http://<IP-LAN-SERVIDOR>:8016**

## Flujo recomendado (feature → prod)

1. Desarrollar en rama `feature/…` (no en `develop` si hay riesgo).
2. `make test` / pytest en local.
3. **`make deploy-staging`** y checklist manual (abajo).
4. Si OK → merge PR a `develop`.
5. **`make deploy`** (prod `:8015` / electro.jualas.es).
6. Smoke prod + marcar TaskBoard.

## Auth / cookies

Staging usa **HTTP** (`:8016`). En `docker-compose.staging.yml` se fuerza
`SESSION_COOKIE_SECURE=false` para que el navegador guarde `electrolineras_session`.
Prod (`https://electro.jualas.es`) mantiene `SESSION_COOKIE_SECURE=true` en su `.env`.

## Checklist smoke staging (Cartagena → Irun)

Última ejecución automática: **2026-09-01** en `:8016` (rama `feature/viaje-activo-6131`, commit desplegado con `make deploy-staging`).

| Check | Resultado | Notas |
|-------|-----------|-------|
| Health 200 en `:8016` | ✅ | `curl -sf http://127.0.0.1:8016/health` |
| Prod `:8015` intacto | ✅ | Health 200 en paralelo |
| Rápida: duraciones Directa vs Rápida | ✅ | Directa 699 min / 748 km · Rápida 608 min / 918 km |
| Rápida: tramos ~2 h (no ~1 h 20 en 2.º) | ✅ | Tramos 175 / **102** / 110 / 124 min (4 paradas) |
| Directa: plan con paradas | ✅ | 1 parada DC (no plan vacío) |
| Login TOTP + sesión | ⬜ manual | Probar en `http://<IP-LAN-SERVIDOR>:8016` |
| «Abrir en Google Maps» con waypoints | ⬜ manual | UI Plan de carga |
| Viaje activo / replan / mapa GPS | ⬜ manual | #6131 — móvil en LAN |

Repetir smoke API (sin UI):

```bash
curl -sf http://127.0.0.1:8016/health
curl -sf 'http://127.0.0.1:8016/api/v1/stations/charging-plan?origin_lat=37.625&origin_lon=-0.996&dest_lat=43.34&dest_lon=-1.79&soc_percent=80&usable_capacity_kwh=60&consumption_wh_per_km=170&terrain_factor=1&reserve_soc_percent=10&min_kw=100&corridor_km=10&limit=15&vehicle_preset_id=tesla_model_3_lr&route_preference=fastest&max_charge_power_kw=150&min_destination_soc_pct=10&min_stop_arrival_soc_pct=10&max_charge_soc_pct=80' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print(d['route_fastest_duration_minutes'],d['route_shortest_duration_minutes'],len(d.get('planned_stops')or[]))"
```

Criterio rápido: `route_fastest_duration_minutes` &lt; `route_shortest_duration_minutes` y `len(planned_stops) >= 1` en **fastest** y **shortest**.

## Alternativa rápida: solo Vite `:5173`

Para UI sin rebuild Docker:

```bash
# Terminal A — API de la rama
make api          # :8000

# Terminal B — frontend hot reload
make web          # :5173
```

Abrir `http://127.0.0.1:5173`. El proxy manda `/api` a `:8000`.  
**No** sustituye staging: no valida imagen nginx ni compose.

## Cloudflare (opcional) — `electro-test.jualas.es`

Para HTTPS público sin tocar prod:

1. Zero Trust → Public Hostname `electro-test.jualas.es` → `http://127.0.0.1:8016`
2. CORS staging ya incluye ese origen en `docker-compose.staging.yml`
3. TaskBoard: subtarea bajo epic #6141

## Operación

| Acción | Comando |
|--------|---------|
| Deploy / rebuild staging | `make deploy-staging` |
| Logs API | `docker logs -f electrolineras-staging-api` |
| Parar staging | `make docker-staging-down` |
| Estado | `docker ps --filter name=electrolineras-staging` |
| Estado fichero | `/mnt/datos/docker/electrolineras/.deploy-state-staging` |

## Qué no hacer

- No apuntar el túnel de **electro.jualas.es** a `:8016`.
- No usar el volumen de datos de **prod** como escritura concurrente desde staging (SQLite).
- No hacer `make deploy` (prod) hasta validar en staging.
