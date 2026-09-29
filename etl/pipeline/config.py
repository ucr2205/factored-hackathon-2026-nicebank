"""Pipeline configuration: every path the pipeline touches, in one injectable object.

run.py builds one from the CLI (defaults under REPO_ROOT/data); tests build one over tmp_path so the
whole pipeline runs against fixtures without environment variables.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]


@dataclass(frozen=True)
class PipelineConfig:
    raw_dir: Path = REPO_ROOT / "data" / "raw"
    silver_dir: Path = REPO_ROOT / "data" / "silver"
    quarantine_dir: Path = REPO_ROOT / "data" / "quarantine"
    state_db: Path = REPO_ROOT / "data" / "etl_state.duckdb"
    tmp_dir: Path = REPO_ROOT / "data" / "tmp"
    run_id: str = field(default_factory=_run_id)
    memory_limit: str = "10GB"
    threads: int = 8
    validate_batch_rows: int = 500_000  # upper bound per Pandera batch (digital_events ~430k/month)

    def duckdb_pragmas(self) -> list[str]:
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        return [
            f"SET temp_directory = '{self.tmp_dir.as_posix()}'",
            f"SET memory_limit = '{self.memory_limit}'",
            f"SET threads = {self.threads}",
            "SET preserve_insertion_order = false",
        ]

    def silver_path(self, table: str) -> Path:
        return self.silver_dir / table

    def quarantine_path(self, table: str) -> Path:
        return self.quarantine_dir / table / f"{self.run_id}.parquet"
