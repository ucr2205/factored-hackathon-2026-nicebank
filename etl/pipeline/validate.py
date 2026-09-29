"""Contract validation: stg_out is pulled into Polars in bounded batches and checked with Pandera.

Partitioned tables are validated one event-month at a time (~430k rows for digital_events), so the
15.6M-row table never sits in memory at once. Failing rows land in _quarantine by _rid; the silver
write later excludes every quarantined _rid.
"""

from __future__ import annotations

import duckdb
from pandera.errors import SchemaErrors

import pandera.polars as pa

from .specs import TableSpec


def _batches(con: duckdb.DuckDBPyConnection, spec: TableSpec) -> list[str]:
    if spec.partitioned_silver and spec.event:
        months = [r[0] for r in con.execute(
            "SELECT DISTINCT strftime(event_date, '%Y-%m') FROM stg_out ORDER BY 1").fetchall()]
        return [f"strftime(event_date, '%Y-%m') = '{m}'" for m in months]
    return ["TRUE"]


def validate_table(con: duckdb.DuckDBPyConnection, spec: TableSpec,
                   schema: pa.DataFrameSchema) -> int:
    """Runs the contract over every stg_out row; returns how many rows it quarantined."""
    bad_rows: list[tuple[int, str, str]] = []
    for cond in _batches(con, spec):
        df = con.execute(f"SELECT * FROM stg_out WHERE {cond}").pl()
        if df.is_empty():
            continue
        try:
            schema.validate(df, lazy=True)
        except SchemaErrors as err:
            rids = df["_rid"]
            for fc in err.failure_cases.iter_rows(named=True):
                if fc["index"] is None:
                    continue
                check = (fc["check"] or "check").split("(")[0]
                rule = f"contract.{fc['column']}.{check}"
                reason = f"{fc['column']} failed {check} (value: {str(fc['failure_case'])[:80]})"
                bad_rows.append((int(rids[fc["index"]]), rule, reason))
    if bad_rows:
        con.executemany(
            "INSERT INTO _quarantine VALUES (?, ?, ?, 'contract')", bad_rows
        )
    return len({r[0] for r in bad_rows})
