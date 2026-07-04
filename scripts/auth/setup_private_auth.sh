#!/usr/bin/env bash
# Configura TOTP + contraseña para la zona privada (usa el venv del proyecto).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../" && pwd)"
PY="${ROOT}/.venv/bin/python"

if [[ ! -x "$PY" ]]; then
  echo "No hay venv en ${ROOT}/.venv"
  echo "Crea uno e instala dependencias:"
  echo "  cd ${ROOT}"
  echo "  python3 -m venv .venv"
  echo "  .venv/bin/pip install -e ."
  exit 1
fi

export PYTHONPATH="${ROOT}/src"
exec "$PY" "${ROOT}/scripts/auth/setup_private_auth.py" "$@"
