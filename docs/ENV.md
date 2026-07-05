# Variables de entorno y secretos (#6043)

Guía de configuración **desarrollo vs producción**, plantillas sin secretos y buenas prácticas en el mini PC / VPS.

## Plantillas (versionadas en git)

| Fichero | Uso |
|---------|-----|
| [`.env.example`](../.env.example) | Desarrollo local (`cp .env.example .env`) |
| [`.env.production.example`](../.env.production.example) | Producción systemd / referencia API |
| [`docker/env.example`](../docker/env.example) | Docker Compose en `/mnt/datos/docker/electrolineras/` |
| [`scripts/cron/electrolineras.env.example`](../scripts/cron/electrolineras.env.example) | Cron ingest, backups, monitoring (host) |

**Nunca commitear:** `.env`, `electrolineras.env`, tokens reales, hashes TOTP, claves Dify/OCM/TeslaMate.

## Ficheros secretos en el mini PC

| Ruta | Contenido | Permisos |
|------|-----------|----------|
| `/mnt/datos/docker/electrolineras/.env` | API Docker + Cloudflare + stack privado | `600` |
| `scripts/cron/electrolineras.env` | Cron, webhooks ntfy, backups | `600` |
| `.env` (repo, solo dev) | SQLite local, Vite | `600` recomendado |

Aplicar permisos:

```bash
make env-secure
# o rutas concretas:
bash scripts/env/secure_env_permissions.sh /mnt/datos/docker/electrolineras/.env
```

Validar antes de desplegar:

```bash
make env-check-prod ENV_FILE=/mnt/datos/docker/electrolineras/.env
```

## Desarrollo vs producción

| Variable | Desarrollo (`.env.example`) | Producción |
|----------|----------------------------|------------|
| `API_ENVIRONMENT` | `development` | `production` |
| `API_RELOAD` | `true` | `false` |
| `API_CORS_ORIGINS` | `localhost:5173` | `https://electro.jualas.es` (+ LAN opcional) |
| `SERVE_WEB_STATIC` | `false` (Vite dev) | `true` (SPA en FastAPI) |
| `VITE_API_URL` | `http://127.0.0.1:8000` | **vacío** en build (`same-origin`) |
| `SESSION_COOKIE_SECURE` | `false` | `true` (HTTPS vía túnel) |
| `API_TRUST_PROXY_HEADERS` | `false` | `true` (Cloudflare) |

## Variables obligatorias (API en producción)

| Variable | Por qué |
|----------|---------|
| `DATABASE_URL` | SQLite en volumen (`sqlite:////app/data/db/stations.db` en Docker) |
| `API_CORS_ORIGINS` | Origen público del frontend; sin `*` |
| `OSRM_BASE_URL` | Routing; en prod usar OSRM self-hosted (#6037) |
| `NOMINATIM_USER_AGENT` | Identificar la app (email/URL de contacto) |
| `NOMINATIM_BASE_URL` (prod) | Instancia LAN — ver [`NOMINATIM.md`](NOMINATIM.md) |
| `API_ENVIRONMENT=production` | Activa hardening (#6042) |
| `API_RELOAD=false` | Sin recarga en caliente en prod |

### Routing OSRM (planificador / corredor)

Desempate fastest, tipos de ruta y convencionales: [`ROUTE_CORRIDOR_SEARCH.md`](ROUTE_CORRIDOR_SEARCH.md#tipos-de-ruta-osrm-planificador-y-en-ruta).

| Variable | Prod típico | Notas |
|----------|-------------|-------|
| `OSRM_USE_MULTI_PROFILE` | `true` | Perfiles separados fastest / shortest / conventional |
| `OSRM_FASTEST_REQUEST_ALTERNATIVES` | `true` | Alternativas OSRM para desempate fastest |
| `OSRM_FASTEST_ALTERNATIVE_TOLERANCE` | `0.05` | ±5 % sobre min tiempo; calibración #6069 |
| `OSRM_SHORTEST_DIRECTNESS_PENALTY` | `0.35` | Penaliza desvío vs geodesic en shortest |

### Frontend (build)

En producción, el build Vite debe usar **origen relativo**:

```bash
cd src/web
VITE_API_URL= npm run build
```

O dejar `VITE_API_URL` vacío en el entorno del build. El cliente llama `/api/v1/...` en el mismo dominio.

## Secretos opcionales (según features)

Generar stack privado (TOTP + sesión):

```bash
.venv/bin/python scripts/auth/setup_private_auth.py
```

| Variable | Cuándo |
|----------|--------|
| `SESSION_SECRET` | `PRIVATE_STACK_ENABLED=true` |
| `PRIVATE_AUTH_PASSWORD_HASH` | Login TOTP; en Docker **duplicar `$` → `$$`** |
| `PRIVATE_TOTP_SECRET` | Microsoft Authenticator |
| `PRIVATE_API_TOKEN` | Automatización / agente |
| `DIFY_TRIP_WORKFLOW_API_KEY` | Guía IA (solo LAN) |
| `CLOUDFLARED_TOKEN` | Túnel Cloudflare |
| `TESLAMATE_MQTT_PASSWORD` | Telemetría coche |
| `OCM_API_KEY` | Sync Open Charge Map (cron) |
| `INGEST_WEBHOOK_URL` | Alertas ntfy (cron, no API) |

Detalle auth: [`PHASE3_AUTH.md`](PHASE3_AUTH.md).

## Rotación de secretos

1. Generar nuevos valores (`setup_private_auth.py`, tokens en consolas Dify/Cloudflare).
2. Actualizar `.env` / `electrolineras.env`.
3. `make env-check-prod` + `make env-secure`.
4. `docker compose up -d --build electrolineras` (si aplica).
5. Invalidar sesiones antiguas (cambio de `SESSION_SECRET`).

## Errores frecuentes

| Síntoma | Causa | Solución |
|---------|-------|----------|
| Login TOTP siempre falla | Hash bcrypt truncado | Duplicar `$` en `.env` Docker |
| CORS en prod | Origen incorrecto | Añadir `https://electro.jualas.es` |
| OSRM timeout | URL pública saturada | OSRM local en compose OSRM |
| `.env.production.example` no en git | `.gitignore` | Ya corregido con `!.env.production.example` |

## Referencias

- Despliegue: [`DEPLOYMENT.md`](DEPLOYMENT.md)
- Hardening API: [`DEPLOYMENT.md` §8](DEPLOYMENT.md#8-hardening-api-6042)
- Docker: [`docker/README.md`](../docker/README.md)
