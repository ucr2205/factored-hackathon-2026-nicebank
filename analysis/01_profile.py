"""Profile the data quality of the 13 raw tables and write docs/data_quality_report.md.

Every table is read once from data/raw/ into a local DuckDB file (data/profile.duckdb, git-ignored) with all
columns as text, so a malformed value is counted instead of breaking the load. Per table the script reports
row counts against the organizer's figures, nulls, inferred types and malformed values, exact and primary-key
duplicates, categorical values, monthly volume, late arrivals (process_date vs event date) and schema drift in
content (null rates and categorical values that change over time). Cross-table checks cover orphans, owner
consistency, date order, FX (amount_usd against the transaction-date rate, ADR 0002), country spellings, phone
prefixes and coordinates.

Personal columns (names, documents, contact data, card numbers, IPs, free text) are measured, but their values
are never written to the report or to the detail files.

Usage: python analysis/01_profile.py [--tables t1 t2 ...] [--reload]
  --tables  profile only these tables (the report still covers every table profiled so far)
  --reload  re-read the CSV files even if data/raw/ did not change since the last load
Outputs: docs/data_quality_report.md, detail CSV/JSON files in analysis/out/profile/ (git-ignored).
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
DB_FILE = REPO_ROOT / "data" / "profile.duckdb"
OUT_DIR = REPO_ROOT / "analysis" / "out" / "profile"
REPORT = REPO_ROOT / "docs" / "data_quality_report.md"

sys.path.insert(0, str(REPO_ROOT / "etl"))
from inventory import EXPECTED_ROWS  # noqa: E402  (organizer's published row counts)

WINDOW = (dt.date(2023, 6, 17), dt.date(2026, 6, 17))  # organizer's stated data window
TYPE_SHARE = 0.99       # a column gets a type when at least 99% of its non-null values parse as it
CATEGORICAL_MAX = 25    # columns with at most this many distinct values get their values listed
DRIFT_PP = 0.05         # monthly null rate range (max - min) that flags a column as drifting
APPROX_ABOVE = 5_000_000  # tables larger than this get approximate distinct counts (marked ≈)
NULL_TOKENS = ("none", "nan", "null", "n/a", "na", "-", "?", "undefined")

# Measured but never shown: values of these columns are personal data or free text.
PII = {"first_name", "last_name", "document_number", "date_of_birth", "email", "mobile_phone", "landline_phone",
       "phone", "address", "postal_code", "product_number", "ip_address", "full_text", "customer_text",
       "agent_text", "mentioned_entities", "open_comments", "latitude", "longitude", "session_id"}


@dataclass(frozen=True)
class Table:
    pk: tuple[str, ...]
    event: str | None = None                  # business event timestamp (process_date is the load date)
    parents: dict[str, tuple[str, str]] = field(default_factory=dict)  # column -> (parent table, key)
    partitioned: bool = True


TABLES: dict[str, Table] = {
    "branches": Table(("branch_id",), partitioned=False),
    "customers": Table(("customer_id",), partitioned=False,
                       parents={"registration_branch_id": ("branches", "branch_id")}),
    "marketing_campaigns": Table(("campaign_id",), partitioned=False),
    "products": Table(("product_id",), partitioned=False,
                      parents={"customer_id": ("customers", "customer_id"),
                               "opening_branch_id": ("branches", "branch_id")}),
    "service_agents": Table(("agent_id",), partitioned=False,
                            parents={"assigned_branch_id": ("branches", "branch_id")}),
    "daily_exchange_rates": Table(("date", "source_currency", "target_currency"), partitioned=False),
    "transactions": Table(("transaction_id",), "transaction_date",
                          {"product_id": ("products", "product_id"), "customer_id": ("customers", "customer_id"),
                           "branch_id": ("branches", "branch_id")}),
    "complaints": Table(("complaint_id",), "creation_date",
                        {"customer_id": ("customers", "customer_id"),
                         "affected_product_id": ("products", "product_id"),
                         "related_branch_id": ("branches", "branch_id"),
                         "origin_interaction_id": ("call_center_interactions", "interaction_id"),
                         "assigned_agent_id": ("service_agents", "agent_id")}),
    "call_center_interactions": Table(("interaction_id",), "interaction_date",
                                      {"customer_id": ("customers", "customer_id"),
                                       "agent_id": ("service_agents", "agent_id")}),
    "call_transcripts": Table(("transcript_id",), None,
                              {"interaction_id": ("call_center_interactions", "interaction_id"),
                               "customer_id": ("customers", "customer_id"),
                               "agent_id": ("service_agents", "agent_id")}),
    "campaign_sends": Table(("send_id",), "send_date",
                            {"campaign_id": ("marketing_campaigns", "campaign_id"),
                             "customer_id": ("customers", "customer_id")}),
    "satisfaction_surveys": Table(("survey_id",), "survey_date",
                                  {"interaction_id": ("call_center_interactions", "interaction_id"),
                                   "customer_id": ("customers", "customer_id"),
                                   "agent_id": ("service_agents", "agent_id")}),
    "digital_events": Table(("event_id",), "event_date",
                            {"customer_id": ("customers", "customer_id"), "product_id": ("products", "product_id")}),
}

# (description, child, child fk, parent, parent key, child column, parent column): the columns must agree.
CONSISTENCY = [
    ("transaction owner = product owner", "transactions", "product_id", "products", "product_id",
     "customer_id", "customer_id"),
    ("transaction currency = product currency", "transactions", "product_id", "products", "product_id",
     "currency", "currency"),
    ("complaint customer = owner of the affected product", "complaints", "affected_product_id", "products",
     "product_id", "customer_id", "customer_id"),
    ("complaint customer = customer of the origin interaction", "complaints", "origin_interaction_id",
     "call_center_interactions", "interaction_id", "customer_id", "customer_id"),
    ("transcript customer = interaction customer", "call_transcripts", "interaction_id",
     "call_center_interactions", "interaction_id", "customer_id", "customer_id"),
    ("transcript agent = interaction agent", "call_transcripts", "interaction_id", "call_center_interactions",
     "interaction_id", "agent_id", "agent_id"),
    ("survey customer = interaction customer", "satisfaction_surveys", "interaction_id",
     "call_center_interactions", "interaction_id", "customer_id", "customer_id"),
    ("survey agent = interaction agent", "satisfaction_surveys", "interaction_id", "call_center_interactions",
     "interaction_id", "agent_id", "agent_id"),
    ("digital event customer = product owner", "digital_events", "product_id", "products", "product_id",
     "customer_id", "customer_id"),
]

# (table, earlier, later): the later column must not precede the earlier one.
DATE_ORDER = [
    ("customers", "date_of_birth", "registration_date"), ("customers", "registration_date", "last_updated"),
    ("products", "opening_date", "expiration_date"), ("products", "opening_date", "last_transaction_date"),
    ("marketing_campaigns", "start_date", "end_date"),
    ("complaints", "creation_date", "assignment_date"), ("complaints", "creation_date", "first_response_date"),
    ("complaints", "first_response_date", "resolution_date"), ("complaints", "creation_date", "resolution_date"),
    ("complaints", "resolution_date", "closing_date"),
    ("campaign_sends", "send_date", "open_date"), ("campaign_sends", "open_date", "click_date"),
    ("campaign_sends", "send_date", "conversion_date"),
]

PHONES = [("customers", "mobile_phone", "country"), ("customers", "landline_phone", "country"),
          ("branches", "phone", "country"), ("service_agents", "phone", "country_of_origin")]
COUNTRY_PREFIX = {"mexico": "+52", "colombia": "+57", "argentina": "+54"}
COORDS = [("branches", "latitude", "longitude"), ("transactions", "latitude", "longitude")]
COUNTRY_COLUMNS = [("customers", "country"), ("branches", "country"), ("service_agents", "country_of_origin"),
                   ("marketing_campaigns", "target_country"), ("transactions", "transaction_country"),
                   ("campaign_sends", "open_country"), ("digital_events", "ip_country")]


# ---------- helpers ----------

def q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def lit(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def raw(name: str) -> str:
    return q(f"raw_{name}")


def as_ts(col: str) -> str:
    return f"try_cast({q(col)} AS TIMESTAMP)"


def as_num(col: str) -> str:
    return f"try_cast({q(col)} AS DOUBLE)"


def null_like(col: str) -> str:
    return f"lower(trim({q(col)})) IN ({', '.join(lit(t) for t in NULL_TOKENS)})"


TYPE_PATTERNS = {
    "boolean": lambda c: f"lower({c}) IN ('true', 'false')",
    "integer": lambda c: f"regexp_full_match({c}, '-?[0-9]+')",
    "decimal": lambda c: f"regexp_full_match({c}, '-?[0-9]+([.][0-9]+)?([eE][-+]?[0-9]+)?')",
    "timestamp": lambda c: (f"(regexp_full_match({c}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}[ T][0-9]{{2}}:[0-9]{{2}}"
                            f"(:[0-9]{{2}}([.][0-9]+)?)?') AND try_cast({c} AS TIMESTAMP) IS NOT NULL)"),
    "date": lambda c: f"(regexp_full_match({c}, '[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}') AND try_cast({c} AS DATE) IS NOT NULL)",
    "time": lambda c: f"(regexp_full_match({c}, '[0-9]{{2}}:[0-9]{{2}}(:[0-9]{{2}})?') AND try_cast({c} AS TIME) IS NOT NULL)",
}
TYPE_PATTERNS["date or timestamp"] = lambda c: f"({TYPE_PATTERNS['date'](c)} OR {TYPE_PATTERNS['timestamp'](c)})"
TYPE_ORDER = ["boolean", "integer", "decimal", "timestamp", "date", "date or timestamp", "time"]


def pct(part: float, whole: float, digits: int = 1) -> str:
    return "—" if not whole else f"{100 * part / whole:.{digits}f}%"


def n(value) -> str:
    return "—" if value is None else f"{value:,}"


def write_csv(path: Path, header: list[str], rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def loaded_tables(con: duckdb.DuckDBPyConnection) -> set[str]:
    names = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    return {t for t in TABLES if f"raw_{t}" in names}


def business_columns(con: duckdb.DuckDBPyConnection, name: str) -> list[str]:
    cols = [r[0] for r in con.execute(f"DESCRIBE {raw(name)}").fetchall()]
    return [c for c in cols if not c.startswith("_")]


# ---------- load ----------

def source_files(name: str, t: Table) -> list[Path]:
    if t.partitioned:
        return sorted((RAW_DIR / name).rglob("*.csv"))
    path = RAW_DIR / f"{name}.csv"
    return [path] if path.exists() else []


def load(con: duckdb.DuckDBPyConnection, name: str, t: Table, reload: bool) -> bool:
    files = source_files(name, t)
    if not files:
        log(f"{name}: no files in data/raw/, skipped")
        return False
    signature = [len(files), sum(p.stat().st_size for p in files)]
    con.execute("""CREATE TABLE IF NOT EXISTS _load_meta (tbl VARCHAR PRIMARY KEY, files BIGINT, bytes BIGINT,
                   rows BIGINT, rejected BIGINT, loaded_at TIMESTAMP)""")
    known = con.execute("SELECT files, bytes FROM _load_meta WHERE tbl = ?", [name]).fetchone()
    if not reload and known and list(known) == signature and name in loaded_tables(con):
        log(f"{name}: unchanged since last load, reusing")
        return True

    log(f"{name}: loading {len(files):,} file(s)")
    glob = (RAW_DIR / name / "**" / "*.csv" if t.partitioned else files[0]).as_posix()
    opts = (f"header = true, all_varchar = true, filename = true, store_rejects = true, "
            f"rejects_table = 'rej_{name}', rejects_scan = 'rejscan_{name}'")
    if t.partitioned:
        opts += ", hive_partitioning = true"
        select = (f"SELECT * EXCLUDE (filename, year, month, day), parse_filename(filename) AS _file, "
                  f"make_date(year::INT, month::INT, day::INT) AS _part_date FROM read_csv({lit(glob)}, {opts})")
    else:
        select = (f"SELECT * EXCLUDE (filename), parse_filename(filename) AS _file, NULL::DATE AS _part_date "
                  f"FROM read_csv({lit(glob)}, {opts})")
    con.execute(f"CREATE OR REPLACE TABLE {raw(name)} AS {select}")
    rows = con.execute(f"SELECT count(*) FROM {raw(name)}").fetchone()[0]
    try:
        rejected = con.execute(f"SELECT count(*) FROM rej_{name}").fetchone()[0]
        examples = con.execute(
            f"SELECT error_type, count(*) FROM rej_{name} GROUP BY 1 ORDER BY 2 DESC, 1").fetchall()
    except duckdb.Error:
        rejected, examples = 0, []
    con.execute("INSERT OR REPLACE INTO _load_meta VALUES (?, ?, ?, ?, ?, now())", [name, *signature, rows, rejected])
    if examples:
        write_csv(OUT_DIR / name / "rejected_lines.csv", ["error_type", "lines"], examples)
    log(f"{name}: {rows:,} rows, {rejected:,} rejected line(s)")
    return True


# ---------- per-table profile ----------

def column_stats(con, name: str, cols: list[str]) -> list[dict]:
    # Exact distinct counts up to APPROX_ABOVE rows; the approximation is off by >10% on some id columns.
    exact = con.execute(f"SELECT count(*) FROM {raw(name)}").fetchone()[0] <= APPROX_ABOVE
    distinct = "count(DISTINCT {})" if exact else "approx_count_distinct({})"
    exprs = []
    for c in cols:
        qc = q(c)
        exprs += [f"count({qc})", distinct.format(qc), f"count_if({qc} <> trim({qc}))",
                  f"count_if({null_like(c)})"]
        exprs += [f"count_if({TYPE_PATTERNS[k](qc)})" for k in TYPE_ORDER]
    row = con.execute(f"SELECT count(*), {', '.join(exprs)} FROM {raw(name)}").fetchone()
    # count_if over an all-null column returns NULL, not 0.
    total, values, width = row[0], [v or 0 for v in row[1:]], 4 + len(TYPE_ORDER)
    out = []
    for i, c in enumerate(cols):
        nonnull, ndistinct, padded, tokens, *matches = values[i * width:(i + 1) * width]
        real = nonnull - tokens
        dtype, malformed = "text", 0
        if real == 0:
            dtype = "empty"
        else:
            for k, m in zip(TYPE_ORDER, matches):
                if m / real >= TYPE_SHARE:
                    dtype, malformed = k, real - m
                    break
        out.append({"column": c, "rows": total, "nulls": total - nonnull, "null_tokens": tokens,
                    "null_rate": (total - real) / total if total else 0,
                    "distinct": ndistinct, "distinct_exact": exact,
                    "padded": padded, "type": dtype, "malformed": malformed})
    return out


def categorical_values(con, name: str, stats: list[dict], partitioned: bool) -> dict[str, list]:
    """Value counts (and first/last partition month) for low-cardinality, non-personal columns."""
    out = {}
    for s in stats:
        c = s["column"]
        if c in PII or s["distinct"] > CATEGORICAL_MAX + 5 or s["type"] in ("empty", "date", "timestamp", "date or timestamp"):
            continue
        month = "strftime(min(_part_date), '%Y-%m'), strftime(max(_part_date), '%Y-%m')" if partitioned else "NULL, NULL"
        # Ties broken by value so the report is identical on every run.
        rows = con.execute(f"SELECT {q(c)}, count(*), {month} FROM {raw(name)} "
                           "GROUP BY 1 ORDER BY 2 DESC, 1 NULLS FIRST").fetchall()
        if len(rows) <= CATEGORICAL_MAX + 1:  # +1 for NULL
            out[c] = rows
    return out


def malformed_detail(con, name: str, stats: list[dict], partitioned: bool) -> dict[str, dict]:
    out = {}
    for s in stats:
        if not s["malformed"]:
            continue
        c, qc = s["column"], q(s["column"])
        bad = f"{qc} IS NOT NULL AND NOT {null_like(c)} AND NOT {TYPE_PATTERNS[s['type']](qc)}"
        detail = {}
        if c not in PII:
            detail["examples"] = con.execute(
                f"SELECT {qc}, count(*) FROM {raw(name)} WHERE {bad} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 5").fetchall()
        if partitioned:
            detail["months"] = con.execute(
                f"SELECT strftime(min(_part_date), '%Y-%m'), strftime(max(_part_date), '%Y-%m'), "
                f"count(DISTINCT date_trunc('month', _part_date)) FROM {raw(name)} WHERE {bad}").fetchone()
        out[c] = detail
    return out


def pk_checks(con, name: str, t: Table, cols: list[str]) -> dict:
    keys = ", ".join(q(k) for k in t.pk)
    rowhash = f"hash({', '.join(q(c) for c in cols)})"
    not_null = " AND ".join(f"{q(k)} IS NOT NULL" for k in t.pk)
    # A content duplicate repeats every column except the key and the load date: the same record re-issued
    # under a new id, which key-based dedup would miss. Only meaningful for generated ids; on a natural key
    # (exchange rates by date and pair) equal content on different days is legitimate.
    surrogate = len(t.pk) == 1 and t.pk[0].endswith("_id")
    content = [c for c in cols if c not in t.pk and c != "process_date"] if surrogate else cols
    total, exact_distinct, null_pk, content_distinct = con.execute(
        f"SELECT count(*), count(DISTINCT {rowhash}), count_if(NOT ({not_null})), "
        f"count(DISTINCT hash({', '.join(q(c) for c in content)})) FROM {raw(name)}").fetchone()
    g = con.execute(f"""
        WITH g AS (SELECT {keys}, count(*) AS n, count(DISTINCT {rowhash}) AS v, count(DISTINCT _file) AS f,
                          date_diff('day', min(_part_date), max(_part_date)) AS span
                   FROM {raw(name)} WHERE {not_null} GROUP BY ALL)
        SELECT count(*), count_if(n > 1), coalesce(sum(n - 1) FILTER (WHERE n > 1), 0),
               count_if(n > 1 AND v = 1), count_if(n > 1 AND v > 1), count_if(n > 1 AND f > 1),
               median(span) FILTER (WHERE n > 1), max(span) FILTER (WHERE n > 1), max(n)
        FROM g""").fetchone()
    res = {"rows": total, "exact_dup_rows": total - exact_distinct, "content_dup_rows": total - content_distinct,
           "null_pk": null_pk, "distinct_pk": g[0],
           "dup_groups": g[1], "dup_extra_rows": g[2], "identical_groups": g[3], "conflicting_groups": g[4],
           "multi_file_groups": g[5], "dup_span_median_days": g[6], "dup_span_max_days": g[7], "max_copies": g[8],
           "differing_columns": []}
    if res["conflicting_groups"]:
        diffs = ", ".join(f"count_if(d_{i} > 1)" for i in range(len(cols)))
        inner = ", ".join(f"count(DISTINCT coalesce({q(c)}, '<null>')) AS d_{i}" for i, c in enumerate(cols))
        counts = con.execute(f"""
            WITH dup AS (SELECT {keys} FROM {raw(name)} WHERE {not_null} GROUP BY ALL
                         HAVING count(DISTINCT {rowhash}) > 1)
            SELECT {diffs} FROM (SELECT {keys}, {inner} FROM {raw(name)} JOIN dup USING ({keys}) GROUP BY ALL)
        """).fetchone()
        res["differing_columns"] = sorted(((c, k) for c, k in zip(cols, counts) if k), key=lambda x: -x[1])
    return res


def timing_checks(con, name: str, t: Table, cols: list[str]) -> dict:
    """Event range, late arrivals (process_date - event date) and how partitions are dated."""
    res = {}
    ev = as_ts(t.event) if t.event else None
    proc = "try_cast(process_date AS DATE)" if "process_date" in cols else None
    if ev:
        r = con.execute(f"""SELECT min({ev}), max({ev}), count({ev}),
                count_if({ev}::DATE < DATE '{WINDOW[0]}' OR {ev}::DATE > DATE '{WINDOW[1]}'),
                count_if(_part_date = {ev}::DATE) FROM {raw(name)}""").fetchone()
        res.update(event_min=str(r[0]), event_max=str(r[1]), event_parsed=r[2], outside_window=r[3],
                   partition_is_event_day=r[4])
    if proc:
        res["partition_is_process_day"] = con.execute(
            f"SELECT count_if(_part_date = {proc}) FROM {raw(name)}").fetchone()[0]
    if ev and proc:
        lag = f"date_diff('day', {ev}::DATE, {proc})"
        r = con.execute(f"""SELECT count({lag}), count_if({lag} < 0), count_if({lag} = 0), count_if({lag} = 1),
                count_if({lag} BETWEEN 2 AND 7), count_if({lag} > 7), min({lag}), median({lag}),
                quantile_cont({lag}, 0.95), max({lag}) FROM {raw(name)}""").fetchone()
        res["lag"] = dict(zip(["rows", "negative", "same_day", "one_day", "two_to_seven", "over_seven",
                               "min", "median", "p95", "max"], r))
        # Negative lags confined to the early hours mean a day cut-off (or time-zone offset), not bad data.
        res["negative_hours"] = con.execute(f"""SELECT min(hour({ev})), max(hour({ev})),
                (SELECT min(hour({ev})) FROM {raw(name)} WHERE {lag} = 0) FROM {raw(name)} WHERE {lag} < 0""").fetchone()
        hist = con.execute(f"SELECT {lag} AS d, count(*) FROM {raw(name)} WHERE {lag} IS NOT NULL "
                           f"GROUP BY 1 ORDER BY 1").fetchall()
        write_csv(OUT_DIR / name / "lag_days.csv", ["lag_days", "rows"], hist)
    return res


def monthly_checks(con, name: str, cols: list[str], stats: list[dict]) -> dict:
    """Rows per partition month and per-column null rate per month (schema drift in content)."""
    nulls = ", ".join(f"count_if({q(c)} IS NULL OR {null_like(c)})" for c in cols)
    rows = con.execute(f"""SELECT strftime(date_trunc('month', _part_date), '%Y-%m') AS m, count(*),
                           count(DISTINCT _part_date), {nulls} FROM {raw(name)} GROUP BY 1 ORDER BY 1""").fetchall()
    write_csv(OUT_DIR / name / "monthly_rows.csv", ["month", "rows", "days"], [r[:3] for r in rows])
    write_csv(OUT_DIR / name / "monthly_null_rate.csv", ["month", *cols],
              [[r[0], *(round(v / r[1], 4) for v in r[3:])] for r in rows])
    # Partial first/last months (the window starts and ends mid-month) are compared by rows per day.
    per_day = [r[1] / r[2] for r in rows]
    drift = []
    full = rows[1:-1] if len(rows) > 3 else rows
    month_rows = sorted(r[1] for r in full)[len(full) // 2]
    for i, c in enumerate(cols):
        rates = [(r[0], r[3 + i] / r[1]) for r in full]
        lo, hi = min(rates, key=lambda x: x[1]), max(rates, key=lambda x: x[1])
        # A random null rate p over m rows moves by about sqrt(p(1-p)/m) per month; only a range well above
        # that noise (and at least DRIFT_PP) is drift. Small tables otherwise flag sampling noise.
        p = sum(v for _, v in rates) / len(rates)
        noise = 6 * (p * (1 - p) / month_rows) ** 0.5
        if hi[1] - lo[1] >= max(DRIFT_PP, noise):
            first3 = sum(v for _, v in rates[:3]) / 3
            last3 = sum(v for _, v in rates[-3:]) / 3
            drift.append({"column": c, "min_month": lo[0], "min_rate": lo[1], "max_month": hi[0],
                          "max_rate": hi[1], "first3": first3, "last3": last3})
    sorted_pd = sorted(per_day)
    return {"months": len(rows), "first_month": rows[0][0], "last_month": rows[-1][0],
            "rows_per_day_min": sorted_pd[0], "rows_per_day_median": sorted_pd[len(sorted_pd) // 2],
            "rows_per_day_max": sorted_pd[-1],
            "rows_per_day_first3": sum(per_day[:3]) / 3, "rows_per_day_last3": sum(per_day[-3:]) / 3,
            "yearly": con.execute(f"SELECT year(_part_date), count(*) FROM {raw(name)} GROUP BY 1 ORDER BY 1").fetchall(),
            "drift": drift}


def enum_drift(values: dict[str, list], first: str, last: str) -> list[dict]:
    """Categorical values that start late or stop early: schema evolution hidden in content."""
    def shift(month: str, k: int) -> str:
        y, m = map(int, month.split("-"))
        m += k
        return f"{y + (m - 1) // 12}-{(m - 1) % 12 + 1:02d}"

    out = []
    for col, rows in values.items():
        for value, count, v_first, v_last in rows:
            if value is None or v_first is None:
                continue
            if v_first > shift(first, 1) or v_last < shift(last, -1):
                out.append({"column": col, "value": value, "rows": count, "first": v_first, "last": v_last})
    return out


def profile(con, name: str, t: Table) -> dict:
    log(f"{name}: profiling")
    cols = business_columns(con, name)
    meta = con.execute("SELECT files, bytes, rows, rejected FROM _load_meta WHERE tbl = ?", [name]).fetchone()
    stats = column_stats(con, name, cols)
    values = categorical_values(con, name, stats, t.partitioned)
    summary = {"table": name, "files": meta[0], "bytes": meta[1], "rows": meta[2], "rejected_lines": meta[3],
               "expected_rows": EXPECTED_ROWS.get(name), "columns": stats, "values": values,
               "malformed": malformed_detail(con, name, stats, t.partitioned), "pk": pk_checks(con, name, t, cols),
               "timing": timing_checks(con, name, t, cols), "pk_columns": list(t.pk), "event": t.event}
    if t.partitioned:
        summary["monthly"] = monthly_checks(con, name, cols, stats)
        summary["enum_drift"] = enum_drift(values, summary["monthly"]["first_month"], summary["monthly"]["last_month"])
    write_csv(OUT_DIR / name / "columns.csv", list(stats[0].keys()), [list(s.values()) for s in stats])
    write_csv(OUT_DIR / name / "values.csv", ["column", "value", "rows", "first_month", "last_month"],
              [[c, *r] for c, rows in values.items() for r in rows])
    (OUT_DIR / name / "summary.json").write_text(json.dumps(summary, indent=1, default=str), encoding="utf-8")
    return summary


# ---------- cross-table checks ----------

def cross_checks(con, have: set[str]) -> dict:
    log("cross-table checks")
    res: dict = {"orphans": [], "consistency": [], "date_order": [], "phones": [], "coords": [], "countries": {}}

    for name, t in TABLES.items():
        for col, (parent, key) in t.parents.items():
            if name not in have or parent not in have:
                continue
            r = con.execute(f"""
                WITH p AS (SELECT DISTINCT {q(key)} AS k FROM {raw(parent)}),
                     pn AS (SELECT DISTINCT upper(trim({q(key)})) AS k FROM {raw(parent)}),
                     o AS (SELECT c.{q(col)} AS v FROM {raw(name)} c LEFT JOIN p ON c.{q(col)} = p.k
                           WHERE c.{q(col)} IS NOT NULL AND p.k IS NULL)
                SELECT (SELECT count({q(col)}) FROM {raw(name)}), count(*), count(DISTINCT v), count(pn.k),
                       list(DISTINCT v ORDER BY v)[1:3] FROM o LEFT JOIN pn ON upper(trim(o.v)) = pn.k""").fetchone()
            res["orphans"].append({"child": name, "column": col, "parent": parent, "key": key, "non_null": r[0],
                                   "orphans": r[1], "distinct_orphans": r[2], "fixable_by_normalizing": r[3],
                                   "examples": r[4]})

    for desc, child, fk, parent, key, ccol, pcol in CONSISTENCY:
        if child not in have or parent not in have:
            continue
        r = con.execute(f"""
            WITH p AS (SELECT {q(key)} AS k, any_value({q(pcol)}) AS v FROM {raw(parent)} GROUP BY 1)
            SELECT count(*), count_if(c.{q(ccol)} IS NOT NULL AND p.v IS NOT NULL AND c.{q(ccol)} <> p.v)
            FROM {raw(child)} c JOIN p ON c.{q(fk)} = p.k""").fetchone()
        res["consistency"].append({"check": desc, "child": child, "joined": r[0], "mismatches": r[1]})

    for name, a, b in DATE_ORDER:
        if name not in have:
            continue
        r = con.execute(f"""SELECT count_if({as_ts(a)} IS NOT NULL AND {as_ts(b)} IS NOT NULL),
                            count_if({as_ts(b)} < {as_ts(a)}) FROM {raw(name)}""").fetchone()
        res["date_order"].append({"table": name, "earlier": a, "later": b, "pairs": r[0], "violations": r[1]})

    if "complaints" in have:
        r = con.execute(f"""SELECT count(*), count_if(abs(date_diff('day', {as_ts('creation_date')},
                {as_ts('resolution_date')}) - {as_num('resolution_days')}) > 1) FROM {raw('complaints')}
                WHERE {as_ts('resolution_date')} IS NOT NULL AND {as_num('resolution_days')} IS NOT NULL""").fetchone()
        res["resolution_days"] = {"rows": r[0], "mismatches": r[1]}

    if {"call_center_interactions", "call_transcripts"} <= have:
        r = con.execute(f"""
            WITH t AS (SELECT DISTINCT interaction_id FROM {raw('call_transcripts')})
            SELECT count_if(lower(i.has_transcript) = 'true'),
                   count_if(lower(i.has_transcript) = 'true' AND t.interaction_id IS NOT NULL),
                   count_if(lower(i.has_transcript) = 'false' AND t.interaction_id IS NOT NULL),
                   (SELECT count(*) FROM t)
            FROM {raw('call_center_interactions')} i LEFT JOIN t USING (interaction_id)""").fetchone()
        res["transcript_coverage"] = {"flagged_true": r[0], "flagged_true_with_transcript": r[1],
                                      "flagged_false_with_transcript": r[2], "distinct_transcribed": r[3]}

    if {"call_center_interactions", "satisfaction_surveys"} <= have:
        # Is a survey filed under its own date or under the date of the interaction it rates?
        r = con.execute(f"""
            WITH j AS (SELECT try_cast(s.process_date AS DATE) = try_cast(i.process_date AS DATE) AS same_process,
                              try_cast(i.interaction_date AS TIMESTAMP)::DATE AS asked,
                              try_cast(s.survey_date AS TIMESTAMP)::DATE AS answered
                       FROM {raw('satisfaction_surveys')} s JOIN {raw('call_center_interactions')} i USING (interaction_id))
            SELECT count(*), count_if(same_process), count_if(answered > asked), max(date_diff('day', asked, answered))
            FROM j""").fetchone()
        res["survey_dating"] = {"joined": r[0], "same_process_date": r[1], "survey_after_interaction_day": r[2],
                                "max_days_after": r[3]}

    if "transactions" in have:
        # The duplicate_charge flow needs same-card, same-merchant, same-amount pairs a few days apart.
        r = con.execute(f"""
            WITH t AS (SELECT product_id p, merchant_name m, {as_num('amount')} a, {as_ts('transaction_date')} ts
                       FROM {raw('transactions')} WHERE merchant_name IS NOT NULL)
            SELECT count_if(x.a = y.a), count(*) FROM t x JOIN t y ON x.p = y.p AND x.m = y.m
            AND y.ts > x.ts AND y.ts <= x.ts + INTERVAL 2 DAY""").fetchone()
        res["duplicate_charge_candidates"] = {"same_amount": r[0], "same_merchant_any_amount": r[1]}

    for name, phone, country in PHONES:
        if name not in have:
            continue
        rows = con.execute(f"""SELECT strip_accents(lower(trim({q(country)}))) AS c,
                                      regexp_extract({q(phone)}, '^[+][0-9]{{2}}') AS p, count(*)
                               FROM {raw(name)} WHERE {q(phone)} IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 3 DESC, 2""").fetchall()
        total = sum(r[2] for r in rows if r[0] in COUNTRY_PREFIX)
        bad = sum(r[2] for r in rows if r[0] in COUNTRY_PREFIX and r[1] != COUNTRY_PREFIX[r[0]])
        res["phones"].append({"table": name, "phone": phone, "country": country, "rows": total,
                              "mismatches": bad, "matrix": rows})

    for name, lat, lon in COORDS:
        if name not in have:
            continue
        r = con.execute(f"""SELECT count_if({as_num(lat)} IS NOT NULL AND {as_num(lon)} IS NOT NULL),
                count_if(abs({as_num(lat)}) < 1 AND abs({as_num(lon)}) < 1),
                count_if(NOT ({as_num(lat)} BETWEEN -56 AND 33 AND {as_num(lon)} BETWEEN -118 AND -34))
                FROM {raw(name)}""").fetchone()
        res["coords"].append({"table": name, "with_coords": r[0], "near_zero": r[1], "outside_latam_box": r[2]})

    for name, col in COUNTRY_COLUMNS:
        if name in have:
            res["countries"][f"{name}.{col}"] = con.execute(
                f"SELECT {q(col)}, count(*) FROM {raw(name)} GROUP BY 1 ORDER BY 2 DESC, 1 NULLS FIRST").fetchall()

    if "daily_exchange_rates" in have:
        res["fx"] = fx_checks(con, have)
    return res


def fx_checks(con, have: set[str]) -> dict:
    fx: dict = {}
    fx["pairs"] = con.execute(f"""
        SELECT source_currency, target_currency, count(*), count(DISTINCT "date"), min("date"), max("date"),
               count(*) - count(DISTINCT "date")
        FROM {raw('daily_exchange_rates')} GROUP BY 1, 2 ORDER BY 1, 2""").fetchall()
    days = (WINDOW[1] - WINDOW[0]).days + 1
    fx["window_days"] = days
    fx["jumps"] = con.execute(f"""
        WITH r AS (SELECT source_currency s, target_currency t, try_cast("date" AS DATE) d,
                          {as_num('exchange_rate')} x FROM {raw('daily_exchange_rates')}),
             j AS (SELECT s, t, x / lag(x) OVER (PARTITION BY s, t ORDER BY d) - 1 AS chg FROM r)
        SELECT s, t, count_if(abs(chg) > 0.2), max(abs(chg)) FROM j GROUP BY 1, 2 HAVING count_if(abs(chg) > 0.2) > 0
        ORDER BY 1, 2""").fetchall()
    if "transactions" not in have:
        return fx
    fx["transactions"] = con.execute(f"""
        WITH r AS (SELECT try_cast("date" AS DATE) d, source_currency s, any_value({as_num('exchange_rate')}) x
                   FROM {raw('daily_exchange_rates')} WHERE target_currency = 'USD' GROUP BY 1, 2),
             t AS (SELECT currency, {as_num('amount')} a, {as_num('amount_usd')} u, {as_ts('transaction_date')}::DATE d
                   FROM {raw('transactions')}),
             j AS (SELECT t.*, CASE WHEN currency = 'USD' THEN 1 ELSE r.x END AS rate
                   FROM t LEFT JOIN r ON r.s = t.currency AND r.d = t.d)
        SELECT currency, count(*), count(u), count(rate), count_if(u IS NOT NULL AND rate IS NOT NULL),
               count_if(u IS NOT NULL AND rate IS NOT NULL AND abs(a * rate - u) > greatest(0.01, 0.01 * abs(u))),
               median(abs(a * rate - u) / nullif(abs(u), 0)) FILTER (WHERE u IS NOT NULL AND rate IS NOT NULL),
               count_if(a < 0), count_if(a = 0),
               quantile_cont(u / nullif(a * rate, 0), 0.01), quantile_cont(u / nullif(a * rate, 0), 0.99)
        FROM j GROUP BY 1 ORDER BY 2 DESC, 1""").fetchall()
    if "customers" in have:
        fx["currency_by_country"] = con.execute(f"""
            SELECT c.country, t.currency, count(*) FROM {raw('transactions')} t
            JOIN (SELECT customer_id, any_value(country) country FROM {raw('customers')} GROUP BY 1) c USING (customer_id)
            GROUP BY 1, 2 ORDER BY 1, 3 DESC""").fetchall()
    return fx


# ---------- report ----------

def md_table(header: list[str], rows: list[list], align: str | None = None) -> list[str]:
    align = align or "|".join("---" for _ in header)
    lines = ["| " + " | ".join(header) + " |", "|" + align + "|"]
    lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return lines + [""]


def fmt_value(v) -> str:
    if v is None:
        return "*(null)*"
    s = str(v).replace("|", "\\|").replace("\n", " ")
    return f"`{s[:60]}`" if s.strip() == s else f"`{s[:60]!r}`"


def key_findings(p: dict[str, dict], x: dict) -> list[str]:
    out = []
    facts = [s for s in p.values() if "monthly" in s]

    # Row counts vs published figures.
    parts = [f"`{s['table']}` {pct(s['rows'], s['expected_rows'])}" for s in facts if s["expected_rows"]]
    if parts:
        out.append("**Row counts vs published figures (fact tables):** " + ", ".join(parts) +
                   ". See [Row-count deviations](#row-count-deviations) for the evidence per table.")

    # Duplicates.
    tot_rows = sum(s["rows"] for s in p.values())
    exact = sum(s["pk"]["exact_dup_rows"] for s in p.values())
    extra = sum(s["pk"]["dup_extra_rows"] for s in p.values())
    content = sum(s["pk"].get("content_dup_rows", 0) for s in p.values())
    conflicting = sum(s["pk"]["conflicting_groups"] for s in p.values())
    if extra or content:
        worst = sorted(p.values(), key=lambda s: -s["pk"]["dup_extra_rows"] / max(s["rows"], 1))[:3]
        out.append(f"**Duplicates:** {n(extra)} extra rows share a primary key with another row "
                   f"({pct(extra, tot_rows, 2)} of all rows); {n(exact)} are exact copies and {n(conflicting)} keys "
                   f"have copies that differ; {n(content)} rows repeat another row's content under a different key. "
                   "Highest: " + ", ".join(f"`{s['table']}` {pct(s['pk']['dup_extra_rows'], s['rows'], 2)}"
                                           for s in worst) + ".")
    else:
        out.append(f"**Duplicates: none** in {n(tot_rows)} rows: no repeated primary key, no exact copy and no "
                   "record repeated under a different key. The organizer's stated ~2% duplicates are not in this "
                   "copy of the data; the ETL still deduplicates (they may arrive with later deliveries).")

    # Nulls: sporadic (random ~5%) vs structural (optional fields).
    sporadic = [c for s in p.values() for c in s["columns"] if 0 < c["null_rate"] <= 0.15]
    structural = [c for s in p.values() for c in s["columns"] if c["null_rate"] > 0.15]
    if sporadic:
        avg = sum(c["null_rate"] for c in sporadic) / len(sporadic)
        out.append(f"**Nulls:** {len(sporadic)} columns have sporadic nulls (0–15%, mean {avg:.1%}), consistent with "
                   f"the organizer's ~5% injected nulls; {len(structural)} columns are mostly empty (>15%), which "
                   f"reads as optional or conditional fields (e.g. `resolution_date` of open complaints).")
    tokens = sum(c["null_tokens"] for s in p.values() for c in s["columns"])
    padded = sum(c["padded"] for s in p.values() for c in s["columns"])
    if tokens or padded:
        out.append(f"**Disguised nulls and padding:** {n(tokens)} values are null-like text "
                   f"({', '.join(NULL_TOKENS[:4])}…) and {n(padded)} values have leading or trailing spaces.")

    malformed = [(s["table"], c["column"], c["type"], c["malformed"]) for s in p.values() for c in s["columns"]
                 if c["malformed"]]
    if malformed:
        out.append(f"**Malformed values:** {len(malformed)} columns have values that do not parse as the column's "
                   "type: " + ", ".join(f"`{t}.{c}` ({n(k)})" for t, c, _, k in malformed[:8]) +
                   ("…" if len(malformed) > 8 else "") + ".")
    else:
        out.append("**Malformed values:** none: every typed column parses fully as its type.")

    rejected = sum(s["rejected_lines"] or 0 for s in p.values())
    out.append(f"**Unreadable CSV lines:** {n(rejected)}.")

    late = [(s["table"], s["timing"]["lag"]) for s in facts if s["timing"].get("lag")]
    if late:
        late_rows = sum(l["rows"] - l["same_day"] - l["negative"] for _, l in late)
        if late_rows:
            out.append("**Late arrivals (process_date after the event day):** " + ", ".join(
                f"`{t}` {pct(l['rows'] - l['same_day'] - l['negative'], l['rows'])} late (p95 {l['p95']:.0f} d, "
                f"max {l['max']} d)" for t, l in late) + ".")
        else:
            out.append("**Late arrivals: none.** No row has a `process_date` after its event day in "
                       f"{', '.join(f'`{t}`' for t, _ in late)}. The organizer's stated late arrivals are not in "
                       "this copy; the incremental load and its late-arrival test must still handle them.")
        # A day cut-off shows as lags of exactly -1 confined to the hours before the first same-day row.
        cutoff, other = [], []
        for s in facts:
            l, h = s["timing"].get("lag") or {}, s["timing"].get("negative_hours")
            if not l.get("negative"):
                continue
            # <=: the cut-off hour itself holds rows on both sides (the cut falls inside that hour).
            is_cutoff = l["min"] == -1 and h and h[2] is not None and h[1] <= h[2]
            (cutoff if is_cutoff else other).append((s["table"], l, h))
        if cutoff:
            out.append("**Processing-day cut-off:** events before a fixed hour are filed under the previous day's "
                       "`process_date` and partition: " + ", ".join(
                           f"`{t}` {pct(l['negative'], l['rows'])} of rows (day cut-off at {h[2]:02d}:00)"
                           for t, l, h in cutoff) +
                       ". The cut-off hour differs by table, so it is a batch rule, not one time zone. "
                       "This is not late or bad data, but the business date must come from the event timestamp, "
                       "never from `process_date` or the partition folder.")
        for t, l, h in other:
            see = " (see [Dating of surveys](#dating-of-surveys))" if t == "satisfaction_surveys" else ""
            out.append(f"**`{t}` dated before its own event:** {pct(l['negative'], l['rows'])} of rows have a "
                       f"`process_date` up to {-l['min']} day(s) before the event timestamp{see}.")

    drift = [(s["table"], d) for s in facts for d in s["monthly"]["drift"]]
    if drift:
        out.append("**Schema drift in content (monthly null rate varies well beyond sampling noise):** " + ", ".join(
            f"`{t}.{d['column']}` between {d['min_rate']:.0%} ({d['min_month']}) and {d['max_rate']:.0%} "
            f"({d['max_month']})" for t, d in drift[:10]) + ("…" if len(drift) > 10 else "") +
            ". A contract with a fixed null threshold would reject whole months of these columns.")
    else:
        out.append("**Schema drift in content:** no column's monthly null rate moves by 5 pp or more.")
    enum = [(s["table"], e) for s in facts for e in s.get("enum_drift", [])]
    if enum:
        out.append("**Categorical values that appear late or disappear early:** " + ", ".join(
            f"`{t}.{e['column']}` = {fmt_value(e['value'])} ({e['first']} → {e['last']})" for t, e in enum[:8]) + ".")

    orphans = [o for o in x.get("orphans", []) if o["orphans"]]
    if orphans:
        out.append("**Orphans (reference to a missing parent):** " + ", ".join(
            f"`{o['child']}.{o['column']}` {n(o['orphans'])} ({pct(o['orphans'], o['non_null'], 2)})"
            for o in orphans) + ".")
    else:
        out.append("**Orphans:** none; every foreign key resolves to its parent table.")
    incons = [c for c in x.get("consistency", []) if c["mismatches"]]
    if incons:
        out.append("**Cross-table inconsistencies:** " + ", ".join(
            f"{c['check']}: {n(c['mismatches'])} ({pct(c['mismatches'], c['joined'], 2)})" for c in incons) + ".")
    order = [d for d in x.get("date_order", []) if d["violations"]]
    if order:
        out.append("**Dates out of order:** " + ", ".join(
            f"`{d['table']}` {d['later']} < {d['earlier']}: {n(d['violations'])}" for d in order) + ".")

    multi = {k: v for k, v in _spellings(x).items() if len(v) > 1}
    if multi:
        out.append("**Country spellings:** " + "; ".join(" vs ".join(f"`{s}`" for s in sorted(v))
                                                         for v in multi.values()) + " across tables.")
    phones = [ph for ph in x.get("phones", []) if ph["mismatches"]]
    if phones:
        wrong = sorted({f"{r[0].title()} numbers use {r[1]}" for ph in phones for r in ph["matrix"]
                        if r[0] in COUNTRY_PREFIX and r[1] and r[1] != COUNTRY_PREFIX[r[0]]})
        out.append("**Phone prefix vs country:** " + ", ".join(
            f"`{ph['table']}.{ph['phone']}` {pct(ph['mismatches'], ph['rows'])}" for ph in phones) +
            " do not match the country's code (" + "; ".join(wrong) + "). Phones cannot be used to infer a country.")
    coords = [c for c in x.get("coords", []) if c["near_zero"] or c["outside_latam_box"]]
    if coords:
        out.append("**Coordinates:** " + ", ".join(
            f"`{c['table']}` {n(c['near_zero'])} near (0, 0) and {n(c['outside_latam_box'])} outside Latin America "
            f"(of {n(c['with_coords'])})" for c in coords) + ".")
    fx = x.get("fx", {})
    if fx.get("transactions"):
        rows = fx["transactions"]
        checked = sum(r[4] for r in rows)
        bad = sum(r[5] for r in rows)
        null_usd = sum(r[1] - r[2] for r in rows)
        band = [r for r in rows if r[9] is not None]
        usd = next((r for r in rows if r[0] == "USD"), None)
        out.append(f"**amount_usd (ADR 0002):** recomputed with the transaction-date rate for {n(checked)} rows; "
                   f"{n(bad)} ({pct(bad, checked, 2)}) differ by more than 1%" +
                   (": the shipped value is the exact conversion times noise between " +
                    ", ".join(f"{r[0]} {r[9]:.3f}–{r[10]:.3f}" for r in band) if band else "") +
                   f". {n(null_usd)} rows have no `amount_usd` ({pct(null_usd, sum(r[1] for r in rows))})" +
                   (f", including all {n(usd[1])} USD transactions" if usd and usd[2] == 0 else "") +
                   ". The ETL recomputes it from the rate table and keeps the shipped value only for comparison.")
        foreign = {v for v, _ in x.get("countries", {}).get("transactions.transaction_country", [])
                   if v in ("USA", "Spain", "Brazil", "Mexico")}
        if "Mexico" in foreign:
            out.append("**`transactions.transaction_country`:** `Mexico` (no accent) appears in the same small share "
                       "as `USA`, `Spain` and `Brazil` for customers of every country, so it marks international "
                       "transactions and is distinct from `México`; normalizing the spelling would erase that signal "
                       "unless an `is_international` flag is derived first.")

    dup = x.get("duplicate_charge_candidates")
    if dup is not None:
        out.append(f"**Duplicate-charge candidates:** {n(dup['same_amount'])} pairs of transactions on the same card "
                   f"at the same merchant with the same amount within 2 days ({n(dup['same_merchant_any_amount'])} with "
                   "any amount). The `duplicate_charge` dispute type has no organic examples in the data; its demo "
                   "and test cases need team-generated fixtures.")
    own = next((c for c in x.get("consistency", []) if c["child"] == "complaints" and "affected product" in c["check"]), None)
    if own and own["joined"] and own["mismatches"] == own["joined"]:
        out.append(f"**`complaints.affected_product_id` never belongs to the complaining customer** (0 of "
                   f"{n(own['joined'])}). Linking a complaint to its transaction through this column is impossible; "
                   "the match must search the complaining customer's own products by amount and date.")
    return out


def etl_implications(p: dict[str, dict], x: dict) -> list[str]:
    """Rules the raw -> silver pipeline takes from these findings (each one only when its evidence is present)."""
    rules = []
    facts = [s for s in p.values() if "monthly" in s]
    if any(s["timing"].get("lag", {}).get("negative") for s in facts):
        rules.append("**Business dates come from the event timestamp**, never from `process_date` or the partition "
                     "folder (processing-day cut-off, survey dating). `process_date` is only the load watermark.")
    rules.append("**Deduplicate by primary key, keeping the row with the latest `process_date`**, and check content "
                 "duplicates under a new key, even though this copy has none: the organizer announced both.")
    rules.append("**Load incrementally by partition/`process_date`** and re-run on every re-sync; a test fixture "
                 "delivers a record late (a newer version of an existing key) and must update it without duplicating.")
    fx = x.get("fx", {})
    if fx.get("transactions"):
        rules.append("**Recompute `amount_usd`** as `amount × rate(transaction date)` from `daily_exchange_rates` "
                     "(USD rows: the amount itself) and keep the shipped value as `amount_usd_source` for audit; "
                     "flag rows without a rate for that day (ADR 0002).")
    if any(len(v) > 1 for v in _spellings(x).values()):
        rules.append("**Normalize country names** (`Mexico` → `México`) in customer, branch, agent and campaign "
                     "columns; in `transactions.transaction_country` derive `is_international` first, since `Mexico` "
                     "there marks a foreign-country transaction.")
    broken = [o for o in x.get("orphans", []) if o["non_null"] and o["orphans"] / o["non_null"] > 0.5]
    if broken:
        rules.append("**Do not enforce** " + ", ".join(f"`{o['child']}.{o['column']}`" for o in broken) +
                     " as foreign keys (they almost never resolve): keep the value, add a `*_resolved` flag. "
                     "Quarantine only rows whose normally-valid keys fail (every other foreign key resolves today).")
    drift = [(s["table"], d["column"]) for s in facts for d in s["monthly"]["drift"]]
    rules.append("**Null contracts per column, from the observed rates** (not a global 5%): required columns have "
                 "0% nulls today and stay required" + (", and drifting columns (" + ", ".join(
                     f"`{t}.{c}`" for t, c in drift[:5]) + ") get a tolerant bound" if drift else "") + ".")
    own = next((c for c in x.get("consistency", []) if c["child"] == "complaints" and "affected product" in c["check"]), None)
    if own and own["joined"] and own["mismatches"] == own["joined"]:
        rules.append("**Keep `complaints.affected_product_id` out of joins**: it never points to the complainant's "
                     "product. Complaint ↔ transaction matching uses the customer's own cards.")
    if any(c["near_zero"] for c in x.get("coords", [])):
        rules.append("**Coordinates near (0, 0) become null** with a `coords_invalid` flag; phone prefixes are not "
                     "used to infer a country.")
    return ["## What this means for the ETL", "",
            "Rules the raw → silver pipeline (`etl/pipeline/`) takes from the findings above:", "",
            *[f"{i}. {r}" for i, r in enumerate(rules, 1)], ""]


def _spellings(x: dict) -> dict[str, set]:
    out: dict[str, set] = {}
    for rows in x.get("countries", {}).values():
        for v, _ in rows:
            if v:
                out.setdefault(v.strip().lower().replace("é", "e"), set()).add(v)
    return out


def render_report(p: dict[str, dict], x: dict) -> str:
    today = dt.date.today().isoformat()
    L = ["# Data Quality Report", "",
         f"Generated by `analysis/01_profile.py` on {today} from the local raw copy (`data/raw/`). "
         "Regenerate with `make profile`. Detail files (per-column stats, monthly volumes and null rates, lag "
         "histograms, value counts) are written to `analysis/out/profile/<table>/` (git-ignored).", "",
         "- Source: organizer-provided **synthetic** dataset; see [`data_inventory.md`](data_inventory.md) for files "
         "and partitions.",
         "- Method: every column is read as text, so malformed values are counted instead of failing the load. "
         f"A column's type is the first of {', '.join(TYPE_ORDER)} that at least {TYPE_SHARE:.0%} of its non-null "
         "values parse as; the rest are reported as malformed. Null-like text (`None`, `nan`, `NULL`, `N/A`…) "
         "counts as null.",
         "- Duplicates are counted on the raw rows; an *exact* duplicate repeats every column, a *key* duplicate "
         "repeats the primary key. Late arrival = `process_date` minus the event date, in days.",
         "- Personal columns (names, documents, contact data, card numbers, IPs, coordinates, free text) are "
         "measured but their values are never listed.", "",
         "## Summary", ""]
    rows = []
    for name in TABLES:
        if name not in p:
            continue
        s, k = p[name], p[name]["pk"]
        lag = s["timing"].get("lag")
        nully = sum(1 for c in s["columns"] if c["null_rate"] > 0)
        rows.append([f"`{name}`", n(s["rows"]), n(s["expected_rows"]), pct(s["rows"], s["expected_rows"]),
                     n(k["distinct_pk"]), n(k["exact_dup_rows"]), f"{n(k['dup_extra_rows'])} ({n(k['conflicting_groups'])})",
                     f"{nully}/{len(s['columns'])}", sum(1 for c in s["columns"] if c["malformed"]),
                     pct(lag["rows"] - lag["same_day"] - lag["negative"], lag["rows"]) if lag else "—"])
    L += md_table(["Table", "Rows", "Published", "Rows / published", "Distinct keys", "Exact dup rows",
                   "Key dup rows (keys that differ)", "Columns with nulls", "Malformed columns", "Late rows"],
                  rows, "---|---:|---:|---:|---:|---:|---:|---:|---:|---:")
    missing = [t for t in TABLES if t not in p]
    if missing:
        L += [f"Not profiled yet: {', '.join(f'`{t}`' for t in missing)}.", ""]

    L += ["## Key findings", "", *[f"{i}. {f}" for i, f in enumerate(key_findings(p, x), 1)], ""]

    L += ["## Row-count deviations", "",
          "Evidence for why the fact tables differ from the published row counts. If rows per day in the last "
          "months matched the rest of the history, the gap is not explained by records still to arrive late.", ""]
    rows = []
    for name, s in p.items():
        if "monthly" not in s:
            continue
        m = s["monthly"]
        rows.append([f"`{name}`", n(s["rows"]), n(s["pk"]["distinct_pk"]), n(s["expected_rows"]),
                     pct(s["pk"]["distinct_pk"], s["expected_rows"]), f"{m['first_month']} → {m['last_month']}",
                     f"{m['rows_per_day_min']:,.0f} / {m['rows_per_day_median']:,.0f} / {m['rows_per_day_max']:,.0f}",
                     f"{m['rows_per_day_first3']:,.0f}", f"{m['rows_per_day_last3']:,.0f}",
                     ", ".join(f"{y}: {c:,}" for y, c in m["yearly"])])
    L += md_table(["Table", "Rows", "Distinct keys", "Published", "Keys / published", "Months",
                   "Rows/day min / median / max", "Rows/day first 3 months", "Rows/day last 3 months", "Rows per year"],
                  rows, "---|---:|---:|---:|---:|---|---:|---:|---:|---")
    facts = [s for s in p.values() if "monthly" in s and s["expected_rows"]]
    short = [s for s in facts if s["rows"] < s["expected_rows"]]
    if short:
        flat = all(s["monthly"]["rows_per_day_last3"] >= 0.95 * s["monthly"]["rows_per_day_median"] for s in short)
        unique = all(s["pk"]["distinct_pk"] == s["rows"] for s in short)
        lo = min(s["rows"] / s["expected_rows"] for s in short)
        hi = max(s["rows"] / s["expected_rows"] for s in short)
        L += [f"Reading: the short tables hold {lo:.1%}–{hi:.1%} of the published counts. "
              + ("Rows per day are flat across the whole window, including the last three months, so the missing "
                 "rows are spread evenly over time rather than concentrated at the end: they are not recent records "
                 "still in transit. " if flat else
                 "The last three months are lighter than the median, consistent with records still to arrive. ")
              + ("Every key is unique, so the gap is not removed duplicates either. " if unique else "")
              + "The published figures read as nominal generation targets (a uniform ~12–16% shortfall, or a "
                "held-back share that may be delivered later as late arrivals); re-sync and re-run to tell them "
                "apart.", ""]
    over = [s for s in facts if s["rows"] > s["expected_rows"]]
    for s in over:
        L += [f"`{s['table']}` holds {pct(s['rows'], s['expected_rows'])} of its published count with "
              f"{n(s['pk']['distinct_pk'])} distinct keys and no duplicates, at a flat "
              f"~{s['monthly']['rows_per_day_median']:,.0f} rows per day: the table is simply larger than published.", ""]
    fx = x.get("fx")
    if fx:
        pairs = fx["pairs"]
        L += [f"`daily_exchange_rates`: {len(pairs)} currency pairs × {max(r[3] for r in pairs):,} "
              f"days = {sum(r[2] for r in pairs):,} rows (the window has {fx['window_days']:,} days). "
              "The published 3,000 does not match any pair count; the file holds one row per pair and day.", ""]

    L += ["## Cross-table checks", "", "### Orphans", ""]
    L += md_table(["Child column", "Parent", "Non-null", "Orphans", "Share", "Fixable by trim/upper", "Examples"],
                  [[f"`{o['child']}.{o['column']}`", f"`{o['parent']}.{o['key']}`", n(o["non_null"]), n(o["orphans"]),
                    pct(o["orphans"], o["non_null"], 2), n(o["fixable_by_normalizing"]),
                    ", ".join(f"`{e}`" for e in (o["examples"] or []))] for o in x.get("orphans", [])],
                  "---|---|---:|---:|---:|---:|---")
    L += ["### Consistency between related tables", ""]
    L += md_table(["Check", "Joined rows", "Mismatches", "Share"],
                  [[c["check"], n(c["joined"]), n(c["mismatches"]), pct(c["mismatches"], c["joined"], 2)]
                   for c in x.get("consistency", [])], "---|---:|---:|---:")
    L += ["### Date order", ""]
    L += md_table(["Table", "Rule", "Rows with both dates", "Violations", "Share"],
                  [[f"`{d['table']}`", f"`{d['earlier']}` ≤ `{d['later']}`", n(d["pairs"]), n(d["violations"]),
                    pct(d["violations"], d["pairs"], 2)] for d in x.get("date_order", [])], "---|---|---:|---:|---:")
    if "resolution_days" in x:
        r = x["resolution_days"]
        L += [f"`complaints.resolution_days` differs by more than one day from `resolution_date - creation_date` in "
              f"{n(r['mismatches'])} of {n(r['rows'])} resolved complaints ({pct(r['mismatches'], r['rows'])}).", ""]
    if "transcript_coverage" in x:
        c = x["transcript_coverage"]
        L += [f"Transcripts: {n(c['flagged_true'])} interactions have `has_transcript = True`; "
              f"{n(c['flagged_true_with_transcript'])} of them have a row in `call_transcripts` "
              f"({pct(c['flagged_true_with_transcript'], c['flagged_true'])}), and "
              f"{n(c['flagged_false_with_transcript'])} interactions flagged `False` do have one.", ""]
    if "survey_dating" in x:
        c = x["survey_dating"]
        L += ["### Dating of surveys", "",
              f"{pct(c['same_process_date'], c['joined'])} of surveys carry the `process_date` (and partition) of the "
              f"interaction they rate, while {pct(c['survey_after_interaction_day'], c['joined'])} were answered on a "
              f"later day (up to {c['max_days_after']} day(s) after). Surveys are filed by interaction, not by answer "
              "date: time-based analysis of surveys must use `survey_date`.", ""]
    if "duplicate_charge_candidates" in x:
        d = x["duplicate_charge_candidates"]
        L += ["### Duplicate-charge candidates", "",
              f"Same card, same merchant, within 2 days: {n(d['same_merchant_any_amount'])} pairs; with the same amount: "
              f"{n(d['same_amount'])}.", ""]

    L += ["### Countries, phone prefixes and coordinates", ""]
    for key, rows in x.get("countries", {}).items():
        L.append(f"- `{key}`: " + ", ".join(f"{fmt_value(v)} {c:,}" for v, c in rows[:12]))
    L.append("")
    for ph in x.get("phones", []):
        known = [r for r in ph["matrix"] if r[0] in COUNTRY_PREFIX]
        L.append(f"- `{ph['table']}.{ph['phone']}` by `{ph['country']}`: " + "; ".join(
            f"{r[0]} {r[1] or '(no prefix)'} {r[2]:,}" for r in known) +
            f" → {pct(ph['mismatches'], ph['rows'])} mismatched")
    for c in x.get("coords", []):
        L.append(f"- `{c['table']}` coordinates: {n(c['with_coords'])} rows, {n(c['near_zero'])} near (0, 0), "
                 f"{n(c['outside_latam_box'])} outside a Latin America bounding box")
    L.append("")

    if fx:
        L += ["### Exchange rates and amount_usd (ADR 0002)", ""]
        L += md_table(["Pair", "Rows", "Days", "From", "To", "Duplicate days"],
                      [[f"{r[0]}→{r[1]}", n(r[2]), n(r[3]), r[4], r[5], n(r[6])] for r in fx["pairs"]],
                      "---|---:|---:|---|---|---:")
        if fx["jumps"]:
            L += ["Day-over-day rate jumps above 20%: " + ", ".join(
                f"{r[0]}→{r[1]} {r[2]} (max {r[3]:.0%})" for r in fx["jumps"]) + ".", ""]
        if fx.get("transactions"):
            L += md_table(["Currency", "Transactions", "With amount_usd", "With a rate that day", "Checked",
                           "Differ > 1%", "Median relative error", "Shipped / exact (p1–p99)", "Negative amounts",
                           "Zero amounts"],
                          [[r[0], n(r[1]), n(r[2]), n(r[3]), n(r[4]), f"{n(r[5])} ({pct(r[5], r[4], 2)})",
                            "—" if r[6] is None else f"{r[6]:.4%}",
                            "—" if r[9] is None else f"{r[9]:.3f}–{r[10]:.3f}", n(r[7]), n(r[8])]
                           for r in fx["transactions"]],
                          "---|---:|---:|---:|---:|---:|---:|---:|---:|---:")
        if fx.get("currency_by_country"):
            L += ["Transaction currency by customer country: " + "; ".join(
                f"{r[0]} {r[1]} {r[2]:,}" for r in fx["currency_by_country"]) + ".", ""]

    L += etl_implications(p, x)
    L += ["## Tables", ""]
    for name in TABLES:
        if name in p:
            L += table_section(p[name])
    return "\n".join(L).rstrip() + "\n"


def table_section(s: dict) -> list[str]:
    k, tm = s["pk"], s["timing"]
    L = [f"### `{s['table']}`", "",
         f"{n(s['rows'])} rows in {n(s['files'])} file(s); primary key `{', '.join(s['pk_columns'])}`: "
         f"{n(k['distinct_pk'])} distinct, {n(k['null_pk'])} null."]
    if k["dup_groups"]:
        L.append(f"Key duplicates: {n(k['dup_groups'])} keys repeated (up to {k['max_copies']} copies, "
                 f"{n(k['dup_extra_rows'])} extra rows); {n(k['identical_groups'])} identical, "
                 f"{n(k['conflicting_groups'])} with differing values; {n(k['multi_file_groups'])} span more than one "
                 f"file" + (f" (median {k['dup_span_median_days']:.0f} d apart, max {k['dup_span_max_days']} d)"
                            if k["dup_span_max_days"] else "") + ".")
        if k["differing_columns"]:
            L.append("Columns that differ between copies: " + ", ".join(
                f"`{c}` ({n(v)})" for c, v in k["differing_columns"][:8]) + ".")
    else:
        L.append("No key duplicates.")
    if k.get("content_dup_rows"):
        L.append(f"{n(k['content_dup_rows'])} rows repeat another row's content (every column but the key and "
                 "`process_date`) under a different key.")
    if tm.get("event_min"):
        L.append(f"Event `{s['event']}` from {tm['event_min']} to {tm['event_max']}; {n(tm['outside_window'])} "
                 f"outside {WINDOW[0]} → {WINDOW[1]}.")
    if "partition_is_process_day" in tm and s["rows"]:
        part = f"Partition day = `process_date` for {pct(tm['partition_is_process_day'], s['rows'])} of rows"
        if "partition_is_event_day" in tm:
            part += f", = event day for {pct(tm['partition_is_event_day'], s['rows'])}"
        L.append(part + ".")
    if tm.get("lag"):
        g = tm["lag"]
        L.append(f"Lag `process_date - {s['event']}` (days): same day {pct(g['same_day'], g['rows'])}, 1 day "
                 f"{pct(g['one_day'], g['rows'])}, 2–7 days {pct(g['two_to_seven'], g['rows'])}, over 7 "
                 f"{pct(g['over_seven'], g['rows'])}, negative {pct(g['negative'], g['rows'])}; "
                 f"median {g['median']}, p95 {g['p95']:.0f}, min {g['min']}, max {g['max']}.")
        h = tm.get("negative_hours")
        if g["negative"] and h and h[0] is not None:
            L.append(f"Negative lags only have event hours {h[0]:02d}:00–{h[1]:02d}:59; same-day rows start at "
                     f"{h[2]:02d}:00.")
    m = s.get("monthly")
    if m and m["drift"]:
        L.append("Monthly null-rate drift: " + ", ".join(
            f"`{d['column']}` {d['min_rate']:.1%} ({d['min_month']}) → {d['max_rate']:.1%} ({d['max_month']}), "
            f"first 3 months {d['first3']:.1%} vs last 3 {d['last3']:.1%}" for d in m["drift"]) + ".")
    for e in s.get("enum_drift", []):
        L.append(f"Value {fmt_value(e['value'])} of `{e['column']}` only appears {e['first']} → {e['last']} "
                 f"({n(e['rows'])} rows).")
    L.append("")

    rows = []
    for c in s["columns"]:
        vals = s["values"].get(c["column"])
        top = ", ".join(f"{fmt_value(v)} {pct(cnt, s['rows'])}" for v, cnt, *_ in vals[:8]) if vals else ""
        if vals and len(vals) > 8:
            top += f" … ({len(vals)} values)"
        mal = s["malformed"].get(c["column"], {})
        bad = n(c["malformed"]) if c["malformed"] else ""
        if mal.get("examples"):
            bad += " e.g. " + ", ".join(fmt_value(v) for v, _ in mal["examples"][:3])
        if mal.get("months"):
            bad += f" ({mal['months'][0]} → {mal['months'][1]})"
        rows.append([f"`{c['column']}`", c["type"], pct(c["nulls"] + c["null_tokens"], c["rows"]),
                     n(c["distinct"]), bad, n(c["padded"]) if c["padded"] else "", top])
    approx = not all(c.get("distinct_exact", False) for c in s["columns"])
    L += md_table(["Column", "Type", "Null", "≈ Distinct" if approx else "Distinct", "Malformed", "Padded",
                   "Values (categorical)"],
                  rows, "---|---|---:|---:|---|---:|---")
    return L


# ---------- main ----------

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tables", nargs="*", choices=list(TABLES), help="Only (re)profile these tables.")
    parser.add_argument("--reload", action="store_true", help="Re-read the CSV files even if unchanged.")
    args = parser.parse_args()
    if not RAW_DIR.exists():
        raise SystemExit("data/raw/ not found: sync the dataset (make data) or link a local copy there.")

    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB_FILE))
    con.execute("SET preserve_insertion_order = false")
    con.execute(f"SET temp_directory = {lit((REPO_ROOT / 'data' / 'tmp').as_posix())}")

    started = time.time()
    for name in args.tables or list(TABLES):
        if load(con, name, TABLES[name], args.reload):
            profile(con, name, TABLES[name])

    have = loaded_tables(con)
    profiles = {}
    for name in TABLES:
        path = OUT_DIR / name / "summary.json"
        if name in have and path.exists():
            profiles[name] = json.loads(path.read_text(encoding="utf-8"))
    cross = cross_checks(con, have)
    (OUT_DIR / "cross_checks.json").write_text(json.dumps(cross, indent=1, default=str), encoding="utf-8")

    REPORT.write_text(render_report(profiles, cross), encoding="utf-8", newline="\n")
    log(f"wrote {REPORT.relative_to(REPO_ROOT)} ({len(profiles)} tables) in {time.time() - started:,.0f} s")


if __name__ == "__main__":
    main()
