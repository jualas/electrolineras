#!/usr/bin/env bash
# Añade electro-test.jualas.es al túnel Cloudflare de Electrolineras (#6142).
#
# Requiere CLOUDFLARE_API_TOKEN con permisos:
#   Account → Cloudflare Tunnel: Edit
#   Zone → DNS: Edit (zona jualas.es)
#
# Uso:
#   export CLOUDFLARE_API_TOKEN=...
#   bash scripts/deploy/cloudflare-staging-hostname.sh
#
# Opcional (por defecto lee /mnt/datos/docker/electrolineras/.env):
#   DEPLOY_COMPOSE_DIR=/ruta/al/compose bash scripts/deploy/cloudflare-staging-hostname.sh

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_DIR="${DEPLOY_COMPOSE_DIR:-/mnt/datos/docker/electrolineras}"
ENV_FILE="${COMPOSE_DIR}/.env"

STAGING_HOST="${CLOUDFLARE_STAGING_HOST:-electro-test.jualas.es}"
STAGING_ORIGIN="${CLOUDFLARE_STAGING_ORIGIN:-http://127.0.0.1:8016}"
PROD_HOST="${CLOUDFLARE_PROD_HOST:-electro.jualas.es}"
ZONE_NAME="${CLOUDFLARE_ZONE_NAME:-jualas.es}"

if [[ -z "${CLOUDFLARE_API_TOKEN:-}" ]]; then
  echo "ERROR: define CLOUDFLARE_API_TOKEN (Zero Trust → API Tokens)." >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: no existe $ENV_FILE" >&2
  exit 1
fi

# Servicio de prod por defecto: IP LAN del host (sin IP fija en el repo); se puede fijar en el entorno.
export PROD_ORIGIN_SERVICE="${PROD_ORIGIN_SERVICE:-http://$(hostname -I | awk '{print $1}'):8015}"

exec python3 - "$REPO_ROOT" "$ENV_FILE" "$STAGING_HOST" "$STAGING_ORIGIN" "$PROD_HOST" "$ZONE_NAME" <<'PY'
from __future__ import annotations

import base64
import json
import os
import re
import sys
import urllib.error
import urllib.request

repo_root, env_file, staging_host, staging_origin, prod_host, zone_name = sys.argv[1:7]
api_token = os.environ["CLOUDFLARE_API_TOKEN"]


def cf_request(method: str, path: str, payload: dict | None = None) -> dict:
    url = f"https://api.cloudflare.com/client/v4{path}"
    data = None
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise SystemExit(f"Cloudflare API {method} {path} → HTTP {exc.code}: {detail}") from exc
    if not body.get("success", False):
        raise SystemExit(f"Cloudflare API error: {body}")
    return body


def read_tunnel_token(path: str) -> tuple[str, str]:
    token = None
    for line in open(path, encoding="utf-8"):
        if line.startswith("CLOUDFLARED_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"').strip("'")
            break
    if not token:
        raise SystemExit(f"CLOUDFLARE_TOKEN no encontrado en {path}")
    pad = "=" * ((4 - len(token) % 4) % 4)
    data = json.loads(base64.urlsafe_b64decode(token + pad))
    return data["a"], data["t"]


def zone_id_for(name: str) -> str:
    body = cf_request("GET", f"/zones?name={name}")
    result = body.get("result") or []
    if not result:
        raise SystemExit(f"Zona DNS no encontrada: {name}")
    return result[0]["id"]


def dns_record_name(host: str, zone: str) -> str:
    suffix = f".{zone}"
    if host.endswith(suffix):
        return host[: -len(suffix)]
    return host.split(".", 1)[0]


account_id, tunnel_id = read_tunnel_token(env_file)
zone_id = zone_id_for(zone_name)
record_name = dns_record_name(staging_host, zone_name)
cname_target = f"{tunnel_id}.cfargotunnel.com"

print(f"Túnel: {tunnel_id}")
print(f"Cuenta: {account_id}")
print(f"Zona: {zone_name} ({zone_id})")

config_body = cf_request(
    "GET",
    f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
)
current_ingress = (config_body.get("result") or {}).get("config", {}).get("ingress") or []

def service_for(hostname: str, default: str) -> str:
    for rule in current_ingress:
        if rule.get("hostname") == hostname and rule.get("service"):
            return rule["service"]
    return default

prod_service = service_for(prod_host, os.environ["PROD_ORIGIN_SERVICE"])
ingress = [
    {"hostname": prod_host, "service": prod_service},
    {"hostname": staging_host, "service": staging_origin},
    {"service": "http_status:404"},
]

print("Ingress propuesto:")
for rule in ingress:
    print(f"  - {rule}")

cf_request(
    "PUT",
    f"/accounts/{account_id}/cfd_tunnel/{tunnel_id}/configurations",
    {"config": {"ingress": ingress}},
)
print("✓ Configuración del túnel actualizada")

existing = cf_request(
    "GET",
    f"/zones/{zone_id}/dns_records?type=CNAME&name={record_name}.{zone_name}",
).get("result") or []

if existing:
    rec = existing[0]
    if rec.get("content") == cname_target and rec.get("proxied"):
        print(f"✓ DNS CNAME ya correcto: {staging_host}")
    else:
        cf_request(
            "PUT",
            f"/zones/{zone_id}/dns_records/{rec['id']}",
            {
                "type": "CNAME",
                "name": record_name,
                "content": cname_target,
                "proxied": True,
            },
        )
        print(f"✓ DNS CNAME actualizado: {staging_host} → {cname_target}")
else:
    cf_request(
        "POST",
        f"/zones/{zone_id}/dns_records",
        {
            "type": "CNAME",
            "name": record_name,
            "content": cname_target,
            "proxied": True,
        },
    )
    print(f"✓ DNS CNAME creado: {staging_host} → {cname_target}")

print()
print("Smoke:")
print(f"  curl -4 -sf https://{staging_host}/health")
print(f"  curl -4 -sf https://{prod_host}/health")
PY
