# Thin wrappers: every target is one `poetry run python ...` command, so it can be run without make (e.g. on Windows).
# Python dependencies are managed with Poetry only (pyproject.toml + poetry.lock).
PY ?= poetry run python

.PHONY: help setup env data inventory profile eda etl test-etl seed smoke test load

help:
	@echo "make setup      - install Python dependencies with Poetry (add ML deps: poetry install --with ml)"
	@echo "make env       - create .env from .env.example and generate a local PII_KEY"
	@echo "make data       - sync the full dataset from S3 into data/raw/ (incremental)"
	@echo "make inventory  - regenerate docs/data_inventory.md from data/raw/"
	@echo "make profile    - profile data quality of the 13 tables into docs/data_quality_report.md"
	@echo "make eda        - Gate 1 business EDA into docs/eda_findings.md (needs make profile first)"
	@echo "make etl        - raw -> silver pipeline (contracts, quarantine, lineage); incremental"
	@echo "make test-etl   - pipeline tests over the labeled fixture dataset"
	@echo "make seed       - load the full silver dataset into Postgres (needs make etl; resets demo data)"
	@echo "make smoke      - reseed and run the end-to-end chat scenarios against the API"
	@echo "make test       - backend unit tests + frontend type check and build"
	@echo "make load       - JMeter smoke load test (5 users, 60 s); needs jmeter on PATH"

setup:
	poetry install

env:
	$(PY) scripts/make_env.py

data:
	$(PY) scripts/sync_data.py

inventory:
	$(PY) etl/inventory.py

profile:
	$(PY) analysis/01_profile.py

eda:
	$(PY) analysis/02_business.py

etl:
	$(PY) etl/pipeline/run.py

test-etl:
	poetry run pytest etl/tests -q

seed:
	$(PY) etl/load_postgres.py

smoke: seed
	$(PY) scripts/smoke_chat.py

test:
	cd backend && go test ./...
	cd frontend && npm run build

load:
	jmeter -n -t qa/jmeter/nicebank-load.jmx -Jusers=5 -Jramp=10 -Jduration=60 -f -l qa/jmeter/results/results.jtl -e -o qa/jmeter/results/report
