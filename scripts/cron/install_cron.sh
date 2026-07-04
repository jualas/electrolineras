#!/usr/bin/env bash
# Muestra el crontab recomendado e instala electrolineras.env si falta.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CRON_DIR="$ROOT/scripts/cron"
ENV_EXAMPLE="$CRON_DIR/electrolineras.env.example"
ENV_FILE="$CRON_DIR/electrolineras.env"

chmod +x "$CRON_DIR/run_scheduled_job.sh"
chmod +x "$CRON_DIR/verify_ingest.py"
chmod +x "$CRON_DIR/notify_ingest_failure.sh"
chmod +x "$CRON_DIR/test_ingest_webhook.sh"
chmod +x "$CRON_DIR/test_ingest_failure_notify.sh"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ENV_EXAMPLE" "$ENV_FILE"
  echo "Creado $ENV_FILE — revísalo antes de activar cron."
else
  echo "Ya existe $ENV_FILE"
fi

echo
echo "=== Crontab recomendado (pegar con: crontab -e) ==="
cat "$CRON_DIR/electrolineras.crontab.example"
echo
echo "=== Probar un job ==="
echo "  bash $CRON_DIR/run_scheduled_job.sh es"
echo
echo "=== Logrotate (opcional, requiere sudo) ==="
echo "  sudo cp $CRON_DIR/logrotate.electrolineras.example /etc/logrotate.d/electrolineras"
echo "  # Ajustar su usuario grupo si difiere de jualas"
echo
echo "=== Webhook alertas (#6052) ==="
echo "  Editar INGEST_WEBHOOK_URL en $ENV_FILE"
echo "  bash $CRON_DIR/test_ingest_webhook.sh"
echo
echo "=== Backups (#6041) ==="
echo "  make backup-run && make backup-verify"
echo "  Añadir a crontab: 30 5 * * * $ROOT/scripts/backup/run_backup.sh daily"
