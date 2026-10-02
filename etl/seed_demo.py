"""DEPRECATED demo seeder: superseded by etl/load_postgres.py (make seed), which loads the full
silver dataset in the canonical dictionary vocabulary. Kept for its identity/realm helpers, which
the loader imports; running it directly would load raw Spanish values the backend no longer reads.


Temporary until the full ETL loader (P2) exists. Picks 20 demo customers deterministically, loads their
customers/products/recent transactions plus all service agents and exchange rates, adds a few clearly
labeled team-generated fixture transactions for the demo scripts, writes etl/seeds/demo_customers.csv and
patches the Keycloak realm file so test users cliente01..cliente20 carry an opaque customer_ref.

Identity is pseudonymized: customers holds no names; customer_identity maps a random customer_ref (the only
identifier in tokens) to the customer_id and stores the names as AES-256-GCM ciphertext bound to the row and
column (associated data "<customer_id>|<column>|v1"). The key is PII_KEY (base64, 32 bytes) from the
environment or the repo's .env (`make env` creates one).

Usage: python etl/seed_demo.py   (Postgres from docker compose must be running)
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import duckdb
import psycopg
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW = REPO_ROOT / "data" / "raw"
SEEDS = REPO_ROOT / "etl" / "seeds"
REALM_FILE = REPO_ROOT / "infra" / "keycloak" / "latam-bank-realm.json"
KEY_VERSION = 1


def load_env_file(path: Path = REPO_ROOT / ".env") -> None:
    """Minimal .env reader (KEY=value lines); real environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        key, sep, value = line.partition("=")
        if sep and not key.strip().startswith("#"):
            os.environ.setdefault(key.strip(), value.split(" #")[0].strip())


load_env_file()

DEMO_TODAY = datetime.fromisoformat(os.environ.get("DEMO_TODAY", "2026-06-17")).replace(tzinfo=timezone.utc)
WINDOW_DAYS = 180          # activity window used to pick customers
HISTORY_DAYS = 365         # transaction history loaded per demo customer
N_CUSTOMERS = 20
CARD_TYPES = ("Tarjeta Crédito", "Tarjeta Débito")
# Customers per (country, segment); the extra slots go to the largest groups.
EXTRA_SLOTS = {("México", "Basic"): 3, ("Colombia", "Basic"): 2, ("Argentina", "Basic"): 1,
               ("México", "Plus"): 1, ("Colombia", "Plus"): 1}

PG_DSN = "host={h} port={p} dbname={d} user={u} password={pw}".format(
    h=os.environ.get("POSTGRES_HOST", "localhost"), p=os.environ.get("POSTGRES_PORT", "5433"),
    d=os.environ.get("POSTGRES_DB", "bank"), u=os.environ.get("POSTGRES_USER", "bank_admin"),
    pw=os.environ.get("POSTGRES_PASSWORD", "change-me-local"))


def pii_cipher() -> AESGCM:
    """AES-GCM cipher from PII_KEY (base64, 32 bytes); exits with a hint when it is missing."""
    key = base64.b64decode(os.environ.get("PII_KEY", ""))
    if len(key) != 32:
        raise SystemExit("PII_KEY missing or not 32 bytes base64: run `make env` (writes it to .env)")
    return AESGCM(key)


def encrypt(aead: AESGCM, customer_id: str, column: str, value: str) -> bytes:
    """Encrypt as nonce || ciphertext || tag, bound to customer, column and key version (backend pii.Decrypt)."""
    nonce = os.urandom(12)
    aad = f"{customer_id}|{column}|v{KEY_VERSION}".encode()
    return nonce + aead.encrypt(nonce, value.encode("utf-8"), aad)


def customer_refs(ordered_ids: list[str]) -> dict[str, str]:
    """Keep existing refs from the mapping file (the realm must match); new customers get a random one."""
    refs: dict[str, str] = {}
    path = SEEDS / "demo_customers.csv"
    if path.exists():
        for row in csv.DictReader(path.open(encoding="utf-8")):
            if row.get("customer_ref"):
                refs[row["customer_id"]] = row["customer_ref"]
    return {cid: refs.get(cid) or "cr_" + secrets.token_urlsafe(18) for cid in ordered_ids}


def csv_glob(table: str) -> str:
    """Glob for every daily CSV of a partitioned raw table."""
    return (RAW / table / "*" / "*" / "*" / "*.csv").as_posix()


def pick_customers(con: duckdb.DuckDBPyConnection) -> list[dict]:
    """Deterministic 20 demo customers: active, with recent card purchases, spread over country and segment."""
    since = (DEMO_TODAY - timedelta(days=WINDOW_DAYS)).date().isoformat()
    rows = con.execute(f"""
        WITH cards AS (
            SELECT DISTINCT product_id, customer_id FROM read_csv('{(RAW / 'products.csv').as_posix()}', all_varchar = true)
            WHERE product_type IN {CARD_TYPES} AND product_status = 'Active'
        ),
        purchases AS (
            SELECT DISTINCT t.transaction_id, t.customer_id
            FROM read_csv('{csv_glob('transactions')}', all_varchar = true, union_by_name = true) t
            JOIN cards c USING (product_id)
            WHERE t.transaction_type = 'Purchase' AND t.merchant_name IS NOT NULL
              AND CAST(t.transaction_date AS TIMESTAMP) >= TIMESTAMP '{since}'
        ),
        active AS (SELECT customer_id, count(*) AS n FROM purchases GROUP BY 1 HAVING count(*) >= 4),
        cust AS (
            SELECT DISTINCT ON (customer_id) customer_id, country, segment
            FROM read_csv('{(RAW / 'customers.csv').as_posix()}', all_varchar = true)
            WHERE customer_status = 'Active' ORDER BY customer_id, last_updated DESC
        )
        SELECT c.customer_id, c.country, c.segment, a.n FROM cust c JOIN active a USING (customer_id)
    """).fetchall()

    groups: dict[tuple[str, str], list[tuple[str, int]]] = {}
    for cid, country, segment, n in rows:
        groups.setdefault((country, segment), []).append((cid, n))
    stable = lambda cid: hashlib.sha256(cid.encode()).hexdigest()  # deterministic, not by row order
    chosen = []
    for country in ("México", "Colombia", "Argentina"):
        for segment in ("Basic", "Plus", "Premium", "Student"):
            members = sorted(groups.get((country, segment), []), key=lambda m: stable(m[0]))
            take = 1 + EXTRA_SLOTS.get((country, segment), 0)
            chosen += [{"customer_id": cid, "country": country, "segment": segment} for cid, _ in members[:take]]
    if len(chosen) != N_CUSTOMERS:
        raise SystemExit(f"Expected {N_CUSTOMERS} demo customers, got {len(chosen)}")
    return chosen


def load(con: duckdb.DuckDBPyConnection, chosen: list[dict], refs: dict[str, str]) -> dict[str, int]:
    """Load demo customers with their history, agents and exchange rates from raw CSVs; returns row counts."""
    ids = [c["customer_id"] for c in chosen]
    con.execute("CREATE TEMP TABLE demo_ids (customer_id VARCHAR)")
    con.executemany("INSERT INTO demo_ids VALUES (?)", [[i] for i in ids])
    history_since = (DEMO_TODAY - timedelta(days=HISTORY_DAYS)).date().isoformat()

    customers = con.execute(f"""
        SELECT DISTINCT ON (customer_id) customer_id, first_name, last_name, country, segment,
               detected_accent, customer_status, email
        FROM read_csv('{(RAW / 'customers.csv').as_posix()}', all_varchar = true)
        WHERE customer_id IN (SELECT customer_id FROM demo_ids) ORDER BY customer_id, last_updated DESC
    """).fetchall()
    products = con.execute(f"""
        SELECT DISTINCT ON (product_id) product_id, customer_id, product_type,
               CASE WHEN product_type LIKE 'Tarjeta%' THEN right(product_number, 4) END,
               currency, product_status, TRY_CAST(credit_limit AS DECIMAL(15, 2)),
               -- Card brand from the BIN (first digits); only the brand and last 4 digits are kept.
               CASE WHEN product_type NOT LIKE 'Tarjeta%' THEN NULL
                    WHEN product_number LIKE '4%' THEN 'visa'
                    WHEN regexp_matches(product_number, '^(5[1-5]|222[1-9]|22[3-9]|2[3-6]|27[01]|2720)') THEN 'mastercard'
                    WHEN regexp_matches(product_number, '^3[47]') THEN 'amex'
                    ELSE 'other' END
        FROM read_csv('{(RAW / 'products.csv').as_posix()}', all_varchar = true)
        WHERE customer_id IN (SELECT customer_id FROM demo_ids) ORDER BY product_id, last_updated DESC
    """).fetchall()
    transactions = con.execute(f"""
        SELECT DISTINCT ON (transaction_id) transaction_id, customer_id, product_id,
               CAST(transaction_date AS TIMESTAMP), transaction_type, CAST(amount AS DECIMAL(15, 2)), currency,
               TRY_CAST(amount_usd AS DECIMAL(15, 2)), merchant_name, merchant_category,
               transaction_country, transaction_city, transaction_status, channel
        FROM read_csv('{csv_glob('transactions')}', all_varchar = true, union_by_name = true)
        WHERE customer_id IN (SELECT customer_id FROM demo_ids)
          AND CAST(transaction_date AS TIMESTAMP) >= TIMESTAMP '{history_since}'
        ORDER BY transaction_id, process_date DESC
    """).fetchall()
    agents = con.execute(f"""
        SELECT DISTINCT ON (agent_id) agent_id, first_name, last_name, languages, specialty, agent_status
        FROM read_csv('{(RAW / 'service_agents.csv').as_posix()}', all_varchar = true) ORDER BY agent_id
    """).fetchall()
    rates = con.execute(f"""
        SELECT DISTINCT ON (date, source_currency, target_currency) CAST(date AS DATE), source_currency,
               target_currency, CAST(exchange_rate AS DECIMAL(18, 8)), source
        FROM read_csv('{(RAW / 'daily_exchange_rates.csv').as_posix()}', all_varchar = true)
        ORDER BY date, source_currency, target_currency
    """).fetchall()

    fixtures = team_fixtures(products, customers, ids)
    aead = pii_cipher()
    # Contact emails are encrypted like names; the notifier redirects them to a test inbox on real SMTP.
    identities = [(refs[cid], cid, encrypt(aead, cid, "first_name", first), encrypt(aead, cid, "last_name", last),
                   encrypt(aead, cid, "email", email) if email else None, KEY_VERSION)
                  for cid, first, last, *_, email in customers]
    with psycopg.connect(PG_DSN) as pg, pg.cursor() as cur:
        cur.execute("TRUNCATE notifications, audit_events, handoffs, card_blocks, dispute_cases, pending_actions, messages, "
                    "chat_sessions, transactions, products, customer_identity, customers, service_agents, "
                    "exchange_rates CASCADE")
        cur.executemany("INSERT INTO customers VALUES (%s,%s,%s,%s,%s)", [(c[0], *c[3:7]) for c in customers])
        cur.executemany("INSERT INTO customer_identity (customer_ref, customer_id, first_name_ct, last_name_ct, "
                        "email_ct, key_version) VALUES (%s,%s,%s,%s,%s,%s)", identities)
        cur.executemany("INSERT INTO products VALUES (%s,%s,%s,%s,%s,%s,%s,%s)", products)
        cur.executemany("INSERT INTO transactions (transaction_id, customer_id, product_id, transaction_date, "
                        "transaction_type, amount, currency, amount_usd, merchant_name, merchant_category, "
                        "transaction_country, transaction_city, transaction_status, channel) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)", transactions)
        cur.executemany("INSERT INTO transactions (transaction_id, customer_id, product_id, transaction_date, "
                        "transaction_type, amount, currency, amount_usd, merchant_name, merchant_category, "
                        "transaction_country, transaction_city, transaction_status, channel, origin) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'team_generated')", fixtures)
        cur.executemany("INSERT INTO service_agents VALUES (%s,%s,%s,%s,%s,%s)", agents)
        with cur.copy("COPY exchange_rates FROM STDIN") as copy:
            for row in rates:
                copy.write_row(row)
    return {"customers": len(customers), "products": len(products), "transactions": len(transactions),
            "team_fixtures": len(fixtures), "agents": len(agents), "exchange_rates": len(rates)}


def team_fixtures(products: list[tuple], customers: list[tuple], ordered_ids: list[str]) -> list[tuple]:
    """Team-generated transactions for the scripted demo cases (labeled origin=team_generated in the DB).

    cliente02 gets a duplicate charge (Portuguese demo), cliente03 a high-value foreign purchase (escalation).
    """
    cards: dict[str, str] = {}
    for product_id, customer_id, product_type, _last4, _cur, status, *_ in products:
        if product_type in CARD_TYPES and status == "Active":
            cards.setdefault(customer_id, product_id)
    country = {row[0]: row[3] for row in customers}  # row = (id, first, last, country, ...) before the split
    c2, c3 = ordered_ids[1], ordered_ids[2]
    p2, p3 = cards[c2], cards[c3]
    day = DEMO_TODAY - timedelta(days=2)
    return [
        # Duplicate charge: same merchant and amount, three minutes apart (cliente02, Portuguese demo).
        ("TRX-DEMO-DUP-0001", c2, p2, day.replace(hour=13, minute=5), "Purchase", 89.90, "USD", 89.90,
         "Mercado Central", "Food", country[c2], None, "Approved", "POS"),
        ("TRX-DEMO-DUP-0002", c2, p2, day.replace(hour=13, minute=8), "Purchase", 89.90, "USD", 89.90,
         "Mercado Central", "Food", country[c2], None, "Approved", "POS"),
        # High-value foreign purchase the customer does not recognize (cliente03, escalation demo).
        ("TRX-DEMO-FRD-0001", c3, p3, day.replace(hour=3, minute=41), "Purchase", 1450.00, "USD", 1450.00,
         "Electro Mundo Online", "Electronics", "USA", "Miami", "Approved", "Web"),
    ]


def write_mapping_and_realm(chosen: list[dict], ordered_ids: list[str], refs: dict[str, str]) -> None:
    """Write etl/seeds/demo_customers.csv and the Keycloak realm users (test customers, load-test users, staff)."""
    SEEDS.mkdir(parents=True, exist_ok=True)
    by_id = {c["customer_id"]: c for c in chosen}
    with (SEEDS / "demo_customers.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["username", "customer_id", "customer_ref", "country", "segment"])
        for i, cid in enumerate(ordered_ids, 1):
            w.writerow([f"cliente{i:02d}", cid, refs[cid], by_id[cid]["country"], by_id[cid]["segment"]])

    realm = json.loads(REALM_FILE.read_text(encoding="utf-8"))
    otp_data = json.dumps({"subType": "totp", "digits": 6, "counter": 0, "period": 30, "algorithm": "HmacSHA1"})
    users = []
    for i, cid in enumerate(ordered_ids, 1):
        name = f"cliente{i:02d}"
        # cliente20 is the password-recovery demo user: its address comes from the Keycloak container
        # environment (the test inbox, MAIL_REDIRECT_TO), resolved when the realm is imported.
        email = "${KC_DEMO_RESET_EMAIL:cliente20@example.test}" if name == "cliente20" else f"{name}@example.test"
        users.append({
            "username": name, "enabled": True, "firstName": "Test", "lastName": f"Customer {i:02d}",
            "email": email, "emailVerified": True,
            "attributes": {"customer_ref": [refs[cid]]}, "realmRoles": ["customer"],
            "credentials": [
                {"type": "password", "value": f"Test-Only-{name}", "temporary": False},
                # Test-only TOTP seed so the step-up demo works without enrolling a phone.
                {"type": "otp", "userLabel": "demo-totp",
                 "secretData": json.dumps({"value": f"nicebank-demo-otp-{name}"}), "credentialData": otp_data},
            ],
        })
    # Load-test users (JMeter): same demo customers, password only, no TOTP. They can never pass step-up,
    # so a load test cannot block cards. Test environment only.
    for i, cid in enumerate(ordered_ids, 1):
        name = f"carga{i:02d}"
        users.append({
            "username": name, "enabled": True, "firstName": "Load", "lastName": f"Test {i:02d}",
            "email": f"{name}@example.test", "emailVerified": True,
            "attributes": {"customer_ref": [refs[cid]]}, "realmRoles": ["customer"],
            "credentials": [{"type": "password", "value": f"Test-Only-{name}", "temporary": False}],
        })
    for name, role in (("agente01", "agent"), ("agente02", "agent"), ("supervisor01", "supervisor")):
        users.append({
            "username": name, "enabled": True, "firstName": "Test", "lastName": name.capitalize(),
            "email": f"{name}@example.test", "emailVerified": True, "realmRoles": [role],
            "credentials": [{"type": "password", "value": f"Test-Only-{name}", "temporary": False}],
        })
    realm["users"] = users
    REALM_FILE.write_text(json.dumps(realm, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")


def main() -> None:
    """Run the deprecated demo seed (kept for reference; use make seed)."""
    con = duckdb.connect()
    chosen = pick_customers(con)
    # Order follows (country, segment); cliente01 is a Mexican Basic customer (normal ES demo).
    ordered_ids = [c["customer_id"] for c in chosen]
    refs = customer_refs(ordered_ids)
    counts = load(con, chosen, refs)
    write_mapping_and_realm(chosen, ordered_ids, refs)
    print("Loaded:", ", ".join(f"{k}={v:,}" for k, v in counts.items()))
    print(f"Wrote {SEEDS.relative_to(REPO_ROOT)}/demo_customers.csv and updated {REALM_FILE.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
