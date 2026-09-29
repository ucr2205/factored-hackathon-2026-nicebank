"""Raw -> silver pipeline entry point (make etl).

Incremental and idempotent: a file is processed once per (path, size, mtime); with nothing pending a
table is a fast no-op, and re-synced or late partitions rebuild only the event months they touch.
Every run records lineage (etl_runs, etl_files, quality_findings) in data/etl_state.duckdb and writes
rejected rows with their rule ids under data/quarantine/. Rules: docs/etl_rules.md.

Usage: python etl/pipeline/run.py [--tables t1 t2 ...] [--full] [--raw-dir PATH]
  --tables   only these tables (their silver dependencies must already exist)
  --full     reprocess everything even if the watermark says it is up to date
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import duckdb

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from etl.pipeline import coherence, stage_sql, writers  # noqa: E402
from etl.pipeline.config import PipelineConfig  # noqa: E402
from etl.pipeline.contracts import build_schema  # noqa: E402
from etl.pipeline.specs import TABLES, topo_order  # noqa: E402
from etl.pipeline.state import RawFile, StateStore  # noqa: E402
from etl.pipeline.validate import validate_table  # noqa: E402


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def affected_months(con: duckdb.DuckDBPyConnection, cfg: PipelineConfig, table: str,
                    pending: list[RawFile]) -> list[str]:
    """Event months a set of pending files can change: the months of their own rows, plus the
    months where silver already holds a row with the same primary key (a late arrival must replace
    its older version wherever it lives)."""
    spec = TABLES[table]
    paths = [(cfg.raw_dir / f.rel_path).as_posix() for f in pending]
    con.execute(
        "CREATE OR REPLACE TEMP TABLE _pending AS SELECT * FROM "
        "read_csv(?, header = true, all_varchar = true, union_by_name = true)", [paths])
    ev = f"try_cast({spec.event} AS TIMESTAMP)"
    months = {r[0] for r in con.execute(
        f"SELECT DISTINCT strftime({ev}, '%Y-%m') FROM _pending WHERE {ev} IS NOT NULL").fetchall()}
    pk = spec.pk[0]
    months |= {r[0] for r in con.execute(
        f"SELECT DISTINCT strftime(s.event_date, '%Y-%m') "
        f"FROM read_parquet('{writers.silver_glob(cfg, table)}', hive_partitioning = true) s "
        f"JOIN _pending p ON s.{pk} = p.{pk}").fetchall()}
    return sorted(m for m in months if m)


def run_table(cfg: PipelineConfig, state: StateStore, table: str, full: bool) -> None:
    spec = TABLES[table]
    started = dt.datetime.now()
    pending, all_files = state.pending_files(table)
    if not all_files:
        log(f"{table}: no raw files, skipped")
        return
    if not pending and not full and writers.silver_exists(cfg, table):
        log(f"{table}: up to date ({len(all_files)} file(s))")
        return

    con = duckdb.connect()
    for pragma in cfg.duckdb_pragmas():
        con.execute(pragma)
    writers.attach_silver(con, cfg, spec.depends_on)

    months: list[str] | None = None
    if (spec.partitioned_silver and not full and pending and len(pending) < len(all_files)
            and writers.silver_exists(cfg, table)):
        months = affected_months(con, cfg, table, pending)
        log(f"{table}: late/changed files -> rebuilding {len(months)} event month(s)")

    stage_sql.ingest(con, cfg, table, spec, months)
    rows_read = con.execute("SELECT count(*) FROM stg_raw").fetchone()[0]
    findings = stage_sql.clean(con, table, spec)
    stage_sql.build_ext(con, table)
    superseded = stage_sql.dedup(con, table, spec)
    stage_sql.apply_business_keys(con, spec)
    stage_sql.project_out(con, spec, months)
    validate_table(con, spec, build_schema(spec))
    findings |= coherence.collect_findings(con, table, spec)

    out_sql = ("SELECT * EXCLUDE (_rid) FROM stg_out "
               "WHERE _rid NOT IN (SELECT _rid FROM _quarantine)")
    rows_valid = con.execute(
        "SELECT count(*) FROM stg_out WHERE _rid NOT IN (SELECT _rid FROM _quarantine)").fetchone()[0]
    if spec.partitioned_silver:
        parts = writers.write_silver_months(con, cfg, table, out_sql, spec.event)
        scope = f"{len(parts)} partition(s)"
    else:
        writers.write_silver_full(con, cfg, table, out_sql)
        scope = "full"
    quarantined = writers.write_quarantine(con, cfg, table)
    for dim, (source, dim_sql) in stage_sql.DIMS.items():
        if source == table:
            writers.write_silver_full(con, cfg, dim, dim_sql)

    state.mark_processed(table, pending or all_files)
    state.record_run(table, started, files_read=len(pending or all_files), rows_read=rows_read,
                     rows_valid=rows_valid, rows_quarantined=quarantined,
                     rows_pk_deduped=superseded, status="ok")
    state.record_findings(table, findings)
    con.close()
    log(f"{table}: {rows_read:,} read -> {rows_valid:,} silver ({scope}); "
        f"{superseded:,} superseded, {quarantined:,} quarantined, {len(findings)} finding(s)")


def run_pipeline(cfg: PipelineConfig, tables: list[str] | None = None, full: bool = False) -> None:
    state = StateStore(cfg)
    try:
        for table in topo_order(tables):
            for dep in TABLES[table].depends_on:
                if not writers.silver_exists(cfg, dep) and (tables is None or dep not in tables):
                    raise SystemExit(f"{table} needs silver '{dep}': run it first or drop --tables")
            run_table(cfg, state, table, full)
    finally:
        state.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tables", nargs="*", choices=list(TABLES), help="Only these tables.")
    parser.add_argument("--full", action="store_true", help="Ignore the watermark and reprocess.")
    parser.add_argument("--raw-dir", type=Path, default=None, help="Alternative raw directory.")
    args = parser.parse_args()
    cfg = PipelineConfig() if args.raw_dir is None else PipelineConfig(raw_dir=args.raw_dir)
    if not cfg.raw_dir.exists():
        raise SystemExit(f"{cfg.raw_dir} not found: sync the dataset or link a local copy there.")
    started = time.time()
    run_pipeline(cfg, args.tables, args.full)
    log(f"pipeline finished in {time.time() - started:,.0f} s (run {cfg.run_id})")


if __name__ == "__main__":
    main()
