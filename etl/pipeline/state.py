"""Watermark and lineage store (data/etl_state.duckdb).

etl_files is the per-file watermark: a raw file is pending until its (path, size, mtime) triple is
recorded, so a re-sync that adds or rewrites a partition makes exactly those files pending again.
etl_runs and quality_findings are the lineage: what each run read, kept, quarantined and flagged.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import duckdb

from .config import PipelineConfig
from .specs import TABLES

DDL = """
CREATE TABLE IF NOT EXISTS etl_files (
    table_name  VARCHAR,
    rel_path    VARCHAR,
    size_bytes  BIGINT,
    mtime_ns    BIGINT,
    run_id      VARCHAR,
    processed_at TIMESTAMP,
    PRIMARY KEY (table_name, rel_path)
);
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id VARCHAR, table_name VARCHAR, started_at TIMESTAMP, finished_at TIMESTAMP,
    files_read BIGINT, rows_read BIGINT, rows_valid BIGINT, rows_quarantined BIGINT,
    rows_pk_deduped BIGINT, status VARCHAR
);
CREATE TABLE IF NOT EXISTS quality_findings (
    run_id VARCHAR, table_name VARCHAR, rule_id VARCHAR, rows_affected BIGINT
);
"""


@dataclass(frozen=True)
class RawFile:
    """One raw CSV as the watermark sees it: path relative to the raw directory, size and modification time."""
    rel_path: str
    size: int
    mtime_ns: int

    @property
    def key(self) -> tuple[str, int, int]:
        """Watermark key: a file is pending again when any of the three values changes."""
        return (self.rel_path, self.size, self.mtime_ns)


def list_raw_files(cfg: PipelineConfig, table: str) -> list[RawFile]:
    """Current raw files of a table (partitioned folder or single root-level CSV)."""
    spec = TABLES[table]
    if spec.partitioned_raw:
        paths = sorted((cfg.raw_dir / table).rglob("*.csv"))
    else:
        p = cfg.raw_dir / f"{table}.csv"
        paths = [p] if p.exists() else []
    out = []
    for p in paths:
        st = p.stat()
        out.append(RawFile(p.relative_to(cfg.raw_dir).as_posix(), st.st_size, st.st_mtime_ns))
    return out


class StateStore:
    """Read/write access to data/etl_state.duckdb: per-file watermark, run lineage and quality findings."""
    def __init__(self, cfg: PipelineConfig):
        self.cfg = cfg
        Path(cfg.state_db).parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(cfg.state_db))
        self.con.execute(DDL)

    def close(self) -> None:
        """Close the DuckDB connection."""
        self.con.close()

    def pending_files(self, table: str) -> tuple[list[RawFile], list[RawFile]]:
        """(pending, all) raw files for a table; pending = not yet processed with this size+mtime."""
        files = list_raw_files(self.cfg, table)
        seen = {
            (r[0], r[1], r[2])
            for r in self.con.execute(
                "SELECT rel_path, size_bytes, mtime_ns FROM etl_files WHERE table_name = ?", [table]
            ).fetchall()
        }
        return [f for f in files if f.key not in seen], files

    def mark_processed(self, table: str, files: list[RawFile]) -> None:
        """Record files as processed by this run (watermark)."""
        rows = [(table, f.rel_path, f.size, f.mtime_ns, self.cfg.run_id, dt.datetime.now()) for f in files]
        self.con.executemany(
            "INSERT OR REPLACE INTO etl_files VALUES (?, ?, ?, ?, ?, ?)", rows
        ) if rows else None

    def record_run(self, table: str, started: dt.datetime, *, files_read: int, rows_read: int,
                   rows_valid: int, rows_quarantined: int, rows_pk_deduped: int, status: str) -> None:
        """Append one etl_runs row with the counts of a table's run."""
        self.con.execute(
            "INSERT INTO etl_runs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [self.cfg.run_id, table, started, dt.datetime.now(), files_read, rows_read,
             rows_valid, rows_quarantined, rows_pk_deduped, status],
        )

    def record_findings(self, table: str, findings: dict[str, int]) -> None:
        """Store non-zero quality finding counts (rule id -> rows) for this run."""
        rows = [(self.cfg.run_id, table, rule, n) for rule, n in findings.items() if n]
        if rows:
            self.con.executemany("INSERT INTO quality_findings VALUES (?, ?, ?, ?)", rows)

    def runs(self, table: str | None = None):
        """All etl_runs rows, optionally for one table, oldest first."""
        q = "SELECT * FROM etl_runs" + (" WHERE table_name = ?" if table else "") + " ORDER BY started_at"
        return self.con.execute(q, [table] if table else []).fetchall()
