.PHONY: install install-dev api web web-build test lint smoke fetch-es fetch-pt parse-es parse-pt load-db ingest ingest-es ingest-pt ingest-reve ingest-reve-full cron-install cron-test-es cron-test-reve clean

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

cron-install:
	bash scripts/cron/install_cron.sh

cron-test-es:
	bash scripts/cron/run_scheduled_job.sh es

cron-test-reve:
	bash scripts/cron/run_scheduled_job.sh reve

clean:
	rm -rf .venv src/web/node_modules src/web/dist
