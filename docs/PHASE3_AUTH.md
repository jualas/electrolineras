# Autenticación de la app (TOTP multiusuario)

Última actualización: 2026-08-21

## Modelo

Un solo sitio (`electro.jualas.es`), un solo Docker, de uso familiar:

- **Toda la API** (`/api/v1/*`, salvo `/api/v1/auth/*`) exige sesión cuando
  `PRIVATE_STACK_ENABLED=true`: mapa, búsqueda de estaciones, plan de carga,
  planificador de ruta y la pestaña Asistente por igual.
- El **HTML/JS estático del SPA sigue sirviéndose sin login** — la pantalla de
  inicio de sesión vive dentro de la propia aplicación (React), no a nivel de
  servidor de ficheros. Cualquiera puede cargar la página, pero ninguna llamada a
  la API funciona sin sesión.
- `/health` queda siempre público (healthcheck de Docker).
- **Multiusuario**: cada persona tiene su propio usuario y su propio secreto TOTP
  (un código de Authenticator distinto por miembro de la familia), no una cuenta
  compartida.
- Sesión en cookie `httpOnly` (7 días por defecto), la cookie recuerda qué usuario
  inició sesión.
- **Dify / Cursor CLI** → opcional `PRIVATE_API_TOKEN` (Bearer) sin TOTP, válido
  para toda la API igual que una sesión de usuario.

Compatible con [Microsoft Authenticator](https://www.microsoft.com/security/mobile-authenticator-app)
y cualquier app TOTP estándar (Google Authenticator, Authy, etc.): escaneas la
clave TOTP al configurar (RFC 6238), igual que Tesla/Meta en modo «otra cuenta».

## Configuración inicial

Añadir el primer usuario (o uno más) al `.env` de producción:

```bash
cd /mnt/datos/Proyectos/Electrolineras
PYTHONPATH=src .venv/bin/python scripts/auth/setup_private_auth.py \
  --username <nombre> --apply /mnt/datos/docker/electrolineras/.env
```

(Si no existe `.venv`: `python3 -m venv .venv && .venv/bin/pip install -e .`)

1. `--username` es obligatorio y distinto para cada miembro de la familia.
2. El script **añade** el usuario a `PRIVATE_AUTH_USERS` sin tocar a los demás ya
   configurados. Si el usuario ya existe, falla salvo que pases `--replace`
   (regenera su código, invalida el QR anterior).
3. Genera un PNG escaneable por usuario (`img/totp-setup-qr-<usuario>.png` por
   defecto). Requiere `qrencode` en el sistema (`sudo apt install qrencode`).
4. Reinicia el contenedor tras aplicar:
   `cd /mnt/datos/docker/electrolineras && docker compose up -d --force-recreate electrolineras-api`

Repite el comando (con un `--username` distinto) por cada miembro de la familia.

**Ver quién está configurado** sin exponer secretos:

```bash
PYTHONPATH=src .venv/bin/python scripts/auth/setup_private_auth.py \
  --list --apply /mnt/datos/docker/electrolineras/.env
```

**Regenerar solo el QR** de un usuario concreto (sin cambiar su secreto):

```bash
./scripts/auth/show_totp_qr.sh --username <nombre>
# → img/totp-authenticator-qr-<nombre>.png
# Authenticator → Agregar cuenta → Otra cuenta → Escanear código QR
```

Variables resultantes en `.env`:

```env
PRIVATE_STACK_ENABLED=true
SESSION_SECRET=<del script, una sola vez>
SESSION_COOKIE_SECURE=true
PRIVATE_AUTH_USERS=juan:ABCD...,maria:EFGH...,...
PRIVATE_API_TOKEN=<del script, una sola vez>
CHARGING_AGENT_ENABLED=true
```

`PRIVATE_AUTH_USERNAME` / `PRIVATE_TOTP_SECRET` / `PRIVATE_AUTH_PASSWORD_HASH` son
el formato mono-usuario anterior; ya no los escribe el script, pero si quedan de
una instalación antigua siguen funcionando como fallback mientras
`PRIVATE_AUTH_USERS` esté vacío.

## API

| Método | Ruta | Auth |
|--------|------|------|
| GET | `/api/v1/auth/config` | Pública |
| GET | `/api/v1/auth/session` | Pública |
| POST | `/api/v1/auth/login` | Body: `username`, `totp_code` |
| POST | `/api/v1/auth/logout` | Cookie |
| GET | `/health` | Pública |
| Resto de `/api/v1/*` (estaciones, ruta, plan de carga, asistente, privado) | Cookie de sesión o Bearer token (`PRIVATE_API_TOKEN`/`AGENT_API_TOKEN`) cuando `PRIVATE_STACK_ENABLED=true`; sin restricción si está en `false` |

## Publicar en GitHub

Incluir en el repo:

- Código auth (`src/api/auth/`, rutas `/auth`)
- `scripts/auth/setup_private_auth.py`
- Esta documentación

**No commitear:** `.env`, `PRIVATE_AUTH_USERS` (contiene los secretos TOTP de
todos los usuarios).

Cada instalación self-hosted genera sus propios usuarios y secretos TOTP.

## Referencias

- [`PHASE3_PRIVATE_STACK.md`](PHASE3_PRIVATE_STACK.md) — TeslaMate y arquitectura
- [`CHARGING_AGENT.md`](CHARGING_AGENT.md) — agente IA
