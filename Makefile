# Thin wrappers: every target is one Python command, so it can be run without make (e.g. on Windows).
PY ?= python

.PHONY: help data inventory

help:
	@echo "make data       - sync the full dataset from S3 into data/raw/ (incremental)"
	@echo "make inventory  - regenerate docs/data_inventory.md from data/raw/"

data:
	$(PY) scripts/sync_data.py

inventory:
	$(PY) etl/inventory.py
