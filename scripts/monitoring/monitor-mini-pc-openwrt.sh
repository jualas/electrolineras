#!/bin/sh
# Monitor mini PC (cucu) desde GL-AXT1800 / OpenWrt.
#
# Casos:
#   A) Sin ping          → Wake-on-LAN (apagado / corte)
#   B) Ping OK, SSH KO   → soft hang: alerta + REBOOT_URL opcional (enchufe)
#   C) Ping OK, SSH OK   → nada
#
# Cron:
#   */5 * * * * /usr/bin/monitor-mini-pc-openwrt.sh >> /tmp/monitor-mini-pc.log 2>&1
#
# Opcional en /etc/monitor-mini-pc.env:
#   REBOOT_URL='http://smartplug/.../cycle'
#   ALERT_URL='https://ntfy.sh/tu-tema'   # POST texto

TARGET_IP="${TARGET_IP:-<IP-LAN-SERVIDOR>}"
TARGET_MAC="${TARGET_MAC:-78:55:36:07:9c:3e}"
TARGET_SSH_PORT="${TARGET_SSH_PORT:-22}"
SSH_USER="${SSH_USER:-jualas}"
WOL_IFACE="${WOL_IFACE:-}"
PING_COUNT="${PING_COUNT:-2}"
PING_TIMEOUT="${PING_TIMEOUT:-2}"
SSH_TIMEOUT="${SSH_TIMEOUT:-8}"
WOL_COOLDOWN_SEC="${WOL_COOLDOWN_SEC:-300}"
SSH_FAIL_THRESHOLD="${SSH_FAIL_THRESHOLD:-3}"
REBOOT_COOLDOWN_SEC="${REBOOT_COOLDOWN_SEC:-1800}"

ENV_FILE="${ENV_FILE:-/etc/monitor-mini-pc.env}"
WOL_LAST_FILE="/tmp/wake-mini-pc.last"
SSH_FAIL_FILE="/tmp/mini-pc-ssh-fails"
REBOOT_LAST_FILE="/tmp/mini-pc-reboot.last"

if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090
    . "$ENV_FILE"
fi

log() {
    printf '[%s] %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$1"
}

detect_iface() {
    if [ -n "$WOL_IFACE" ]; then
        echo "$WOL_IFACE"
        return 0
    fi
    ip route get "$TARGET_IP" 2>/dev/null | awk '{
        for (i = 1; i <= NF; i++) {
            if ($i == "dev") { print $(i + 1); exit }
        }
    }'
}

send_wol() {
    iface="$(detect_iface)"
    if [ -z "$iface" ]; then
        log "ERROR: no se pudo detectar interfaz hacia $TARGET_IP"
        return 1
    fi
    if ! command -v etherwake >/dev/null 2>&1; then
        log "ERROR: falta etherwake"
        return 1
    fi
    log "WoL por $iface → $TARGET_MAC"
    etherwake -i "$iface" "$TARGET_MAC"
}

alert() {
    msg="$1"
    log "$msg"
    if [ -n "${ALERT_URL:-}" ] && command -v curl >/dev/null 2>&1; then
        curl -fsS -m 10 -d "$msg" "$ALERT_URL" >/dev/null 2>&1 || true
    fi
}

cooldown_ok() {
    file="$1"
    sec="$2"
    now="$(date +%s)"
    if [ -f "$file" ]; then
        last="$(cat "$file" 2>/dev/null)"
        if [ -n "$last" ] && [ $((now - last)) -lt "$sec" ]; then
            return 1
        fi
    fi
    echo "$now" > "$file"
    return 0
}

ssh_alive() {
    # BatchMode sin clave: si sshd vive → Permission denied / ok
    # Si soft-hang / puerto muerto → timeout / refused
    err="$(ssh -y -o BatchMode=yes -o ConnectTimeout="$SSH_TIMEOUT" \
        -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
        -p "$TARGET_SSH_PORT" "${SSH_USER}@${TARGET_IP}" 'echo ok' 2>&1)" || true
    case "$err" in
        *Permission\ denied*|*ok*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

try_reboot_outlet() {
    if [ -z "${REBOOT_URL:-}" ]; then
        alert "SOFT-HANG $TARGET_IP: ping OK, SSH KO — sin REBOOT_URL (configura enchufe en $ENV_FILE)"
        return 1
    fi
    if ! cooldown_ok "$REBOOT_LAST_FILE" "$REBOOT_COOLDOWN_SEC"; then
        log "Reboot outlet en cooldown"
        return 0
    fi
    alert "SOFT-HANG $TARGET_IP: ciclando alimentación vía REBOOT_URL"
    if command -v curl >/dev/null 2>&1; then
        curl -fsS -m 15 "$REBOOT_URL" >/dev/null 2>&1 || true
    else
        wget -q -T 15 -O /dev/null "$REBOOT_URL" 2>/dev/null || true
    fi
    echo 0 > "$SSH_FAIL_FILE"
}

# --- main ---

if ! ping -c "$PING_COUNT" -W "$PING_TIMEOUT" "$TARGET_IP" >/dev/null 2>&1; then
    echo 0 > "$SSH_FAIL_FILE"
    if cooldown_ok "$WOL_LAST_FILE" "$WOL_COOLDOWN_SEC"; then
        log "Sin ping a $TARGET_IP"
        send_wol
        log "Magic packet enviado"
    else
        log "Sin ping; WoL en cooldown"
    fi
    exit 0
fi

if ssh_alive; then
    echo 0 > "$SSH_FAIL_FILE"
    exit 0
fi

fails=0
[ -f "$SSH_FAIL_FILE" ] && fails="$(cat "$SSH_FAIL_FILE" 2>/dev/null || echo 0)"
fails=$((fails + 1))
echo "$fails" > "$SSH_FAIL_FILE"
log "Ping OK, SSH KO en $TARGET_IP (fail $fails/$SSH_FAIL_THRESHOLD)"

if [ "$fails" -ge "$SSH_FAIL_THRESHOLD" ]; then
    try_reboot_outlet
fi

exit 1
