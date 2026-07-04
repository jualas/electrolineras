# Dify + Cursor (sin OpenAI en el workflow)

El workflow **Electrolineras — guía de viaje EV** no usa el nodo LLM de Dify ni GPT-5/OpenAI. La narrativa sale del **Cursor CLI** vía `cursor-cli-bridge` (mismo patrón que Oposiciones).

## Flujo

```
Electrolineras API → Dify workflow → HTTP → cursor-cli-bridge → cursor agent → guide_text
```

1. API calcula plan + `trip_context_json` (motor determinista).
2. Dify recibe `trip_context_json` + `agent_summary`.
3. Nodo **Build prompt** → **HTTP → Cursor bridge** → **Parse bridge** → `guide_text`.

DSL: `docs/dify/electrolineras-trip-guide.yml`

## 1. Arrancar el puente Cursor (minipc)

```bash
cp scripts/dify/cursor-bridge.env.example scripts/dify/cursor-bridge.env
# Editar CURSOR_CLI_PATH si hace falta

./scripts/dify/run_cursor_bridge.sh
```

Comprobar:

```bash
curl -s http://127.0.0.1:18765/health
```

Opcional (arranque automático, **recomendado en prod**):

```bash
sudo cp scripts/dify/cursor-cli-bridge.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now cursor-cli-bridge
```

Usa `scripts/dify/cursor-bridge.env` (usuario `jualas`, puerto `18765`). Comprobar:

```bash
systemctl status cursor-cli-bridge
curl -s http://127.0.0.1:18765/health
```

## 2. Dify (solo LAN)

- Consola: http://<IP-LAN-SERVIDOR>:8590
- App: **Electrolineras — guía de viaje EV** (publicada `v3-multi-parada-e2e`)
- Grafo: **Start → Invoke Cursor bridge (Code) → End** — el nodo Code hace `POST` a `http://<IP-LAN-SERVIDOR>:18765/invoke` con `trip_context_json` + `agent_summary` (el nodo HTTP de Dify no sustituía variables en plantillas importadas).
- El **puente** construye el prompt multi-parada (`planned_stops[]`, comparativa de rutas) antes de llamar a Cursor CLI.

## 3. Electrolineras

En `/mnt/datos/docker/electrolineras/.env`:

```env
DIFY_API_BASE_URL=http://<IP-LAN-SERVIDOR>:8590/v1
DIFY_TRIP_WORKFLOW_API_KEY=app-…
```

```bash
cd /mnt/datos/docker/electrolineras && docker compose up -d --force-recreate electrolineras
```

## Referencias

- Puente: `/mnt/datos/docker/dify/integrations/dify-cursor/`
- Guía general Dify↔Cursor: `/mnt/datos/docker/dify/integrations/dify-cursor/README.md`
