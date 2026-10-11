# Puente Cursor (cursor-cli-bridge)

El chat del asistente de viaje (`src/api/agent_trip_chat.py`) llama directamente al puente con `CURSOR_BRIDGE_URL` y `CURSOR_BRIDGE_TOKEN` (cabecera `X-Bridge-Token`). La guía de viaje la genera el motor local, sin IA.

Histórico: hasta el 2026-10-11 existía un flujo Dify «Electrolineras — guía de viaje EV» (API → Dify → puente). Se retiró (#6297) porque nunca llegó a funcionar y la web lo tenía desactivado.

```
Electrolineras API (chat) → cursor-cli-bridge → cursor agent (contenedor aislado, modo ask)
```

## Arrancar el puente (minipc)

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

## Referencias

- Puente: `/mnt/datos/docker/dify/integrations/dify-cursor/`
