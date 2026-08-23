#!/usr/bin/env bash
# Genera QR TOTP para Microsoft Authenticator (lee PRIVATE_AUTH_USERS del .env prod).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PY="${ROOT}/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "No hay venv en ${ROOT}/.venv — ejecuta: make install-dev" >&2
  exit 1
fi

exec "$PY" "${ROOT}/scripts/auth/show_totp_qr.py" "$@"
