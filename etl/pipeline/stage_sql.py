"""SQL stages generated from the TableSpec, all executed inside one DuckDB connection.

Stage order per table (docs/etl_rules.md):
  stg_raw    ingest: CSVs as text + _rid/_file/_part_date, strict header check (schema drift fails loudly)
  stg_clean  cast to dictionary types, trim, null tokens, canonical-English standardization;
             a NOT NULL column whose value does not parse -> quarantine (rule cast.<col>)
  stg_ext    derived columns and flags per table (joins to already-built silver dependencies)
  stg_kept   PK dedup (latest process_date wins; losers are superseded versions, only counted)
             + content duplicates under a different PK -> quarantine
  stg_final  business-key uniqueness policies (keep_first / null_all) with flag columns
  stg_out    final projection: renames, drops, event_date, source_file (what silver will contain)
"""

from __future__ import annotations

import duckdb

from .config import PipelineConfig
from .mappings import NULL_TOKENS, card_brand_sql, standardize_sql
from .specs import BizKey, TableSpec

DATASET_END = "DATE '2026-06-17'"
META = ("_rid", "_file", "_part_date")


def _txt(col: str) -> str:
    tokens = ", ".join(f"'{t}'" for t in NULL_TOKENS)
    return f"(CASE WHEN trim({col}) = '' OR lower(trim({col})) IN ({tokens}) THEN NULL ELSE trim({col}) END)"


def ingest(con: duckdb.DuckDBPyConnection, cfg: PipelineConfig, table: str, spec: TableSpec,
           months: list[str] | None) -> None:
    """stg_raw: raw text rows in scope. months limits partitioned tables to the files that can
    contain those event months (the 06:00/08:00 cutoff files events of a day under the previous
    process_date, so the day before each month is included)."""
    if spec.partitioned_raw:
        glob = (cfg.raw_dir / table / "**" / "*.csv").as_posix()
        where = ""
        if months is not None:
            # A partition file dated the last day of month M-1 can hold events of M (day cutoff),
            # so each month's file range starts one day early.
            ranges = " OR ".join(
                f"make_date(year::INT, month::INT, day::INT) "
                f"BETWEEN (DATE '{m}-01' - INTERVAL 1 DAY) "
                f"AND (DATE '{m}-01' + INTERVAL 1 MONTH - INTERVAL 1 DAY)"
                for m in months
            )
            where = f"WHERE {ranges}"
        src = (f"SELECT * EXCLUDE (filename, year, month, day), parse_filename(filename) AS _file, "
               f"make_date(year::INT, month::INT, day::INT) AS _part_date "
               f"FROM read_csv('{glob}', header = true, all_varchar = true, union_by_name = true, "
               f"hive_partitioning = true, filename = true) {where}")
    else:
        path = (cfg.raw_dir / f"{table}.csv").as_posix()
        src = (f"SELECT * EXCLUDE (filename), parse_filename(filename) AS _file, NULL::DATE AS _part_date "
               f"FROM read_csv('{path}', header = true, all_varchar = true, filename = true)")
    con.execute(f"CREATE OR REPLACE TEMP TABLE stg_raw AS "
                f"SELECT row_number() OVER () AS _rid, * FROM ({src})")

    got = {r[0] for r in con.execute("DESCRIBE stg_raw").fetchall()} - set(META)
    expected = set(spec.types)
    if got != expected:  # strict input schema: any drift stops the load with a clear message
        missing, extra = sorted(expected - got), sorted(got - expected)
        raise SystemExit(f"{table}: raw schema drift — missing columns {missing}, unexpected {extra}")


def clean(con: duckdb.DuckDBPyConnection, table: str, spec: TableSpec) -> dict[str, int]:
    """stg_clean + cast-error quarantine; returns findings for values nulled by a failed cast."""
    exprs, findings = [], {}
    for col, typ in spec.types.items():
        base = _txt(col)
        if col in spec.standardize:
            base = standardize_sql(base, spec.standardize[col])
        exprs.append(base if typ == "VARCHAR" else f"try_cast({base} AS {typ})")
    cols = ", ".join(f"{e} AS {c}" for e, c in zip(exprs, spec.types))
    con.execute(f"CREATE OR REPLACE TEMP TABLE stg_clean AS SELECT _rid, _file, _part_date, {cols} FROM stg_raw")

    con.execute("CREATE OR REPLACE TEMP TABLE _quarantine "
                "(_rid BIGINT, rule_id VARCHAR, reason VARCHAR, stage VARCHAR)")
    for col, typ in spec.types.items():
        if typ == "VARCHAR":
            continue
        bad = f"{_txt(col)} IS NOT NULL AND try_cast({_txt(col)} AS {typ}) IS NULL"
        if col in spec.not_null:
            con.execute(f"INSERT INTO _quarantine SELECT _rid, 'cast.{col}', "
                        f"'value does not parse as {typ}', 'cast' FROM stg_raw WHERE {bad}")
        else:
            n = con.execute(f"SELECT count(*) FROM stg_raw WHERE {bad}").fetchone()[0]
            if n:
                findings[f"cast.{col}.nulled"] = n
    return findings


def dedup(con: duckdb.DuckDBPyConnection, table: str, spec: TableSpec) -> int:
    """stg_kept: one row per PK (and content duplicates quarantined); returns PK-superseded count."""
    pk = ", ".join(spec.pk)
    order = ([f"{spec.dedup_order} DESC NULLS LAST"] if spec.dedup_order else []) + ["_file DESC", "_rid DESC"]
    con.execute(f"""CREATE OR REPLACE TEMP TABLE stg_dedup AS
        SELECT * EXCLUDE (_rn) FROM (
            SELECT *, row_number() OVER (PARTITION BY {pk} ORDER BY {', '.join(order)}) AS _rn
            FROM stg_ext WHERE _rid NOT IN (SELECT _rid FROM _quarantine)
        ) WHERE _rn = 1""")
    superseded = con.execute(
        "SELECT (SELECT count(*) FROM stg_ext WHERE _rid NOT IN (SELECT _rid FROM _quarantine))"
        " - (SELECT count(*) FROM stg_dedup)").fetchone()[0]

    if spec.content_dup_check:
        content_cols = [c for c in spec.types if c not in spec.pk and c != "process_date"]
        h = "hash(" + ", ".join(content_cols) + ")"
        con.execute(f"""CREATE OR REPLACE TEMP TABLE stg_kept AS
            SELECT * EXCLUDE (_h, _n, _rk) FROM (
                SELECT *, {h} AS _h, count(*) OVER (PARTITION BY {h}) AS _n,
                       row_number() OVER (PARTITION BY {h} ORDER BY {pk}) AS _rk
                FROM stg_dedup
            ) k WHERE _n = 1 OR _rk = 1""")
        con.execute(f"""INSERT INTO _quarantine
            SELECT _rid, 'dedup.content_duplicate',
                   'same content as another row under a different {spec.pk[0]}', 'dedup'
            FROM (SELECT _rid, count(*) OVER (PARTITION BY {h}) AS _n,
                         row_number() OVER (PARTITION BY {h} ORDER BY {pk}) AS _rk FROM stg_dedup)
            WHERE _n > 1 AND _rk > 1""")
    else:
        con.execute("CREATE OR REPLACE TEMP TABLE stg_kept AS SELECT * FROM stg_dedup")
    return superseded


def apply_business_keys(con: duckdb.DuckDBPyConnection, spec: TableSpec) -> None:
    """stg_final: uniqueness policies over business keys, one pass per key (rules B2-B7)."""
    src = "stg_kept"
    for i, bk in enumerate(spec.business_keys):
        grp = bk.group_expr().format(c=bk.column) if "{c}" in bk.group_expr() else bk.group_expr()
        order = f"{bk.order_by} ASC NULLS LAST, " if bk.order_by else ""
        losers = "TRUE" if bk.policy == "null_all" else "_bk_rk > 1"
        con.execute(f"""CREATE OR REPLACE TEMP TABLE stg_bk{i} AS
            SELECT * EXCLUDE (_bk_grp, _bk_n, _bk_rk)
                 REPLACE (CASE WHEN _bk_grp IS NOT NULL AND _bk_n > 1 AND {losers}
                               THEN NULL ELSE {bk.column} END AS {bk.column}),
                   coalesce(_bk_grp IS NOT NULL AND _bk_n > 1 AND {losers}, FALSE) AS {bk.flag}
            FROM (
                SELECT *, {grp} AS _bk_grp,
                       CASE WHEN {grp} IS NULL THEN 1
                            ELSE count(*) OVER (PARTITION BY {grp}) END AS _bk_n,
                       row_number() OVER (PARTITION BY {grp}
                                          ORDER BY {order}{', '.join(spec.pk)}) AS _bk_rk
                FROM {src}
            )""")
        src = f"stg_bk{i}"
    con.execute(f"CREATE OR REPLACE TEMP TABLE stg_final AS SELECT * FROM {src}")


def project_out(con: duckdb.DuckDBPyConnection, spec: TableSpec, months: list[str] | None) -> None:
    """stg_out: silver columns (drops, renames, event_date, source_file) plus _rid for quarantine.

    With a month scope, neighbor-month rows staged only for dedup context are filtered out here,
    so a partition swap never writes a partial adjacent month.
    """
    described = [r[0] for r in con.execute("DESCRIBE stg_final").fetchall()]
    derived = [c for c in described if c not in spec.types and c not in META]
    cols = [f"{c} AS {spec.rename[c]}" if c in spec.rename else c
            for c in spec.types if c not in spec.drop]
    cols += derived
    if spec.event and "event_date" not in derived:
        cols.append(f"CAST({spec.event} AS DATE) AS event_date")
    cols.append("_file AS source_file")
    where = ""
    if months is not None and spec.event:
        inlist = ", ".join(f"'{m}'" for m in months)
        where = f" WHERE strftime(CAST({spec.event} AS DATE), '%Y-%m') IN ({inlist})"
    con.execute(f"CREATE OR REPLACE TEMP TABLE stg_out AS "
                f"SELECT _rid, {', '.join(cols)} FROM stg_final{where}")


# ---------- per-table derived columns and flags (stg_clean -> stg_ext) ----------

_COORDS_BAD = "(SELECT *, coalesce(abs(latitude) < 1 AND abs(longitude) < 1, FALSE) AS _coords_bad FROM stg_clean)"
_COORDS_REPLACE = ("CASE WHEN c._coords_bad THEN NULL ELSE c.latitude END AS latitude, "
                   "CASE WHEN c._coords_bad THEN NULL ELSE c.longitude END AS longitude")


def build_ext(con: duckdb.DuckDBPyConnection, table: str) -> None:
    sql = {
        "branches": f"""
            SELECT c.* EXCLUDE (_coords_bad) REPLACE ({_COORDS_REPLACE}),
                   c._coords_bad AS coords_invalid
            FROM {_COORDS_BAD} c""",
        "service_agents": """
            SELECT c.* REPLACE (CASE WHEN b.branch_id IS NULL THEN NULL
                                     ELSE c.assigned_branch_id END AS assigned_branch_id),
                   (c.assigned_branch_id IS NOT NULL AND b.branch_id IS NULL) AS branch_unresolved
            FROM stg_clean c LEFT JOIN silver_branches b ON c.assigned_branch_id = b.branch_id""",
        "customers": """
            SELECT c.* REPLACE (
                    CASE WHEN b.branch_id IS NULL THEN NULL ELSE c.registration_branch_id END
                        AS registration_branch_id,
                    CASE WHEN ap.ph IS NOT NULL THEN NULL ELSE c.mobile_phone END AS mobile_phone),
                (c.registration_branch_id IS NOT NULL AND b.branch_id IS NULL) AS branch_unresolved,
                (ap.ph IS NOT NULL) AS phone_matches_agent
            FROM stg_clean c
            LEFT JOIN silver_branches b ON c.registration_branch_id = b.branch_id
            LEFT JOIN (SELECT DISTINCT regexp_replace(phone, '[^0-9]', '', 'g') AS ph
                       FROM silver_service_agents WHERE phone IS NOT NULL) ap
              ON regexp_replace(c.mobile_phone, '[^0-9]', '', 'g') = ap.ph""",
        "products": f"""
            SELECT c.*,
                CASE WHEN c.product_type IN ('Credit Card', 'Debit Card')
                     THEN right(regexp_replace(c.product_number, '[^0-9]', '', 'g'), 4) END AS card_last4,
                CASE WHEN c.product_type IN ('Credit Card', 'Debit Card')
                     THEN {card_brand_sql('c.product_number')} END AS card_brand,
                coalesce(c.product_type IN ('Credit Card', 'Debit Card')
                         AND c.expiration_date < {DATASET_END}
                         AND c.product_status = 'Active', FALSE) AS expired_active_card,
                coalesce(c.opening_date < CAST(cu.registration_date AS DATE), FALSE)
                    AS opened_before_registration
            FROM stg_clean c LEFT JOIN silver_customers cu USING (customer_id)""",
        "transactions": f"""
            SELECT c.* EXCLUDE (_coords_bad) REPLACE ({_COORDS_REPLACE},
                    -- recomputed at the transaction-date rate (ADR 0002); shipped value kept below
                    CASE WHEN c.currency = 'USD' THEN round(c.amount, 2)
                         ELSE round(c.amount * fx.exchange_rate, 2) END AS amount_usd),
                c._coords_bad AS coords_invalid,
                c.amount_usd AS amount_usd_source,
                coalesce(c.currency <> 'USD' AND fx.exchange_rate IS NULL, FALSE) AS fx_rate_missing,
                -- raw pre-standardization value: unaccented 'Mexico' marks international purchases
                coalesce(trim(r.transaction_country) IN ('USA', 'Spain', 'Brazil', 'Mexico'), FALSE)
                    AS is_international,
                coalesce(CAST(c.transaction_date AS DATE) < p.opening_date, FALSE) AS predates_product
            FROM {_COORDS_BAD} c
            JOIN stg_raw r ON r._rid = c._rid
            LEFT JOIN silver_products p ON p.product_id = c.product_id
            LEFT JOIN (SELECT rate_date, source_currency, any_value(exchange_rate) AS exchange_rate
                       FROM silver_daily_exchange_rates WHERE target_currency = 'USD'
                       GROUP BY 1, 2) fx
              ON fx.source_currency = c.currency
             AND fx.rate_date = CAST(c.transaction_date AS DATE)""",
        "call_center_interactions": """
            SELECT *, coalesce(was_escalated AND was_resolved, FALSE) AS escalated_and_resolved
            FROM stg_clean""",
        "satisfaction_surveys": """
            SELECT * REPLACE (
                CASE WHEN survey_type = 'NPS' THEN coalesce(nps_category,
                        CASE WHEN main_score <= 6 THEN 'Detractor'
                             WHEN main_score <= 8 THEN 'Passive' ELSE 'Promoter' END)
                     ELSE NULL END AS nps_category)
            FROM stg_clean""",
        "complaints": """
            SELECT * REPLACE (
                    CASE WHEN claimed_amount IS NULL THEN NULL ELSE currency END AS currency),
                coalesce(claimed_amount IS NULL AND currency IS NOT NULL, FALSE)
                    AS currency_removed_no_amount,
                coalesce(claimed_amount IS NOT NULL AND currency IS NULL, FALSE)
                    AS amount_without_currency,
                coalesce(status IN ('Resolved', 'Closed') AND resolution_date IS NULL, FALSE)
                    AS resolved_without_date,
                coalesce(status = 'Closed' AND closing_date IS NULL, FALSE)
                    AS closed_without_closing_date,
                coalesce(resolution_date < first_response_date, FALSE) AS resolved_before_first_response
            FROM stg_clean""",
        "digital_events": """
            SELECT *, coalesce((event_type = 'Logout' AND action = 'login')
                            OR (event_type = 'Login' AND action = 'logout'), FALSE)
                          AS action_event_mismatch
            FROM stg_clean""",
    }.get(table, "SELECT * FROM stg_clean")
    con.execute(f"CREATE OR REPLACE TEMP TABLE stg_ext AS {sql}")


# Normalized lookup dimensions (3NF): built from the source table's staged rows before columns drop.
DIMS: dict[str, tuple[str, str]] = {
    "dim_cities": ("branches", "SELECT DISTINCT city, state, country FROM stg_final ORDER BY country, state, city"),
    "dim_merchants": ("transactions",
                      "SELECT merchant_name, any_value(merchant_category) AS merchant_category "
                      "FROM stg_final WHERE merchant_name IS NOT NULL GROUP BY 1 ORDER BY 1"),
    "dim_categories": ("complaints",
                       "SELECT category, any_value(subcategory) AS subcategory "
                       "FROM stg_final WHERE subcategory IS NOT NULL GROUP BY 1 ORDER BY 1"),
}
