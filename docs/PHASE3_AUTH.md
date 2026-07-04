# Autenticación zona privada (TOTP)

Última actualización: 2026-06-23

## Modelo

Un solo sitio (`electro.jualas.es`), un solo Docker:

- **Mapa / plan manual** → sin login.
- **Pestaña Asistente** → contraseña + código TOTP (Microsoft Authenticator).
- Sesión en cookie `httpOnly` (7 días por defecto).
- **Dify / Cursor CLI** → opcional `PRIVATE_API_TOKEN` (Bearer) sin TOTP.

Compatible con [Microsoft Authenticator](https://www.microsoft.com/security/mobile-authenticator-app): escaneas la clave TOTP al configurar (RFC 6238), igual que Tesla/Meta en modo «otra cuenta».

## Configuración inicial

```bash
cd /mnt/datos/Proyectos/Electrolineras
./scripts/auth/setup_private_auth.sh
```

(El script usa `.venv` del proyecto; si no existe: `python3 -m venv .venv && .venv/bin/pip install -e .`)

Alternativa manual:

```bash
PYTHONPATH=src .venv/bin/python scripts/auth/setup_private_auth.py
```

1. Introduce contraseña (≥8 caracteres).
2. Copia las líneas al `.env` de producción (`/mnt/datos/docker/electrolineras/.env`).
3. **Sustituye** las variables existentes; no pegues un segundo bloque (docker-compose usa la última línea y el Authenticator quedaría desincronizado).
4. El script ya escapa el hash bcrypt para **docker-compose** (`$` → `$$`). Si pegas un hash manual, duplica cada `$`.
5. Si duplicaste por error: `PYTHONPATH=src .venv/bin/python scripts/auth/dedupe_env_auth.py`

Producción:

```env
PRIVATE_STACK_ENABLED=true
SESSION_SECRET=<del script>
SESSION_COOKIE_SECURE=true
PRIVATE_AUTH_PASSWORD_HASH=<del script — con $$ si pegas manualmente>
PRIVATE_TOTP_SECRET=<del script>
CHARGING_AGENT_ENABLED=true
```

Ejemplo de hash en `.env` docker-compose (nota los `$$`):

```env
PRIVATE_AUTH_PASSWORD_HASH=$$2b$$12$$abcdefghijklmnopqrstuvwxYz012345678901234567890
```

Reinicia el contenedor:

```bash
cd /mnt/datos/docker/electrolineras && docker compose up -d --build electrolineras
```

## API

| Método | Ruta | Auth |
|--------|------|------|
| GET | `/api/v1/auth/config` | Pública |
| GET | `/api/v1/auth/session` | Pública |
| POST | `/api/v1/auth/login` | Body: `password`, `totp_code` |
| POST | `/api/v1/auth/logout` | Cookie |
| GET | `/api/v1/private/*` | Cookie sesión o Bearer token |

## Publicar en GitHub

Incluir en el repo:

- Código auth (`src/api/auth/`, rutas `/auth`)
- `scripts/auth/setup_private_auth.py`
- Esta documentación

**No commitear:** `.env`, hashes, `PRIVATE_TOTP_SECRET`.

Cada usuario self-hosted genera su propio TOTP y contraseña.

## Referencias

- [`PHASE3_PRIVATE_STACK.md`](PHASE3_PRIVATE_STACK.md) — TeslaMate y arquitectura
- [`CHARGING_AGENT.md`](CHARGING_AGENT.md) — agente IA
