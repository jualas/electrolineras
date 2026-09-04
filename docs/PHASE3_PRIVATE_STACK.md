# Fase 3 — Stack privado (IA + TeslaMate)

Última actualización: 2026-06-23

## Objetivo

Separar dos mundos:

| Zona | Quién | Qué |
|------|-------|-----|
| **Pública** | Cualquiera | Mapa, estaciones, plan de carga manual (SOC + GPS móvil) |
| **Privada** | Solo tú (inicialmente) | Agente IA, telemetría del coche, plan desde el vehículo |

La telemetría **no pasa por Tesla Fleet API** en esta fase: reutilizamos **TeslaMate** (ya autenticado con tu cuenta Tesla en tu mini PC) y **TeslaMateApi** como bridge REST — el mismo patrón que MateDroid y otros proyectos de la comunidad.

## Arquitectura recomendada (mini PC)

```mermaid
flowchart TB
  subgraph public [Zona pública]
    WEB[electro.jualas.es]
    MAP[Mapa + plan manual]
  end

  subgraph edge [Borde]
    CF[Cloudflare Tunnel + Access]
  end

  subgraph private [Zona privada — solo tú]
    PRIV[electro-private.jualas.es o /private]
    API_PRIV[/api/v1/private/*]
    API_AGENT[/api/v1/agent/*]
    DIFY[Dify LAN]
    CURSOR[Cursor CLI]
  end

  subgraph vehicle [Telemetría — nunca expuesta al navegador]
  TM[TeslaMate]
  TMAPI[TeslaMateApi]
  end

  WEB --> MAP
  CF --> WEB
  CF -->|Zero Trust email| PRIV
  PRIV --> API_PRIV
  DIFY --> API_AGENT
  CURSOR --> API_AGENT
  API_PRIV --> TMAPI
  TMAPI --> TM
  TM -->|OAuth Tesla ya hecho| TESLA[Cuenta Tesla]
```

## Capas de seguridad (defensa en profundidad)

### 1. Red y dominio (recomendado)

- **Mapa público:** `https://electro.jualas.es` — sin cambios.
- **Stack privado:** subdominio distinto, p. ej. `https://electro-private.jualas.es`, o ruta `/private/*` en Cloudflare Access.
- **Cloudflare Zero Trust:** política «Allow» solo tu email (o grupo «familia»). Nadie más ve la UI privada ni puede abrir Dify desde fuera sin pasar Access.

### 2. Login TOTP en la app (implementado)

Contraseña + código de 6 dígitos (Microsoft Authenticator). Ver [`PHASE3_AUTH.md`](PHASE3_AUTH.md).

| Header | Uso |
|--------|-----|
| Cookie de sesión | Navegador / Tesla (tras login) |
| `Authorization: Bearer <token>` | Dify / Cursor CLI (opcional) |

Variables:

```env
PRIVATE_STACK_ENABLED=true
PRIVATE_API_TOKEN=<mín. 32 caracteres, generar con openssl rand -hex 32>
AGENT_API_TOKEN=          # opcional; si vacío, usa PRIVATE_API_TOKEN
CHARGING_AGENT_ENABLED=true
```

**Nunca** poner estos tokens en el frontend público ni en `VITE_*`.

## TeslaMate / telemetría del coche

Guía detallada en el mini PC: **`/mnt/datos/docker/teslamate/INTEGRACION_APPS.md`**

Electrolineras **no duplica OAuth Tesla**; lee lo que TeslaMate ya recoge (Fleet API vía `ship.jualas.es`).

### Opción recomendada — MQTT (tiempo real)

Mismos parámetros que TeslaMate (`MQTT_HOST`, usuario `jualas`, car_id `1`):

```env
TESLAMATE_DATA_SOURCE=auto
TESLAMATE_CAR_ID=1
TESLAMATE_CAR_DISPLAY_NAME=The Ship
TESLAMATE_MQTT_HOST=<IP-LAN-SERVIDOR>
TESLAMATE_MQTT_PORT=1883
TESLAMATE_MQTT_USERNAME=jualas
TESLAMATE_MQTT_PASSWORD=<igual que MQTT_PASSWORD en teslamate/.env>
TESLAMATE_MQTT_TOPIC_PREFIX=teslamate/cars
# Consumo y capacidad reales (The Ship: cars.efficiency + cargas)
TESLAMATE_EFFICIENCY_KWH_PER_KM=0.13733
TESLAMATE_USABLE_CAPACITY_KWH=57.5
```

`TESLAMATE_EFFICIENCY_KWH_PER_KM` es el valor de `cars.efficiency` en PostgreSQL TeslaMate (kWh/km → ×1000 = Wh/km). El planificador `trip-*-from-car` lo usa como consumo base; el campo REVE `consumption_kwh_per_100km` solo lo sobrescribe si el usuario lo rellena a mano.

Probar broker:

```bash
mosquitto_sub -h <IP-LAN-SERVIDOR> -u jualas -P '...' -t 'teslamate/cars/1/#' -v
```

### Opción alternativa — TeslaMateApi (REST)

Solo si añades el contenedor `teslamateapi` al stack (ver INTEGRACION_APPS.md § Opción 3):

```env
TESLAMATE_API_BASE_URL=http://<IP-LAN-SERVIDOR>:8080
TESLAMATE_API_TOKEN=<API_TOKEN del contenedor>
```

Con `TESLAMATE_DATA_SOURCE=auto`, si MQTT falla se intenta la API.

### 4. Dify y Cursor CLI

- **Dify solo en LAN del minipc** (sin túnel): consola `http://<IP-LAN-SERVIDOR>:8590`, API workflow `http://<IP-LAN-SERVIDOR>:8590/v1`. Electrolineras llama a Dify desde el contenedor con `DIFY_API_BASE_URL` (ver [`DIFY_TRIP_GUIDE.md`](DIFY_TRIP_GUIDE.md)).
- Nodos HTTP en Dify hacia Electrolineras: `Authorization: Bearer $PRIVATE_API_TOKEN` o `X-Private-Token`.
- Cursor CLI: `AGENT_API_TOKEN` o `PRIVATE_API_TOKEN` en el script (`scripts/agent/trip_advice.sh`).
- El LLM **no calcula** SOC; solo narra JSON del motor ([`CHARGING_AGENT.md`](CHARGING_AGENT.md)).

## Endpoints privados

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/private/status` | Estado del stack privado |
| GET | `/api/v1/private/vehicle/state` | Posición + SOC vía TeslaMate |
| GET | `/api/v1/private/trip-advice-from-car` | Plan de carga: origen/SOC del coche + destino |
| GET | `/api/v1/private/trip-guide-from-car` | Plan + guía IA (Dify LAN o fallback local) |
| GET | `/api/v1/agent/trip-advice` | Plan + narrativa (requiere token si privado activo) |
| GET | `/api/v1/agent/score-charging-plan` | Alias Dify |

Ejemplo — plan desde el coche:

```bash
curl -fsS \
  -H "Authorization: Bearer $PRIVATE_API_TOKEN" \
  "http://127.0.0.1:8015/api/v1/private/trip-advice-from-car?dest_lat=40.35&dest_lon=-1.10&terrain_factor=1.25&local_mobility_km=50"
```

## Uso en el navegador Tesla

1. Abres `electro-private.jualas.es` (tras Cloudflare Access con tu cuenta).
2. La UI privada llama a `/api/v1/private/*` con sesión o token de corta duración (futuro #6058).
3. Origen y SOC vienen de TeslaMate, no del GPS del navegador (más fiable en el coche).
4. El mapa público sigue disponible en `electro.jualas.es` sin login.

## Publicar en GitHub para otros usuarios

Patrón alineado con TeslaMate (cada uno self-hosted):

| Publicar en el repo | No publicar |
|---------------------|-------------|
| Cliente `api/integrations/teslamate.py` | `.env`, tokens |
| `docs/PHASE3_PRIVATE_STACK.md` | `PRIVATE_API_TOKEN` |
| `docker-compose` ejemplo con TeslaMateApi | Tokens TeslaMateApi |
| Variables en `.env.example` | Cloudflare tokens |

Cada usuario:

1. Instala **TeslaMate** + vincula su cuenta Tesla (como ya hace la comunidad).
2. Añade **TeslaMateApi** con su `API_TOKEN`.
3. Configura Electrolineras con `TESLAMATE_API_*` + `PRIVATE_API_TOKEN`.
4. Opcional: Cloudflare Access con su email.

No necesitamos reimplementar OAuth Tesla en Electrolineras: TeslaMate ya lo resuelve. Nuestro valor es **plan de carga peninsular + agente + recomendación de SOC en destino**.

Referencia comunidad: [Projects using TeslaMate](https://docs.teslamate.org/docs/projects/).

## Docker — conectar con tu TeslaMate existente

Si TeslaMate ya corre en el mini PC, en `docker-compose` de Electrolineras:

```yaml
services:
  electrolineras:
    environment:
      PRIVATE_STACK_ENABLED: "true"
      TESLAMATE_API_BASE_URL: "http://teslamateapi:8080"
    networks:
      - default
      - teslamate_default   # red donde está TeslaMateApi
```

O URL host: `http://<IP-LAN-SERVIDOR>:8080` si TeslaMateApi expone puerto en LAN (menos recomendable que red Docker interna).

## Roadmap

| Paso | Tarea |
|------|-------|
| ✅ | Token privado + cliente TeslaMateApi + endpoints |
| ⏳ | Cloudflare Access en subdominio privado |
| ⏳ | UI privada en Tesla (#6058) con sesión tras Access |
| ⏳ | Workflow Dify (#6057) |
| Futuro | OAuth multi-usuario si quieres abrir a amigos (cada uno su TeslaMate) |

## Referencias

- [`CHARGING_AGENT.md`](CHARGING_AGENT.md) — agente y narrativa
- [`EV_RANGE_PLAN.md`](EV_RANGE_PLAN.md) — Fase 3
- [`NAVIGATION.md`](NAVIGATION.md) — Fleet API vs enlaces externos
- [TeslaMateApi](https://github.com/tobiasehlert/teslamateapi)
- [TeslaMate MQTT](https://docs.teslamate.org/docs/integrations/mqtt/) — alternativa futura
