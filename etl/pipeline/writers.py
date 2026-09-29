"""Parquet writers: silver tables (full replace or per-month partition swap) and quarantine files.

Every write goes to a temp directory first and is swapped in with rename, so a crashed run never
leaves a half-written silver table. Windows cannot atomically replace a non-empty directory, so the
swap is remove-then-rename; the pipeline is the only writer, and readers re-open per query.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import duckdb

from .config import PipelineConfig

PARQUET_OPTS = "FORMAT parquet, COMPRESSION zstd"


def _swap(tmp: Path, final: Path) -> None:
    final.parent.mkdir(parents=True, exist_ok=True)
    if final.exists():
        shutil.rmtree(final)
    tmp.rename(final)


def write_silver_full(con: duckdb.DuckDBPyConnection, cfg: PipelineConfig, table: str, select_sql: str) -> None:
    """Replace the whole silver table with the result of select_sql (one parquet file)."""
    tmp = cfg.silver_dir / f"_tmp_{table}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    con.execute(f"COPY ({select_sql}) TO '{(tmp / 'data.parquet').as_posix()}' ({PARQUET_OPTS})")
    _swap(tmp, cfg.silver_path(table))


def write_silver_months(con: duckdb.DuckDBPyConnection, cfg: PipelineConfig, table: str,
                        select_sql: str, event_col: str) -> list[str]:
    """Rebuild only the event-month partitions present in select_sql; other months stay untouched.

    Returns the list of 'YYYY-MM' partitions written.
    """
    tmp = cfg.silver_dir / f"_tmp_{table}"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True)
    con.execute(
        f"COPY (SELECT *, year({event_col}) AS event_year, month({event_col}) AS event_month "
        f"FROM ({select_sql})) TO '{tmp.as_posix()}' "
        f"({PARQUET_OPTS}, PARTITION_BY (event_year, event_month), OVERWRITE_OR_IGNORE)"
    )
    final = cfg.silver_path(table)
    written = []
    for year_dir in sorted(tmp.glob("event_year=*")):
        for month_dir in sorted(year_dir.glob("event_month=*")):
            rel = month_dir.relative_to(tmp)
            _swap(month_dir, final / rel)
            written.append(f"{year_dir.name.split('=')[1]}-{int(month_dir.name.split('=')[1]):02d}")
    shutil.rmtree(tmp, ignore_errors=True)
    return written


def silver_glob(cfg: PipelineConfig, table: str) -> str:
    return (cfg.silver_path(table) / "**" / "*.parquet").as_posix()


def silver_exists(cfg: PipelineConfig, table: str) -> bool:
    root = cfg.silver_path(table)
    return root.exists() and any(root.rglob("*.parquet"))


def attach_silver(con: duckdb.DuckDBPyConnection, cfg: PipelineConfig, tables: tuple[str, ...]) -> None:
    """Expose already-built silver tables as views silver_<name> for joins."""
    for t in tables:
        con.execute(
            f"CREATE OR REPLACE VIEW silver_{t} AS "
            f"SELECT * FROM read_parquet('{silver_glob(cfg, t)}', hive_partitioning = true)"
        )


def write_quarantine(con: duckdb.DuckDBPyConnection, cfg: PipelineConfig, table: str) -> int:
    """Write stg_raw rows listed in _quarantine (rule ids aggregated per row); returns row count."""
    n = con.execute("SELECT count(DISTINCT _rid) FROM _quarantine").fetchone()[0]
    if not n:
        return 0
    path = cfg.quarantine_path(table)
    path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(
        f"""COPY (
            SELECT r.* EXCLUDE (_rid), q.rule_id, q.reason, q.stage,
                   '{cfg.run_id}' AS run_id, now() AS quarantined_at
            FROM stg_raw r
            JOIN (SELECT _rid, string_agg(rule_id, '; ' ORDER BY rule_id) AS rule_id,
                         string_agg(reason, '; ' ORDER BY rule_id) AS reason,
                         string_agg(DISTINCT stage, '; ') AS stage
                  FROM _quarantine GROUP BY _rid) q USING (_rid)
        ) TO '{path.as_posix()}' ({PARQUET_OPTS})"""
    )
    return n
