#!/usr/bin/env bash
# Monitor externo para el mini PC (cucu / debian @ <IP-LAN-SERVIDOR>).
# Ejecutar desde OTRO equipo (router GL, portátil en LAN, VPS con VPN).
#
# Si hay ping pero SSH no responde N veces → intenta recuperación:
#   1) RECOVER_SSH_CMD  (opcional: reinicio remoto vía IPMI/API)
#   2) REBOOT_URL       (opcional: webhook enchufe inteligente / smart plug)
#   3) WOL_CMD          (solo útil si el host está apagado; no ayuda en soft-hang)
#
# Cron ejemplo (en el router u otro host):
#   */5 * * * * TARGET_HOST=<IP-LAN-SERVIDOR> /usr/local/sbin/check-cucu-ssh-recover.sh >>/tmp/cucu-ssh-recover.log 2>&1
set -euo pipefail

TARGET_HOST="${TARGET_HOST:-<IP-LAN-SERVIDOR>}"
TARGET_SSH_PORT="${TARGET_SSH_PORT:-22}"
SSH_USER="${SSH_USER:-jualas}"
FAILS_FILE="${FAILS_FILE:-/tmp/cucu-ssh-failcount}"
FAIL_THRESHOLD="${FAIL_THRESHOLD:-3}"
PING_COUNT="${PING_COUNT:-2}"
SSH_TIMEOUT="${SSH_TIMEOUT:-8}"

log() { printf '[%s] %s\n' "$(date -Is)" "$*"; }

ping_ok=0
if ping -c "$PING_COUNT" -W 2 "$TARGET_HOST" >/dev/null 2>&1; then
  ping_ok=1
fi

ssh_ok=0
if [[ "$ping_ok" -eq 1 ]]; then
  if ssh -o BatchMode=yes -o ConnectTimeout="$SSH_TIMEOUT" -o StrictHostKeyChecking=accept-new \
      -p "$TARGET_SSH_PORT" "${SSH_USER}@${TARGET_HOST}" 'echo ok' >/dev/null 2>&1; then
    ssh_ok=1
  fi
fi

fails=0
[[ -f "$FAILS_FILE" ]] && fails=$(cat "$FAILS_FILE" 2>/dev/null || echo 0)

if [[ "$ping_ok" -eq 1 && "$ssh_ok" -eq 1 ]]; then
  echo 0 >"$FAILS_FILE"
  exit 0
fi

if [[ "$ping_ok" -eq 0 ]]; then
  log "WARN: sin ping a $TARGET_HOST — posible apagado; WOL si está configurado"
  if [[ -n "${WOL_CMD:-}" ]]; then
    log "running WOL_CMD"
    bash -c "$WOL_CMD" || true
  fi
  exit 1
fi

fails=$((fails + 1))
echo "$fails" >"$FAILS_FILE"
log "SSH down on $TARGET_HOST (fail $fails/$FAIL_THRESHOLD), ping OK"

if [[ "$fails" -lt "$FAIL_THRESHOLD" ]]; then
  exit 1
fi

log "threshold reached — attempting recovery"
recovered=0
if [[ -n "${RECOVER_SSH_CMD:-}" ]]; then
  log "running RECOVER_SSH_CMD"
  if bash -c "$RECOVER_SSH_CMD"; then
    recovered=1
  fi
fi
if [[ "$recovered" -eq 0 && -n "${REBOOT_URL:-}" ]]; then
  log "hitting REBOOT_URL"
  if curl -fsS -m 15 "$REBOOT_URL" >/dev/null; then
    recovered=1
  fi
fi

if [[ "$recovered" -eq 1 ]]; then
  echo 0 >"$FAILS_FILE"
  log "recovery triggered"
  exit 0
fi

log "ERROR: no RECOVER_SSH_CMD ni REBOOT_URL configurados; intervención manual necesaria"
exit 2
