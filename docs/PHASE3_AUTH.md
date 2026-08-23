# Autenticación zona privada (TOTP multiusuario)

Última actualización: 2026-08-23

## Modelo

Un solo sitio (`electro.jualas.es`), un solo Docker:

- **Mapa / plan de carga / planificador de ruta** → sin login (públicos).
- **Pestaña Asistente** (coche real vía TeslaMate) → usuario + código TOTP
  (Microsoft Authenticator u otra app compatible).
- **Multiusuario**: cada persona tiene su propio usuario y su propio secreto
  TOTP (un código de Authenticator distinto por miembro de la familia), no una
  cuenta compartida. `PRIVATE_AUTH_USERS` guarda `usuario:SECRETO` por persona,
  separados por comas.
- Sesión en cookie `httpOnly` (7 días por defecto); recuerda qué usuario inició sesión.
- **Dify / Cursor CLI** → opcional `PRIVATE_API_TOKEN` (Bearer) sin TOTP.

Compatible con [Microsoft Authenticator](https://www.microsoft.com/security/mobile-authenticator-app): escaneas la clave TOTP al configurar (RFC 6238), igual que Tesla/Meta en modo «otra cuenta».

## Configuración inicial

Añadir un usuario (uno por miembro de la familia):

```bash
cd /mnt/datos/Proyectos/Electrolineras
PYTHONPATH=src .venv/bin/python scripts/auth/setup_private_auth.py \
  --username <nombre> --apply /mnt/datos/docker/electrolineras/.env
```

(Si no existe `.venv`: `python3 -m venv .venv && .venv/bin/pip install -e .`)

1. Repite el comando con `--username` distinto para cada persona; `--apply`
   añade cada una a `PRIVATE_AUTH_USERS` sin borrar las demás.
2. El script genera un PNG escaneable (`img/totp-setup-qr.png` por defecto).
   Requiere `qrencode` en el sistema (`sudo apt install qrencode`).
3. `PYTHONPATH=src .venv/bin/python scripts/auth/setup_private_auth.py --list --apply <.env>`
   lista los usuarios ya configurados.
4. Si algo quedó duplicado: `PYTHONPATH=src .venv/bin/python scripts/auth/dedupe_env_auth.py`

**Regenerar solo el QR** de un usuario existente (sin cambiar su secreto):

```bash
PYTHONPATH=src .venv/bin/python scripts/auth/show_totp_qr.py --username <nombre> --env-file <.env>
# Microsoft Authenticator → Agregar cuenta → Otra cuenta → Escanear código QR
```

Producción:

```env
PRIVATE_STACK_ENABLED=true
SESSION_SECRET=<del script>
SESSION_COOKIE_SECURE=true
PRIVATE_AUTH_USERS=usuario1:SECRETO1,usuario2:SECRETO2
CHARGING_AGENT_ENABLED=true
```

`PRIVATE_AUTH_USERNAME` / `PRIVATE_TOTP_SECRET` son el formato mono-usuario
anterior; se mantienen como *fallback* solo si `PRIVATE_AUTH_USERS` está vacío.
`PRIVATE_AUTH_PASSWORD_HASH` ya no se usa (login solo usuario + TOTP). Puedes
borrarlo del `.env` si quedó de una instalación antigua.

Reinicia el contenedor:

```bash
cd /mnt/datos/docker/electrolineras && docker compose up -d --build electrolineras
```

## API

| Método | Ruta | Auth |
|--------|------|------|
| GET | `/api/v1/auth/config` | Pública |
| GET | `/api/v1/auth/session` | Pública |
| POST | `/api/v1/auth/login` | Body: `username`, `totp_code` |
| POST | `/api/v1/auth/logout` | Cookie |
| GET | `/api/v1/private/*` | Cookie sesión o Bearer token |

## Publicar en GitHub

Incluir en el repo:

- Código auth (`src/api/auth/`, rutas `/auth`)
- `scripts/auth/setup_private_auth.py`
- Esta documentación

**No commitear:** `.env`, hashes, `PRIVATE_TOTP_SECRET`.

Cada usuario self-hosted genera su propio TOTP y nombre de usuario.

## Referencias

- [`PHASE3_PRIVATE_STACK.md`](PHASE3_PRIVATE_STACK.md) — TeslaMate y arquitectura
- [`CHARGING_AGENT.md`](CHARGING_AGENT.md) — agente IA
