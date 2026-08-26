# CI/CD — Electrolineras (#6044)

Pipeline GitHub Actions + scripts locales de despliegue en el mini PC.

## Resumen

| Workflow | Runner | Cuándo | Qué hace |
|----------|--------|--------|----------|
| [`ci.yml`](../.github/workflows/ci.yml) | `ubuntu-latest` | PR y push a `main` | Ruff, pytest, build Docker |
| [`deploy.yml`](../.github/workflows/deploy.yml) | **`self-hosted`** | Tag `v*` o manual | `scripts/deploy/deploy.sh` |

## CI (GitHub cloud)

En cada PR / push a `main`:

1. **Ruff** — `ruff check src tests`
2. **Pytest** — suite completa (sin tests `@integration`)
3. **Docker build** — valida `docker/Dockerfile` + import de la app

Localmente:

```bash
make ci-local    # lint + pytest
make lint
make test
docker build -f docker/Dockerfile -t electrolineras:local .
```

## Deploy (mini PC)

### 1. Runner self-hosted (recomendado)

El mini PC no es accesible desde Internet; el job de deploy usa un **runner en la LAN**.

```bash
# En el mini PC (como usuario de despliegue, p. ej. jualas)
mkdir -p ~/actions-runner && cd ~/actions-runner
curl -o actions-runner-linux-x64-2.322.0.tar.gz -L \
  https://github.com/actions/runner/releases/download/v2.322.0/actions-runner-linux-x64-2.322.0.tar.gz
tar xzf ./actions-runner-linux-x64-*.tar.gz
./config.sh --url https://github.com/TU_ORG/Electrolineras --token TOKEN_DE_GITHUB
sudo ./svc.sh install
sudo ./svc.sh start
```

Etiqueta sugerida: `self-hosted`, `Linux`, `electrolineras`.

Tras registrar el runner:

- **Release:** `git tag v0.1.0 && git push origin v0.1.0` → deploy automático
- **Manual:** GitHub → Actions → Deploy → Run workflow → ref `main` o `v0.1.0`

### 2. Script local (sin Actions)

```bash
cp scripts/deploy/deploy.env.example scripts/deploy/deploy.env
bash scripts/deploy/deploy.sh

# Tag concreto
DEPLOY_REF=v0.1.0 bash scripts/deploy/deploy.sh
```

El script:

1. `git pull` (o checkout `DEPLOY_REF`)
2. `sync_compose.sh` — copia `docker-compose.prod.yml` al mini PC
3. Guarda imágenes actuales como `*:previous` (api + nginx)
4. `docker compose -f docker-compose.prod.yml build` + `up -d electrolineras-api electrolineras-nginx`
5. Espera `GET /health` (vía nginx)
6. Si falla → intenta `rollback.sh`

Estado del último deploy: `/mnt/datos/docker/electrolineras/.deploy-state`

### 2b. Staging (pruebas antes de prod)

Stack paralelo en **`:8016`** — no toca `electro.jualas.es` / `:8015`.

```bash
# Desde la rama a validar
make deploy-staging
curl -s http://127.0.0.1:8016/health
```

Documentación completa: [`docs/STAGING.md`](STAGING.md).

### 3. Rollback

```bash
bash scripts/deploy/rollback.sh
```

Restaura `electrolineras-api:previous` y `electrolineras-nginx:previous` y reinicia los contenedores.

### 4. Deploy vía SSH (alternativa)

Si el host es alcanzable (VPN/Tailscale/IP pública), activa el job `deploy-ssh-fallback` en [`deploy.yml`](../.github/workflows/deploy.yml) (`if: false` → condición real) y configura secrets:

| Secret | Ejemplo |
|--------|---------|
| `DEPLOY_HOST` | `<IP-LAN-SERVIDOR>` |
| `DEPLOY_USER` | `jualas` |
| `DEPLOY_SSH_KEY` | clave privada ed25519 |
| `DEPLOY_SSH_PORT` | `22` (opcional) |

## Releases y tags

Convención: **`vMAJOR.MINOR.PATCH`** (SemVer).

```bash
git tag -a v0.1.0 -m "Primera release prod"
git push origin v0.1.0
```

Opcional futuro: publicar imagen en GHCR (`ghcr.io/.../electrolineras:v0.1.0`) y `docker pull` en el VPS.

## Variables de deploy

Ver [`scripts/deploy/deploy.env.example`](../scripts/deploy/deploy.env.example):

| Variable | Default |
|----------|---------|
| `ELECTROLINERAS_REPO` | repo git |
| `DEPLOY_COMPOSE_DIR` | `/mnt/datos/docker/electrolineras` |
| `DEPLOY_HEALTH_URL` | `http://127.0.0.1:8015/health` |
| `DEPLOY_REF` | (vacío = pull rama actual) |

## Checklist pre-merge a main

- [ ] `make ci-local` verde
- [ ] `make env-check-prod` en `.env` Docker
- [ ] Changelog / tag si es release

## Referencias

- Runbook: [`DEPLOYMENT.md`](DEPLOYMENT.md)
- Variables: [`ENV.md`](ENV.md)
