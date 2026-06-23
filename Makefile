.PHONY: install install-dev api web test lint fetch-es fetch-pt clean

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

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check src tests

fetch-es:
	.venv/bin/electrolineras-fetch-es

fetch-pt:
	.venv/bin/electrolineras-fetch-pt

clean:
	rm -rf .venv src/web/node_modules src/web/dist
