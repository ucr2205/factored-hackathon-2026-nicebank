"""Business EDA for Gate 1: is card-dispute intake a relevant, painful and data-backed flow?

Answers the three Gate 1 questions with the organizer dataset and writes docs/eda_findings.md:
  1. Volume: how many complaints and contacts are about disputed charges, by country, segment, channel and month.
  2. Pain: how those cases are handled today (resolution time, SLA breaches, open backlog, escalation, first
     contact resolution, CSAT) compared with the other categories.
  3. Data: what the system can actually learn from and look up: the complaint <-> transaction matching experiment
     (with a shuffled-customer control), natural-language data, card transactions and fraud labels.
It also writes the draft category -> flow mapping analysis/mappings/contact_reason_to_flow.csv (taxonomy C6).

Outcome columns (was_resolved, was_escalated, sla_breached, resolution, compensation_granted, is_fraud) are used
here only to describe today's service; they are evaluation labels and never system or model inputs.

Reads the DuckDB copy built by analysis/01_profile.py (run `make profile` first).
Usage: python analysis/02_business.py
"""

from __future__ import annotations

import csv
import datetime as dt
import time
from pathlib import Path

import duckdb

REPO_ROOT = Path(__file__).resolve().parents[1]
DB_FILE = REPO_ROOT / "data" / "profile.duckdb"
OUT_DIR = REPO_ROOT / "analysis" / "out" / "business"
REPORT = REPO_ROOT / "docs" / "eda_findings.md"
MAPPING = REPO_ROOT / "analysis" / "mappings" / "contact_reason_to_flow.csv"

MATCH_WINDOW_DAYS = 60   # a complaint can refer to a charge up to this many days before it was filed
AMOUNT_TOLERANCES = (0.01, 0.05)
SEED = 42                # shuffled-customer control

# Complaint categories that are card-charge disputes (subcategory in parentheses) and their C6 dispute type.
DISPUTE_CATEGORIES = {"Transactions": "unrecognized_charge", "Fees": "other_in_scope"}

# Draft mapping for taxonomy C6, to agree with P3 and P4. flow: dispute_intake | out_of_scope | mixed.
FLOW_MAPPING = [
    ("complaints.category", "Transactions", "Cargo no reconocido", "dispute_intake", "unrecognized_charge",
     "Customer does not recognize a charge: the core dispute flow."),
    ("complaints.category", "Fees", "Cobro indebido", "dispute_intake", "other_in_scope",
     "Charge the customer considers undue (fees); in scope, type to confirm (wrong_amount vs other_in_scope)."),
    ("complaints.category", "Technical", "Problema con app", "out_of_scope", "out_of_scope", "App problems."),
    ("complaints.category", "Service", "Calidad de servicio", "out_of_scope", "out_of_scope", "Service quality."),
    ("complaints.category", "Branch", "Atención en sucursal", "out_of_scope", "out_of_scope", "Branch service."),
    ("call_center_interactions.contact_reason", "Queja", "", "mixed", "",
     "Complaint contacts; the dataset does not say which ones are about charges."),
    ("call_center_interactions.contact_reason", "Transaccional", "", "mixed", "",
     "Transactional contacts (movements, payments); may include charge questions, not distinguishable."),
    ("call_center_interactions.contact_reason", "Producto", "", "out_of_scope", "out_of_scope", "Product questions."),
    ("call_center_interactions.contact_reason", "Técnico", "", "out_of_scope", "out_of_scope", "Technical support."),
    ("call_center_interactions.contact_reason", "Comercial", "", "out_of_scope", "out_of_scope", "Sales."),
    ("call_center_interactions.contact_reason", "Retención", "", "out_of_scope", "out_of_scope", "Retention."),
]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def pct(part, whole, digits: int = 1) -> str:
    return "—" if not whole or part is None else f"{100 * part / whole:.{digits}f}%"


def n(value) -> str:
    return "—" if value is None else f"{value:,}"


def f1(value, suffix: str = "") -> str:
    return "—" if value is None else f"{value:,.1f}{suffix}"


def md_table(header: list[str], rows: list[list], align: str) -> list[str]:
    return ["| " + " | ".join(header) + " |", "|" + align + "|",
            *["| " + " | ".join(str(c) for c in r) + " |" for r in rows], ""]


def write_csv(path: Path, header: list[str], rows: list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def views(con: duckdb.DuckDBPyConnection) -> None:
    """Typed views over the raw text tables; business dates come from event timestamps (see the quality report)."""
    con.execute("""CREATE OR REPLACE TEMP VIEW customers AS
        SELECT customer_id, country, segment FROM raw_customers""")
    con.execute("""CREATE OR REPLACE TEMP VIEW complaints AS
        SELECT c.complaint_id, c.customer_id, cu.country, cu.segment, c.case_type, c.category, c.subcategory,
               c.reception_channel AS channel, try_cast(c.creation_date AS TIMESTAMP) AS created,
               try_cast(c.first_response_date AS TIMESTAMP) AS first_response,
               try_cast(c.resolution_days AS DOUBLE) AS resolution_days, c.status, c.priority,
               lower(c.sla_breached) = 'true' AS sla_breached,
               try_cast(c.compensation_granted AS DOUBLE) AS compensation,
               try_cast(c.resolution_satisfaction AS DOUBLE) AS satisfaction,
               lower(c.is_repeat_complainer) = 'true' AS repeat_complainer,
               try_cast(c.claimed_amount AS DOUBLE) AS claimed_amount, c.currency
        FROM raw_complaints c LEFT JOIN customers cu USING (customer_id)""")
    con.execute("""CREATE OR REPLACE TEMP VIEW contacts AS
        SELECT i.interaction_id, i.customer_id, cu.country, cu.segment, i.channel, i.interaction_type,
               i.contact_reason, try_cast(i.interaction_date AS TIMESTAMP) AS ts,
               try_cast(i.duration_seconds AS DOUBLE) AS duration_s, try_cast(i.wait_time_seconds AS DOUBLE) AS wait_s,
               lower(i.was_resolved) = 'true' AS resolved, lower(i.was_escalated) = 'true' AS escalated,
               lower(i.requires_followup) = 'true' AS followup, try_cast(i.sentiment_score AS DOUBLE) AS sentiment
        FROM raw_call_center_interactions i LEFT JOIN customers cu USING (customer_id)""")
    con.execute("""CREATE OR REPLACE TEMP VIEW txns AS
        SELECT t.transaction_id, t.customer_id, t.product_id, p.product_type,
               try_cast(t.transaction_date AS TIMESTAMP) AS ts, t.transaction_type, t.currency,
               try_cast(t.amount AS DOUBLE) AS amount, t.transaction_status, lower(t.is_fraud) = 'true' AS is_fraud
        FROM raw_transactions t LEFT JOIN raw_products p USING (product_id)""")


def dispute_case() -> str:
    cats = ", ".join(f"'{c}'" for c in DISPUTE_CATEGORIES)
    return f"(category IN ({cats}))"


# ---------- 1. volume ----------

def volume(con) -> dict:
    res = {}
    res["complaints_total"] = con.execute("SELECT count(*) FROM complaints").fetchone()[0]
    res["by_category"] = con.execute("""
        SELECT category, coalesce(any_value(subcategory) FILTER (WHERE subcategory IS NOT NULL), '') AS sub, count(*)
        FROM complaints GROUP BY 1 ORDER BY 3 DESC""").fetchall()
    res["by_case_type"] = con.execute(f"""
        SELECT case_type, count(*), count_if({dispute_case()}) FROM complaints GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    res["contacts_total"] = con.execute("SELECT count(*) FROM contacts").fetchone()[0]
    res["contacts_by_reason"] = con.execute(
        "SELECT contact_reason, count(*) FROM contacts GROUP BY 1 ORDER BY 2 DESC").fetchall()
    cuts = {}
    for col in ("country", "segment", "channel"):
        cuts[col] = con.execute(f"""
            SELECT coalesce({col}, '(unknown)'), count(*), count_if({dispute_case()}),
                   count_if({dispute_case()}) / count(*) FROM complaints GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    res["cuts"] = cuts
    res["by_year"] = con.execute(f"""
        SELECT year(created), count(*), count_if({dispute_case()}) FROM complaints GROUP BY 1 ORDER BY 1""").fetchall()
    monthly = con.execute(f"""
        SELECT strftime(date_trunc('month', created), '%Y-%m') m, count(*), count_if({dispute_case()}),
               count_if(category = 'Transactions') FROM complaints GROUP BY 1 ORDER BY 1""").fetchall()
    write_csv(OUT_DIR / "complaints_monthly.csv", ["month", "complaints", "dispute_complaints", "unrecognized_charge"],
              monthly)
    full = monthly[1:-1]  # first and last months are partial
    shares = [r[2] / r[1] for r in full]
    res["monthly_share_range"] = (min(shares), max(shares))
    res["monthly_dispute_range"] = (min(r[2] for r in full), max(r[2] for r in full))
    res["customers_with_dispute"] = con.execute(
        f"SELECT count(DISTINCT customer_id) FROM complaints WHERE {dispute_case()}").fetchone()[0]
    res["customers_total"] = con.execute("SELECT count(*) FROM customers").fetchone()[0]
    return res


# ---------- 2. pain ----------

def pain(con) -> dict:
    res = {}
    res["complaints"] = con.execute(f"""
        SELECT CASE WHEN {dispute_case()} THEN category ELSE 'Other categories' END AS grp, count(*),
               median(resolution_days), avg(resolution_days), avg(sla_breached::INT),
               avg((status IN ('Open', 'In Process', 'Escalated'))::INT), avg((status = 'Escalated')::INT),
               median(date_diff('minute', created, first_response) / 60.0), avg(satisfaction),
               avg((compensation > 0)::INT) FILTER (WHERE status IN ('Resolved', 'Closed')),
               avg(repeat_complainer::INT), median(compensation) FILTER (WHERE compensation > 0)
        FROM complaints GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    res["contacts"] = con.execute("""
        SELECT contact_reason, count(*), avg(resolved::INT), avg(escalated::INT), avg(followup::INT),
               median(duration_s) / 60, median(wait_s) / 60, avg(sentiment)
        FROM contacts GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    res["csat"] = con.execute("""
        SELECT c.contact_reason, s.survey_type, count(*), avg(try_cast(s.main_score AS DOUBLE))
        FROM raw_satisfaction_surveys s JOIN contacts c USING (interaction_id)
        GROUP BY 1, 2 ORDER BY 2, 1""").fetchall()
    res["dispute_by_country"] = con.execute(f"""
        SELECT country, count(*), median(resolution_days), avg(sla_breached::INT),
               avg((status IN ('Open', 'In Process', 'Escalated'))::INT)
        FROM complaints WHERE {dispute_case()} GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    res["dispute_by_channel"] = con.execute(f"""
        SELECT channel, count(*), median(resolution_days), avg(sla_breached::INT)
        FROM complaints WHERE {dispute_case()} GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    return res


# ---------- 3. data: matching experiment ----------

def matching(con) -> dict:
    """For each dispute complaint with an amount, count the complainant's transactions that could be the one."""
    con.execute(f"""CREATE OR REPLACE TEMP TABLE claims AS
        SELECT complaint_id, customer_id, category, created, claimed_amount, currency
        FROM complaints WHERE {dispute_case()} AND claimed_amount IS NOT NULL""")
    # Control: the same claims assigned to a random other complainant. A real link should match far more often
    # for the true customer than for a random one; equal rates mean the amounts carry no information.
    con.execute(f"""CREATE OR REPLACE TEMP TABLE claims_control AS
        WITH ids AS (SELECT customer_id, row_number() OVER (ORDER BY hash(customer_id || '{SEED}')) AS k
                     FROM (SELECT DISTINCT customer_id FROM claims)),
             m AS (SELECT count(*) AS total FROM ids)
        SELECT c.complaint_id, s.customer_id, c.category, c.created, c.claimed_amount, c.currency
        FROM claims c JOIN ids o ON o.customer_id = c.customer_id CROSS JOIN m
        JOIN ids s ON s.k = (o.k % m.total) + 1""")
    # The control reuses the same customers, so their transactions are all the search needs.
    con.execute("""CREATE OR REPLACE TEMP TABLE claim_txns AS
        SELECT transaction_id, customer_id, ts, amount, currency FROM txns
        WHERE customer_id IN (SELECT customer_id FROM claims)""")
    res = {"claims": con.execute("SELECT count(*) FROM claims").fetchone()[0],
           "dispute_complaints": con.execute(f"SELECT count(*) FROM complaints WHERE {dispute_case()}").fetchone()[0],
           "currency": con.execute("SELECT coalesce(currency, '(none)'), count(*) FROM claims GROUP BY 1 ORDER BY 2 DESC").fetchall(),
           "claim_amounts": con.execute("""SELECT min(claimed_amount), median(claimed_amount), max(claimed_amount)
                                          FROM claims""").fetchone(),
           "txn_amounts": con.execute("""SELECT currency, median(amount) FROM txns GROUP BY 1 ORDER BY 1""").fetchall(),
           "variants": []}
    for tol in AMOUNT_TOLERANCES:
        for same_currency in (True, False):
            row = {"tolerance": tol, "same_currency": same_currency}
            for label, table in (("true", "claims"), ("control", "claims_control")):
                cur = "AND t.currency = c.currency" if same_currency else ""
                r = con.execute(f"""
                    WITH hits AS (
                        SELECT c.complaint_id, count(t.transaction_id) AS k
                        FROM {table} c LEFT JOIN claim_txns t ON t.customer_id = c.customer_id
                         AND t.ts BETWEEN c.created - INTERVAL {MATCH_WINDOW_DAYS} DAY AND c.created
                         AND abs(t.amount - c.claimed_amount) <= {tol} * c.claimed_amount {cur}
                        GROUP BY 1)
                    SELECT count(*), count_if(k = 0), count_if(k = 1), count_if(k > 1) FROM hits""").fetchone()
                row[label] = r
            res["variants"].append(row)
    res["window_activity"] = con.execute(f"""
        SELECT count(*), count_if(k > 0), median(k) FROM (
            SELECT c.complaint_id, count(t.transaction_id) AS k FROM claims c LEFT JOIN claim_txns t
            ON t.customer_id = c.customer_id AND t.ts BETWEEN c.created - INTERVAL {MATCH_WINDOW_DAYS} DAY AND c.created
            GROUP BY 1)""").fetchone()
    return res


def data_assets(con) -> dict:
    res = {}
    res["cards"] = con.execute("""SELECT product_type, count(*) FROM raw_products WHERE product_type LIKE 'Tarjeta%'
                                  GROUP BY 1 ORDER BY 1""").fetchall()
    res["card_txns"] = con.execute("""SELECT count(*), count_if(is_fraud), count(DISTINCT customer_id)
                                      FROM txns WHERE product_type LIKE 'Tarjeta%'""").fetchone()
    res["txns_total"] = con.execute("SELECT count(*) FROM txns").fetchone()[0]
    res["card_txn_types"] = con.execute("""SELECT transaction_type, count(*) FROM txns WHERE product_type LIKE 'Tarjeta%'
                                           GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    res["transcripts"] = con.execute("""SELECT count(*), count(DISTINCT customer_text), count(DISTINCT full_text),
                                               count(DISTINCT detected_intents), count(DISTINCT detected_language)
                                        FROM raw_call_transcripts""").fetchone()
    res["transcript_openings"] = con.execute("""
        SELECT regexp_extract(customer_text, '^[^.?!]*[.?!]( [^.?!]*[.?!])?') AS opening, count(*)
        FROM raw_call_transcripts GROUP BY 1 ORDER BY 2 DESC LIMIT 3""").fetchall()
    words = "cargo|cobro|no reconozco|fraude|duplicad|cajero|robo|robaron|perd[ií]|bloque|reembols|disputa"
    res["dispute_words"] = con.execute(f"""SELECT count_if(regexp_matches(lower(full_text), '{words}'))
                                           FROM raw_call_transcripts""").fetchone()[0]
    res["descriptions"] = con.execute("""SELECT count(DISTINCT description), count(*) FROM raw_complaints""").fetchone()
    res["origin_links"] = con.execute("SELECT count(origin_interaction_id) FROM raw_complaints").fetchone()[0]
    res["languages"] = con.execute("""SELECT detected_language, count(*) FROM raw_call_transcripts
                                      GROUP BY 1 ORDER BY 2 DESC""").fetchall()
    return res


# ---------- report ----------

def verdict(v: dict, p: dict, m: dict, d: dict) -> tuple[str, list[list[str]]]:
    share = sum(c for cat, _, c in v["by_category"] if cat in DISPUTE_CATEGORIES) / v["complaints_total"]
    disp = [r for r in p["complaints"] if r[0] in DISPUTE_CATEGORIES]
    sla = sum(r[1] * r[4] for r in disp) / sum(r[1] for r in disp)
    backlog = sum(r[1] * r[5] for r in disp) / sum(r[1] for r in disp)
    days = sum(r[1] * r[3] for r in disp) / sum(r[1] for r in disp)
    base = next(x for x in m["variants"] if x["tolerance"] == AMOUNT_TOLERANCES[0] and x["same_currency"])
    true_hit = 1 - base["true"][1] / base["true"][0]
    ctrl_hit = 1 - base["control"][1] / base["control"][0]
    volume_ok = share >= 0.2
    pain_ok = sla >= 0.1 or days >= 7
    rows = [
        ["Relevant volume", "✅" if volume_ok else "❌",
         f"{share:.1%} of all complaints are card-charge disputes ({n(sum(c for cat, _, c in v['by_category'] if cat in DISPUTE_CATEGORIES))} "
         f"in 3 years, ~{v['monthly_dispute_range'][0]:,}–{v['monthly_dispute_range'][1]:,} per month), from "
         f"{pct(v['customers_with_dispute'], v['customers_total'])} of customers."],
        ["Measurable pain", "✅" if pain_ok else "❌",
         f"Dispute complaints take {days:.1f} days on average, {sla:.1%} breach the SLA and {backlog:.1%} are still "
         "open, in process or escalated. The same holds for every other category (the synthetic data does not make "
         "disputes worse than the rest), so the pain is real but not dispute-specific."],
        ["Data to build on", "⚠️",
         f"Enough structured data to look transactions up ({n(d['card_txns'][0])} card transactions of "
         f"{n(d['card_txns'][2])} customers), but no natural-language dispute text: the {n(d['transcripts'][0])} "
         f"transcripts come from {d['transcripts'][1]} customer-text templates about balances, with "
         f"{n(d['dispute_words'])} mentions of a charge. Complaints cannot be tied to a transaction: with the true "
         f"customer {true_hit:.1%} of claims find a candidate, with a random customer {ctrl_hit:.1%}."],
    ]
    decision = ("**Confirm the dispute-intake flow**" if volume_ok and pain_ok else "**Switch to plan B**")
    return decision, rows


def render(v: dict, p: dict, m: dict, d: dict) -> str:
    today = dt.date.today().isoformat()
    decision, rows = verdict(v, p, m, d)
    L = ["# EDA Findings — Gate 1", "",
         f"Generated by `analysis/02_business.py` on {today} (`make eda`) from the DuckDB copy built by "
         "`make profile`; monthly series in `analysis/out/business/` (git-ignored). Outcome columns are used only to "
         "describe today's service (evaluation labels, never system inputs). Data quality caveats: "
         "[`data_quality_report.md`](data_quality_report.md).", "",
         "## Gate 1 decision", "",
         f"{decision}, with two conditions the data imposes on the rest of the plan (see "
         "[What this means for the team](#what-this-means-for-the-team)).", ""]
    L += md_table(["Criterion", "Met", "Evidence"], rows, "---|:---:|---")

    # Volume
    L += ["## 1. Volume", "", "### Complaints by category", ""]
    total = v["complaints_total"]
    L += md_table(["Category", "Subcategory", "Complaints", "Share", "Flow (C6 draft)"],
                  [[f"`{c}`", s, n(k), pct(k, total), DISPUTE_CATEGORIES.get(c, "out_of_scope")]
                   for c, s, k in v["by_category"]], "---|---|---:|---:|---")
    L += ["Subcategory is empty in ~10% of complaints; the category is always set and maps one-to-one to it, so the "
          "category is the key used here.", ""]
    L += md_table(["Case type", "Complaints", "Of which disputes", "Dispute share"],
                  [[t, n(a), n(b), pct(b, a)] for t, a, b in v["by_case_type"]], "---|---:|---:|---:")
    L += md_table(["Year", "Complaints", "Dispute complaints"],
                  [[y, n(a), n(b)] for y, a, b in v["by_year"]], "---|---:|---:")
    lo, hi = v["monthly_share_range"]
    L += [f"Monthly dispute share stays between {lo:.1%} and {hi:.1%} (full months): stable, no seasonality.", ""]
    for col, title in (("country", "Country"), ("segment", "Segment"), ("channel", "Reception channel")):
        L += [f"### By {title.lower()}", ""]
        L += md_table([title, "Complaints", "Disputes", "Dispute share"],
                      [[a, n(b), n(c), f"{s:.1%}"] for a, b, c, s in v["cuts"][col]], "---|---:|---:|---:")
    L += ["### Contacts (call center and digital channels)", ""]
    ct = v["contacts_total"]
    L += md_table(["Contact reason", "Contacts", "Share"],
                  [[r, n(k), pct(k, ct)] for r, k in v["contacts_by_reason"]], "---|---:|---:")
    L += ["`contact_reason` has only these six values and none of them is \"dispute\": contacts cannot be split into "
          "dispute and non-dispute. Complaints are the only source that names disputed charges.", ""]

    # Pain
    L += ["## 2. Pain: how these cases are handled today", ""]
    L += md_table(["Group", "Complaints", "Median days to resolve", "Mean days", "SLA breached", "Still open*",
                   "Escalated", "Median hours to first response", "Satisfaction (1–5)", "Compensated**",
                   "Median compensation", "Repeat complainer"],
                  [[f"`{r[0]}`" if r[0] in DISPUTE_CATEGORIES else r[0], n(r[1]), f1(r[2]), f1(r[3]),
                    pct(r[4], 1), pct(r[5], 1), pct(r[6], 1), f1(r[7]), f1(r[8]), pct(r[9], 1), f1(r[11]),
                    pct(r[10], 1)] for r in p["complaints"]], "---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:")
    L += ["\\* Open, In Process or Escalated. \\*\\* Share of resolved or closed complaints with a compensation "
          "amount (`compensation_granted` holds the amount, in the complaint's currency).", ""]
    L += ["### Contacts by reason", ""]
    L += md_table(["Contact reason", "Contacts", "Resolved on first contact", "Escalated", "Needs follow-up",
                   "Median minutes", "Median wait (min)", "Mean sentiment"],
                  [[r[0], n(r[1]), pct(r[2], 1), pct(r[3], 1), pct(r[4], 1), f1(r[5]), f1(r[6]),
                    "—" if r[7] is None else f"{r[7]:+.2f}"] for r in p["contacts"]],
                  "---|---:|---:|---:|---:|---:|---:|---:")
    L += md_table(["Contact reason", "Survey", "Surveys", "Mean score"],
                  [[a, b, n(c), f1(dd)] for a, b, c, dd in p["csat"]], "---|---|---:|---:")
    L += ["### Dispute complaints by country and channel", ""]
    L += md_table(["Country", "Disputes", "Median days", "SLA breached", "Still open"],
                  [[a, n(b), f1(c), pct(dd, 1), pct(e, 1)] for a, b, c, dd, e in p["dispute_by_country"]],
                  "---|---:|---:|---:|---:")
    L += md_table(["Channel", "Disputes", "Median days", "SLA breached"],
                  [[a, n(b), f1(c), pct(dd, 1)] for a, b, c, dd in p["dispute_by_channel"]], "---|---:|---:|---:")

    # Data
    L += ["## 3. Data the system can build on", "", "### Complaint ↔ transaction matching experiment", "",
          f"`complaints` has no `transaction_id` and `affected_product_id` never belongs to the complainant, so each "
          f"dispute complaint with an amount ({n(m['claims'])} of {n(m['dispute_complaints'])}) is matched against "
          f"the complainant's own transactions from the {MATCH_WINDOW_DAYS} days before it was filed. The control "
          "repeats the search with each claim assigned to a random other complainant: if amounts pointed to real "
          "transactions, the true customer would match far more often.", ""]
    rows = []
    for x in m["variants"]:
        t, c = x["true"], x["control"]
        rows.append([f"±{x['tolerance']:.0%}", "same" if x["same_currency"] else "any",
                     f"{pct(t[1], t[0])} / {pct(t[2], t[0])} / {pct(t[3], t[0])}",
                     f"{pct(c[1], c[0])} / {pct(c[2], c[0])} / {pct(c[3], c[0])}"])
    L += md_table(["Amount tolerance", "Currency", "True customer: 0 / 1 / 2+ candidates",
                   "Random customer (control): 0 / 1 / 2+"], rows, "---|---|---|---")
    lo_c, med_c, hi_c = m["claim_amounts"]
    L += [f"Why: `claimed_amount` is spread evenly between {lo_c:,.0f} and {hi_c:,.0f} (median {med_c:,.0f}) whatever "
          "its currency, while the median transaction is " + ", ".join(f"{cur} {a:,.0f}" for cur, a in m["txn_amounts"]) +
          ". Claim currencies (" + ", ".join(f"{cur} {k:,}" for cur, k in m["currency"]) + ") are unrelated to the "
          "customer's country, and MXN claims exist although no transaction is in MXN. "
          f"{pct(m['window_activity'][1], m['window_activity'][0])} of claimants have any transaction in the window "
          f"(median {m['window_activity'][2]:.0f}). **The complaint amounts are synthetic noise: complaints tell us "
          "how many disputes there are and how they are handled, not which transaction they are about.**", ""]

    L += ["### Transactions, cards and labels", ""]
    L += [f"- {n(d['txns_total'])} transactions, {n(d['card_txns'][0])} on cards "
          f"({', '.join(f'{t} {k:,}' for t, k in d['cards'])} card products) from {n(d['card_txns'][2])} customers; "
          "types: " + ", ".join(f"{t} {k:,}" for t, k in d["card_txn_types"]) + ".",
          f"- `is_fraud` marks {n(d['card_txns'][1])} card transactions ({pct(d['card_txns'][1], d['card_txns'][0], 2)}): "
          "usable as an evaluation label for unrecognized-charge cases, never as an input.",
          "- No two card transactions share merchant and amount within 2 days (quality report): no organic "
          "duplicate charges.", ""]
    L += ["### Natural-language data", ""]
    tr = d["transcripts"]
    L += [f"- `call_transcripts`: {n(tr[0])} transcripts, but only **{tr[1]} distinct customer texts** and {tr[2]} "
          f"distinct full texts, {tr[3]} intent value(s) and {tr[4]} language(s) "
          f"({', '.join(f'{lang} {k:,}' for lang, k in d['languages'])}). They open with: " +
          "; ".join(f"\"{o}\" ({k:,})" for o, k in d["transcript_openings"][:2]) +
          f". {n(d['dispute_words'])} transcripts mention a charge, fraud, ATM, theft, block or refund.",
          f"- `complaints.description`: {d['descriptions'][0]} distinct texts for {n(d['descriptions'][1])} "
          "complaints (\"Queja relacionada con …\").",
          f"- `complaints.origin_interaction_id` is set in {n(d['origin_links'])} complaints: complaints cannot be "
          "linked to their call or transcript.",
          "- No Portuguese anywhere (the dataset covers Mexico, Colombia and Argentina).", ""]

    share = sum(c for cat, _, c in v["by_category"] if cat in DISPUTE_CATEGORIES) / v["complaints_total"]
    L += ["## What this means for the team", "",
          "1. **The flow stands** (volume and pain are there) and the case for it is service time and SLA: "
          f"disputes are {share:.0%} of complaints and take about two weeks each today.",
          "2. **P3 — classifier and prompts:** the dataset has no dispute utterances in any language. Training and "
          "dev data must be `team_generated` (ES and PT), labeled with the C6 taxonomy; the transcripts only serve "
          "as out-of-scope examples (balance questions).",
          "3. **P4 — evaluation:** held-out cases are `team_generated` utterances on the demo customers' real "
          "transactions; `duplicate_charge` needs fixture transactions; `is_fraud` can back the expected outcome "
          "of unrecognized-charge cases. Baseline numbers for the pitch come from the tables above.",
          "4. **Transaction lookup** stays as the backend does it: search the customer's own card transactions by "
          "amount, date and merchant from the conversation. Complaints cannot seed it.",
          "5. **Taxonomy C6 draft** in [`analysis/mappings/contact_reason_to_flow.csv`](../analysis/mappings/"
          "contact_reason_to_flow.csv): `Transactions` → `unrecognized_charge`, `Fees` → `other_in_scope` (or "
          "`wrong_amount`, to agree with P3/P4), other categories → `out_of_scope`; `Queja`/`Transaccional` "
          "contacts are mixed and cannot be mapped.", ""]
    return "\n".join(L).rstrip() + "\n"


def main() -> None:
    if not DB_FILE.exists():
        raise SystemExit("data/profile.duckdb not found: run `make profile` first.")
    started = time.time()
    con = duckdb.connect(str(DB_FILE), read_only=True)
    views(con)
    log("volume")
    v = volume(con)
    log("pain")
    p = pain(con)
    log("matching experiment")
    m = matching(con)
    log("data assets")
    d = data_assets(con)
    write_csv(MAPPING, ["source", "value", "subcategory", "flow", "dispute_type", "note"], FLOW_MAPPING)
    REPORT.write_text(render(v, p, m, d), encoding="utf-8", newline="\n")
    log(f"wrote {REPORT.relative_to(REPO_ROOT)} and {MAPPING.relative_to(REPO_ROOT)} in {time.time() - started:,.0f} s")


if __name__ == "__main__":
    main()
