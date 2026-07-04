#!/usr/bin/env bash
# Prueba INGEST_WEBHOOK_URL (#6052) — alerta de fallo simulado.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${ELECTROLINERAS_CRON_ENV:-$SCRIPT_DIR/electrolineras.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  set -a
  source "$ENV_FILE"
  set +a
fi

if [[ -z "${INGEST_WEBHOOK_URL:-}" ]]; then
  echo "ERROR: INGEST_WEBHOOK_URL no está definido en $ENV_FILE"
  echo "Opciones: ntfy (https://ntfy.sh/TU-TOPICO), Slack, Discord, n8n…"
  exit 1
fi

echo "Enviando alerta de prueba a: $INGEST_WEBHOOK_URL"
bash "$SCRIPT_DIR/notify_ingest_failure.sh" es "TEST webhook OK (#6052 — simulación fallo ingest-es)"
echo "OK — revisa la notificación (app ntfy, Slack, Discord, etc.)."
