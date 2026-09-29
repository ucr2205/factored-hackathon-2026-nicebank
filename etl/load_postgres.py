"""Load the full silver dataset into the operational Postgres (contract C1), replacing seed_demo.py.

Reads data/silver (run `make etl` first) and loads ALL customers, products, transactions, exchange
rates and agents with COPY. It keeps every guarantee of the old demo seeder, reusing its helpers:
the same deterministic 20 demo customers mapped to Keycloak users (etl/seeds/demo_customers.csv and
the realm file are refreshed), AES-GCM encrypted identity for every customer, the team_generated demo
fixture transactions, and idempotency (TRUNCATE + load).

The operational database uses the same canonical dictionary vocabulary as silver (Credit Card,
Mexico, ...): backend queries and the frontend label map read those values directly, so there is no
translation layer anywhere. Demo customers get unique clienteNN@example.test contact emails so
notifications never depend on the sanitized (mostly nulled) dataset emails.

Usage: python etl/load_postgres.py   (Postgres from docker compose must be running)
"""

from __future__ import annotations

import hashlib
import secrets
import sys
import time
from datetime import timedelta
from pathlib import Path

import duckdb
import psycopg

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl"))
sys.path.insert(0, str(REPO_ROOT))

from etl.pipeline.config import PipelineConfig  # noqa: E402
from etl.pipeline.writers import silver_exists, silver_glob  # noqa: E402
from seed_demo import (  # noqa: E402  (shared helpers; seed_demo itself is superseded by this loader)
    DEMO_TODAY, KEY_VERSION, N_CUSTOMERS, PG_DSN, WINDOW_DAYS,
    customer_refs, encrypt, pii_cipher, write_mapping_and_realm,
)

EXTRA_SLOTS = {("Mexico", "Basic"): 3, ("Colombia", "Basic"): 2, ("Argentina", "Basic"): 1,
               ("Mexico", "Plus"): 1, ("Colombia", "Plus"): 1}
BATCH = 50_000
CARD_TYPES = ("Credit Card", "Debit Card")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def demo_fixtures(con: duckdb.DuckDBPyConnection, ordered_ids: list[str]) -> list[tuple]:
    """Team-generated transactions for the scripted demo cases (origin=team_generated in the DB).

    cliente02 gets a duplicate charge (Portuguese demo), cliente03 a high-value foreign purchase
    (escalation). Same cases seed_demo.py created, expressed in the canonical vocabulary.
    """
    rows = con.execute(
        "SELECT p.customer_id, p.product_id, c.country FROM products p JOIN customers c USING (customer_id) "
        "WHERE p.customer_id IN (SELECT unnest(?)) AND p.product_type IN ('Credit Card', 'Debit Card') "
        "AND p.product_status = 'Active' ORDER BY p.product_id", [ordered_ids]).fetchall()
    cards: dict[str, str] = {}
    country: dict[str, str] = {}
    for cid, pid, ctry in rows:
        cards.setdefault(cid, pid)
        country[cid] = ctry
    c2, c3 = ordered_ids[1], ordered_ids[2]
    day = DEMO_TODAY - timedelta(days=2)
    return [
        ("TRX-DEMO-DUP-0001", c2, cards[c2], day.replace(hour=13, minute=5), "Purchase", 89.90, "USD",
         89.90, "Mercado Central", "Food", country[c2], None, "Approved", "POS"),
        ("TRX-DEMO-DUP-0002", c2, cards[c2], day.replace(hour=13, minute=8), "Purchase", 89.90, "USD",
         89.90, "Mercado Central", "Food", country[c2], None, "Approved", "POS"),
        ("TRX-DEMO-FRD-0001", c3, cards[c3], day.replace(hour=3, minute=41), "Purchase", 1450.00, "USD",
         1450.00, "Electro Mundo Online", "Electronics", "USA", "Miami", "Approved", "Web"),
    ]


def connect_silver(cfg: PipelineConfig) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    for table in ("customers", "products", "transactions", "daily_exchange_rates",
                  "service_agents", "dim_merchants"):
        if not silver_exists(cfg, table):
            raise SystemExit(f"silver '{table}' not found: run `make etl` first")
        con.execute(f"CREATE VIEW {table} AS SELECT * FROM "
                    f"read_parquet('{silver_glob(cfg, table)}', hive_partitioning = true)")
    return con


def pick_demo_customers(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Same deterministic selection as seed_demo.py, expressed over silver (English values)."""
    since = DEMO_TODAY.date().isoformat()
    rows = con.execute(f"""
        WITH cards AS (
            SELECT DISTINCT product_id, customer_id FROM products
            WHERE product_type IN ('Credit Card', 'Debit Card') AND product_status = 'Active'
        ),
        purchases AS (
            SELECT t.customer_id, count(*) AS n
            FROM transactions t JOIN cards c USING (product_id)
            WHERE t.transaction_type = 'Purchase' AND t.merchant_name IS NOT NULL
              AND t.transaction_date >= TIMESTAMP '{since}' - INTERVAL {WINDOW_DAYS} DAY
            GROUP BY 1 HAVING count(*) >= 4
        )
        SELECT c.customer_id, c.country, c.segment
        FROM customers c JOIN purchases USING (customer_id)
        WHERE c.customer_status = 'Active'
    """).fetchall()
    groups: dict[tuple[str, str], list[str]] = {}
    for cid, country, segment in rows:
        groups.setdefault((country, segment), []).append(cid)
    stable = lambda cid: hashlib.sha256(cid.encode()).hexdigest()  # noqa: E731 (same as seed_demo)
    chosen = []
    for country in ("Mexico", "Colombia", "Argentina"):
        for segment in ("Basic", "Plus", "Premium", "Student"):
            members = sorted(groups.get((country, segment), []), key=stable)
            take = 1 + EXTRA_SLOTS.get((country, segment), 0)
            chosen += [{"customer_id": cid, "country": country, "segment": segment}
                       for cid in members[:take]]
    if len(chosen) != N_CUSTOMERS:
        raise SystemExit(f"Expected {N_CUSTOMERS} demo customers, got {len(chosen)}")
    return chosen


def copy_rows(cur: psycopg.Cursor, copy_sql: str,
              con: duckdb.DuckDBPyConnection, select_sql: str) -> int:
    res = con.execute(select_sql)
    n = 0
    with cur.copy(copy_sql) as copy:
        while True:
            rows = res.fetchmany(BATCH)
            if not rows:
                break
            for row in rows:
                copy.write_row(row)
            n += len(rows)
    return n


def main() -> None:
    cfg = PipelineConfig()
    con = connect_silver(cfg)
    log("selecting demo customers from silver")
    chosen = pick_demo_customers(con)
    ordered_ids = [c["customer_id"] for c in chosen]
    refs = customer_refs(ordered_ids)
    demo_email = {cid: f"cliente{i:02d}@example.test" for i, cid in enumerate(ordered_ids, 1)}
    aead = pii_cipher()

    counts: dict[str, int] = {}
    with psycopg.connect(PG_DSN) as pg, pg.cursor() as cur:
        cur.execute(
            "TRUNCATE notifications, audit_events, handoffs, card_blocks, dispute_cases, "
            "pending_actions, messages, chat_sessions, transactions, products, customer_identity, "
            "customers, service_agents, exchange_rates CASCADE")

        log("customers (150k)")
        counts["customers"] = copy_rows(
            cur, "COPY customers FROM STDIN", con,
            "SELECT customer_id, country, segment, detected_accent, customer_status "
            "FROM customers ORDER BY customer_id")

        log("customer_identity (encrypting names and contact emails)")
        rel = con.execute("SELECT customer_id, first_name, last_name, email "
                          "FROM customers ORDER BY customer_id")
        with cur.copy("COPY customer_identity (customer_ref, customer_id, first_name_ct, "
                      "last_name_ct, email_ct, key_version) FROM STDIN") as copy:
            n = 0
            while True:
                rows = rel.fetchmany(BATCH)
                if not rows:
                    break
                for cid, first, last, email in rows:
                    ref = refs.get(cid) or "cr_" + secrets.token_urlsafe(18)
                    email = demo_email.get(cid, email)
                    copy.write_row((
                        ref, cid,
                        encrypt(aead, cid, "first_name", first or ""),
                        encrypt(aead, cid, "last_name", last or ""),
                        encrypt(aead, cid, "email", email) if email else None,
                        KEY_VERSION,
                    ))
                n += len(rows)
        counts["customer_identity"] = n

        log("products (400k)")
        counts["products"] = copy_rows(
            cur, "COPY products FROM STDIN", con,
            "SELECT product_id, customer_id, product_type, card_last4, currency, "
            "product_status, credit_limit, card_brand FROM products ORDER BY product_id")

        log("transactions (4.4M, a few minutes)")
        # merchant_category re-joined from dim_merchants (normalized out of silver transactions);
        # domestic country names go back to Spanish, international rows keep their raw marker.
        txn_sql = """
            SELECT t.transaction_id, t.customer_id, t.product_id, t.transaction_date,
                   t.transaction_type, round(t.amount, 2), t.currency, t.amount_usd,
                   t.merchant_name, m.merchant_category, t.transaction_country,
                   t.transaction_city, t.transaction_status, t.channel
            FROM transactions t LEFT JOIN dim_merchants m USING (merchant_name)"""
        counts["transactions"] = copy_rows(
            cur,
            "COPY transactions (transaction_id, customer_id, product_id, transaction_date, "
            "transaction_type, amount, currency, amount_usd, merchant_name, merchant_category, "
            "transaction_country, transaction_city, transaction_status, channel) FROM STDIN",
            con, txn_sql)

        log("team_generated demo fixtures")
        fixtures = demo_fixtures(con, ordered_ids)
        cur.executemany(
            "INSERT INTO transactions (transaction_id, customer_id, product_id, transaction_date, "
            "transaction_type, amount, currency, amount_usd, merchant_name, merchant_category, "
            "transaction_country, transaction_city, transaction_status, channel, origin) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'team_generated')", fixtures)
        counts["team_fixtures"] = len(fixtures)

        log("service_agents and exchange_rates")
        counts["service_agents"] = copy_rows(
            cur, "COPY service_agents FROM STDIN", con,
            "SELECT agent_id, first_name, last_name, languages, specialty, agent_status "
            "FROM service_agents ORDER BY agent_id")
        counts["exchange_rates"] = copy_rows(
            cur, "COPY exchange_rates FROM STDIN", con,
            "SELECT rate_date, source_currency, target_currency, exchange_rate, source "
            "FROM daily_exchange_rates ORDER BY rate_date, source_currency, target_currency")

    write_mapping_and_realm(chosen, ordered_ids, refs)
    log("Loaded: " + ", ".join(f"{k}={v:,}" for k, v in counts.items()))
    log("Updated etl/seeds/demo_customers.csv and the Keycloak realm file")


if __name__ == "__main__":
    main()
