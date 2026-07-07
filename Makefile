.PHONY: install install-dev api web web-build test lint smoke fetch-es fetch-pt parse-es parse-pt load-db ingest ingest-es ingest-pt ingest-reve ingest-reve-full test-reve-api cron-install cron-test-es cron-test-reve backup-run backup-verify monitor-check monitor-test env-check-prod env-secure ci-local deploy deploy-rollback docker-build docker-up docker-down docker-sync-prod nominatim-prepare nominatim-up nominatim-logs nominatim-status nominatim-finish-prod nominatim-install-finish-cron nominatim-remove-finish-cron clean

DOCKER_COMPOSE_DIR ?= /mnt/datos/docker/electrolineras
DOCKER_COMPOSE_FILE ?= docker/docker-compose.prod.yml
DOCKER_COMPOSE := docker compose -f $(DOCKER_COMPOSE_FILE)

ENV_FILE ?= .env

install:
	python3 -m venv .venv
	.venv/bin/pip install -U pip
	.venv/bin/pip install -e .

install-dev: install
	.venv/bin/pip install -e ".[dev]"
	cd src/web && npm install

api:
	.venv/bin/electrolineras-api

web:
	cd src/web && npm run dev

web-build:
	cd src/web && npm run build

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check src tests

smoke:
	@if curl -sf http://127.0.0.1:8000/health 2>/dev/null | grep -q '"status"'; then \
		SMOKE_BASE_URL=http://127.0.0.1:8000 bash scripts/smoke_dev.sh; \
	else \
		echo "API Electrolineras no detectada en :8000 (¿otro servicio?). Test in-process:"; \
		.venv/bin/python -c "from fastapi.testclient import TestClient; from api.main import app; c=TestClient(app); print('health', c.get('/health').json()); print('stations', c.get('/api/v1/meta/stats').json()['total_stations'])"; \
	fi

fetch-es:
	.venv/bin/electrolineras-fetch-es

fetch-pt:
	.venv/bin/electrolineras-fetch-pt

parse-es:
	.venv/bin/electrolineras-parse-datex --latest ES --summary

parse-pt:
	.venv/bin/electrolineras-parse-datex --latest PT --summary

load-db:
	.venv/bin/electrolineras-load-db

ingest:
	.venv/bin/electrolineras-ingest

ingest-es:
	.venv/bin/electrolineras-ingest --es-only

ingest-pt:
	.venv/bin/electrolineras-ingest --pt-only

ingest-reve:
	.venv/bin/electrolineras-sync-reve --geojson

ingest-reve-full:
	.venv/bin/electrolineras-ingest --es-only --skip-fetch && .venv/bin/electrolineras-sync-reve --geojson

test-reve-api:
	@REVE_API_KEY="$$(grep -m1 '^REVE_API_KEY=' scripts/cron/electrolineras.env 2>/dev/null | cut -d= -f2-)"; \
	export REVE_API_KEY; \
	.venv/bin/electrolineras-sync-reve --test-connection

cron-install:
	bash scripts/cron/install_cron.sh

cron-test-es:
	bash scripts/cron/run_scheduled_job.sh es

cron-test-reve:
	bash scripts/cron/run_scheduled_job.sh reve

backup-run:
	bash scripts/backup/run_backup.sh daily

backup-verify:
	bash scripts/backup/verify_restore.sh

monitor-check:
	bash scripts/monitoring/run_health_checks.sh

monitor-test:
	bash scripts/monitoring/test_health_checks.sh

env-check-prod:
	.venv/bin/python scripts/env/check_env.py $(ENV_FILE)

env-secure:
	bash scripts/env/secure_env_permissions.sh $(ENV_FILE)

ci-local: lint test

deploy:
	bash scripts/deploy/deploy.sh

deploy-rollback:
	bash scripts/deploy/rollback.sh

docker-sync-prod:
	bash scripts/deploy/sync_compose.sh

docker-build:
	$(DOCKER_COMPOSE) build electrolineras-api electrolineras-nginx

docker-up:
	$(DOCKER_COMPOSE) up -d

docker-down:
	$(DOCKER_COMPOSE) down

nominatim-prepare:
	bash scripts/nominatim/prepare_pbf.sh

nominatim-up:
	cd docker/nominatim && docker compose up -d

nominatim-logs:
	cd docker/nominatim && docker compose logs -f nominatim

nominatim-status:
	@docker ps --filter name=electrolineras-nominatim --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
	@du -sh /mnt/datos/docker/volumes/nominatim-iberia 2>/dev/null || echo "Sin datos aún"
	@curl -sf 'http://127.0.0.1:8092/search?q=Madrid&format=json&limit=1&countrycodes=es' >/dev/null && echo "Geocode: OK" || echo "Geocode: aún importando (502/connection refused es normal)"

nominatim-finish-prod:
	bash scripts/nominatim/finish_prod_setup.sh

nominatim-install-finish-cron:
	bash scripts/nominatim/install_finish_cron.sh

nominatim-remove-finish-cron:
	bash scripts/nominatim/install_finish_cron.sh --remove

clean:
	rm -rf .venv src/web/node_modules src/web/dist
