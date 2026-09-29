"""Test harness: each test gets a private copy of the labeled fixture dataset (origin: team_generated)
under tmp_path and a PipelineConfig pointing at it, so tests never touch data/ or each other."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import duckdb
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from etl.pipeline.config import PipelineConfig  # noqa: E402
from etl.pipeline.writers import silver_glob  # noqa: E402

FIXTURES = Path(__file__).parent / "fixtures" / "raw"
TABLES_IN_FIXTURE = ["branches", "service_agents", "customers", "products",
                     "daily_exchange_rates", "transactions"]


@pytest.fixture
def cfg(tmp_path: Path) -> PipelineConfig:
    raw = tmp_path / "raw"
    shutil.copytree(FIXTURES, raw)
    return PipelineConfig(
        raw_dir=raw,
        silver_dir=tmp_path / "silver",
        quarantine_dir=tmp_path / "quarantine",
        state_db=tmp_path / "etl_state.duckdb",
        tmp_dir=tmp_path / "tmp",
        memory_limit="2GB",
        threads=2,
    )


def silver_rows(cfg: PipelineConfig, table: str, order_by: str) -> list[dict]:
    con = duckdb.connect()
    rel = con.sql(f"SELECT * FROM read_parquet('{silver_glob(cfg, table)}', "
                  f"hive_partitioning = true) ORDER BY {order_by}")
    cols = rel.columns
    rows = [dict(zip(cols, r)) for r in rel.fetchall()]
    con.close()
    return rows


def quarantine_rows(cfg: PipelineConfig, table: str) -> list[dict]:
    glob = (cfg.quarantine_dir / table / "*.parquet").as_posix()
    con = duckdb.connect()
    rel = con.sql(f"SELECT * FROM read_parquet('{glob}')")
    cols = rel.columns
    rows = [dict(zip(cols, r)) for r in rel.fetchall()]
    con.close()
    return rows
