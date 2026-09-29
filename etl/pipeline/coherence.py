"""Quality findings: generator incoherences are counted and recorded, never deleted (rule group E).

Every boolean flag column the pipeline adds is counted generically; the extra queries below cover
incoherences that do not warrant a per-row column. Counts land in quality_findings (etl_state.duckdb)
under the current run, so each load documents what it saw.
"""

from __future__ import annotations

import duckdb

from .specs import TableSpec

DATASET_END = "DATE '2026-06-17'"

EXTRA_FINDINGS: dict[str, list[tuple[str, str]]] = {
    "customers": [
        ("age.registered_minor",
         "count_if(date_diff('year', date_of_birth, CAST(registration_date AS DATE)) < 18)"),
        ("age.student_over_30",
         f"count_if(segment = 'Student' AND date_diff('year', date_of_birth, {DATASET_END}) > 30)"),
    ],
    "products": [
        ("dict.credit_card_without_limit",
         "count_if(product_type = 'Credit Card' AND credit_limit IS NULL)"),
        ("dict.card_without_expiration",
         "count_if(product_type IN ('Credit Card', 'Debit Card') AND expiration_date IS NULL)"),
    ],
    "transactions": [
        ("coherence.atm_channel_not_withdrawal",
         "count_if(channel = 'ATM' AND transaction_type <> 'Withdrawal')"),
        ("coherence.withdrawal_not_atm_or_branch",
         "count_if(transaction_type = 'Withdrawal' AND channel NOT IN ('ATM', 'Branch'))"),
        ("coherence.purchase_without_merchant",
         "count_if(transaction_type = 'Purchase' AND merchant_name IS NULL)"),
    ],
    "call_transcripts": [
        ("dict.duration_seconds_null", "count_if(duration_seconds IS NULL)"),
    ],
    "complaints": [
        ("coherence.assigned_agent_without_date",
         "count_if(assigned_agent_id IS NOT NULL AND assignment_date IS NULL)"),
        ("coherence.assignment_date_without_agent",
         "count_if(assigned_agent_id IS NULL AND assignment_date IS NOT NULL)"),
    ],
}


def collect_findings(con: duckdb.DuckDBPyConnection, table: str, spec: TableSpec) -> dict[str, int]:
    """Counts every flag column plus the table's extra queries, in one aggregate pass."""
    silver_cols = {spec.rename.get(c, c) for c in spec.types if c not in spec.drop}
    flags = [name for name, typ, *_ in con.execute("DESCRIBE stg_out").fetchall()
             if typ == "BOOLEAN" and name not in silver_cols]
    exprs = [(f"flag.{f}", f"count_if({f})") for f in flags]
    exprs += EXTRA_FINDINGS.get(table, [])
    if not exprs:
        return {}
    row = con.execute(f"SELECT {', '.join(e for _, e in exprs)} FROM stg_out").fetchone()
    return {rule: int(n or 0) for (rule, _), n in zip(exprs, row) if n}
