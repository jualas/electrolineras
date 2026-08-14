#!/usr/bin/env bash
# Ciclo de vida OSRM on-demand: wake / idle-stop / reap-unhealthy.
#
# Uso:
#   manage_osrm.sh once          # wake + reap + idle (cron)
#   manage_osrm.sh wake          # arrancar si hay demanda
#   manage_osrm.sh stop          # parar ambos
#   manage_osrm.sh status
#
# Señales (volumen API → host):
#   $LIFECYCLE_DIR/osrm_wake.request  — la API pide arranque
#   $LIFECYCLE_DIR/osrm_last_used     — último routing local OK
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${ELECTROLINERAS_REPO:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
COMPOSE_DIR="${OSRM_COMPOSE_DIR:-$REPO/docker/osrm}"
LIFECYCLE_DIR="${OSRM_LIFECYCLE_DIR:-/mnt/datos/docker/volumes/electrolineras-data/runtime}"
WAKE_FILE="${OSRM_WAKE_FILE:-$LIFECYCLE_DIR/osrm_wake.request}"
LAST_USED_FILE="${OSRM_LAST_USED_FILE:-$LIFECYCLE_DIR/osrm_last_used}"
STATE_FILE="${OSRM_LIFECYCLE_STATE:-$LIFECYCLE_DIR/osrm_lifecycle.state}"
IDLE_MINUTES="${OSRM_IDLE_MINUTES:-30}"
UNHEALTHY_GRACE_MINUTES="${OSRM_UNHEALTHY_GRACE_MINUTES:-12}"
KILL_COOLDOWN_MINUTES="${OSRM_KILL_COOLDOWN_MINUTES:-20}"
CONTAINERS=(electrolineras-osrm-car electrolineras-osrm-shortest)

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*"
}

mkdir -p "$LIFECYCLE_DIR"

load_state() {
  LAST_KILL_EPOCH=0
  if [[ -f "$STATE_FILE" ]]; then
    # shellcheck disable=SC1090
    source "$STATE_FILE" || true
  fi
}

save_state() {
  cat >"$STATE_FILE" <<EOF
LAST_KILL_EPOCH=${LAST_KILL_EPOCH:-0}
EOF
}

file_age_minutes() {
  local path="$1"
  if [[ ! -f "$path" ]]; then
    echo 999999
    return
  fi
  local mtime now
  mtime=$(stat -c %Y "$path" 2>/dev/null || echo 0)
  now=$(date +%s)
  echo $(((now - mtime) / 60))
}

container_running() {
  local name="$1"
  [[ "$(docker inspect -f '{{.State.Running}}' "$name" 2>/dev/null || echo false)" == "true" ]]
}

container_health() {
  local name="$1"
  docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$name" 2>/dev/null || echo "missing"
}

container_uptime_minutes() {
  local name="$1"
  local started now
  started=$(docker inspect -f '{{.State.StartedAt}}' "$name" 2>/dev/null || true)
  if [[ -z "$started" || "$started" == "0001-01-01T00:00:00Z" ]]; then
    echo 0
    return
  fi
  now=$(date +%s)
  local started_epoch
  started_epoch=$(date -d "$started" +%s 2>/dev/null || echo "$now")
  echo $(((now - started_epoch) / 60))
}

any_running() {
  local c
  for c in "${CONTAINERS[@]}"; do
    if container_running "$c"; then
      return 0
    fi
  done
  return 1
}

compose() {
  docker compose -f "$COMPOSE_DIR/docker-compose.yml" "$@"
}

cmd_status() {
  local c
  for c in "${CONTAINERS[@]}"; do
    if container_running "$c"; then
      log "$c: running health=$(container_health "$c") uptime_min=$(container_uptime_minutes "$c")"
    else
      log "$c: stopped"
    fi
  done
  log "wake_age_min=$(file_age_minutes "$WAKE_FILE") last_used_age_min=$(file_age_minutes "$LAST_USED_FILE")"
}

cmd_wake() {
  local wake_age demand=0
  wake_age=$(file_age_minutes "$WAKE_FILE")
  # Demanda reciente: wake file tocado en la última hora, o last_used muy reciente.
  if [[ -f "$WAKE_FILE" && "$wake_age" -le 60 ]]; then
    demand=1
  fi
  if [[ "$(file_age_minutes "$LAST_USED_FILE")" -le 5 ]]; then
    demand=1
  fi
  if [[ "$demand" -ne 1 ]]; then
    return 0
  fi
  if any_running; then
    # Ya arriba: limpiar wake viejo si ambos healthy
    local all_healthy=1 c
    for c in "${CONTAINERS[@]}"; do
      if container_running "$c"; then
        local h
        h=$(container_health "$c")
        if [[ "$h" != "healthy" && "$h" != "none" ]]; then
          all_healthy=0
        fi
      else
        all_healthy=0
      fi
    done
    if [[ "$all_healthy" -eq 1 && -f "$WAKE_FILE" ]]; then
      rm -f "$WAKE_FILE"
      log "OSRM healthy; wake request cleared"
    fi
    return 0
  fi

  load_state
  local now cooldown_age
  now=$(date +%s)
  cooldown_age=$(((now - ${LAST_KILL_EPOCH:-0}) / 60))
  if [[ "${LAST_KILL_EPOCH:-0}" -gt 0 && "$cooldown_age" -lt "$KILL_COOLDOWN_MINUTES" ]]; then
    log "wake deferred: kill cooldown ${cooldown_age}/${KILL_COOLDOWN_MINUTES} min"
    return 0
  fi

  log "starting OSRM (on-demand)"
  compose up -d
}

cmd_reap() {
  load_state
  local c killed=0
  for c in "${CONTAINERS[@]}"; do
    container_running "$c" || continue
    local health uptime
    health=$(container_health "$c")
    uptime=$(container_uptime_minutes "$c")
    if [[ "$health" == "unhealthy" && "$uptime" -ge "$UNHEALTHY_GRACE_MINUTES" ]]; then
      log "killing unhealthy $c (uptime ${uptime}m >= grace ${UNHEALTHY_GRACE_MINUTES}m)"
      docker kill "$c" >/dev/null 2>&1 || docker stop -t 5 "$c" >/dev/null 2>&1 || true
      killed=1
    fi
  done
  if [[ "$killed" -eq 1 ]]; then
    LAST_KILL_EPOCH=$(date +%s)
    save_state
    # Tras kill, no relanzar en bucle: quitar wake para forzar fallback público
    # hasta nueva demanda explícita de la API.
    rm -f "$WAKE_FILE"
    log "wake cleared after reap; API seguirá con fallback público"
  fi
}

cmd_idle_stop() {
  any_running || return 0
  local wake_age used_age
  wake_age=$(file_age_minutes "$WAKE_FILE")
  used_age=$(file_age_minutes "$LAST_USED_FILE")
  # Si hay wake reciente, no parar.
  if [[ -f "$WAKE_FILE" && "$wake_age" -lt "$IDLE_MINUTES" ]]; then
    return 0
  fi
  # Si se usó local recientemente, no parar.
  if [[ -f "$LAST_USED_FILE" && "$used_age" -lt "$IDLE_MINUTES" ]]; then
    return 0
  fi
  # Sin señales: si nunca hubo last_used/wake, y llevan idle_minutes uptime, parar.
  local min_uptime=999999 c up
  for c in "${CONTAINERS[@]}"; do
    if container_running "$c"; then
      up=$(container_uptime_minutes "$c")
      if [[ "$up" -lt "$min_uptime" ]]; then
        min_uptime=$up
      fi
    fi
  done
  if [[ "$min_uptime" -lt "$IDLE_MINUTES" ]]; then
    return 0
  fi
  log "idle stop OSRM (no demand >= ${IDLE_MINUTES}m, uptime>=${min_uptime}m)"
  compose stop
}

cmd_stop() {
  log "stopping OSRM"
  compose stop || true
}

cmd_once() {
  cmd_reap
  cmd_wake
  cmd_idle_stop
}

main() {
  local action="${1:-once}"
  case "$action" in
    once) cmd_once ;;
    wake) cmd_wake ;;
    stop) cmd_stop ;;
    reap) cmd_reap ;;
    idle) cmd_idle_stop ;;
    status) cmd_status ;;
    *)
      echo "Uso: $0 {once|wake|stop|reap|idle|status}" >&2
      exit 2
      ;;
  esac
}

main "$@"
