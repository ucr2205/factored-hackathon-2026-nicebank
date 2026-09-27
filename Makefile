# Thin wrappers: every target is one `poetry run python ...` command, so it can be run without make (e.g. on Windows).
# Python dependencies are managed with Poetry only (pyproject.toml + poetry.lock).
PY ?= poetry run python

.PHONY: help setup data inventory seed smoke test

help:
	@echo "make setup      - install Python dependencies with Poetry (add ML deps: poetry install --with ml)"
	@echo "make data       - sync the full dataset from S3 into data/raw/ (incremental)"
	@echo "make inventory  - regenerate docs/data_inventory.md from data/raw/"
	@echo "make seed       - load the 20 demo customers into Postgres (resets demo data)"
	@echo "make smoke      - reseed and run the end-to-end chat scenarios against the API"
	@echo "make test       - backend unit tests + frontend type check and build"

setup:
	poetry install

data:
	$(PY) scripts/sync_data.py

inventory:
	$(PY) etl/inventory.py

seed:
	$(PY) etl/seed_demo.py

smoke: seed
	$(PY) scripts/smoke_chat.py

test:
	cd backend && go test ./...
	cd frontend && npm run build
