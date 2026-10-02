"""Create the NiceBank database objects and load the data bundle into a Postgres server.

Everything comes from the bundle next to this script (built by scripts/build_db_bundle.py on a machine where
`make seed` ran):
  sql/00_roles.sql, sql/01_schema.sql, sql/02_rls.sql   the same objects as infra/postgres/init
  data/<table>.csv + data/manifest.json                 one CSV per data table, with row counts and SHA-256

Steps (each logged with loguru):
  1. connect as the database owner (a superuser or a role with BYPASSRLS: the tables use FORCE ROW LEVEL SECURITY)
  2. pgvector extension and the application role (no superuser, no BYPASSRLS) for the backend
  3. tables, row-level security, grants and functions, only when the schema does not exist yet
  4. integrity check of every CSV against the manifest (row count and SHA-256)
  5. load in foreign-key order with COPY, in ONE transaction: all or nothing
  6. row counts in the database against the manifest, and PII_KEY against the encrypted names
  7. ANALYZE

Connection and options come from environment variables (or a .env file next to this script): see .env.example.

Usage: poetry install && poetry run python load_db.py [--replace] [--check-only]
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import psycopg
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from dotenv import load_dotenv
from loguru import logger
from psycopg import sql
from psycopg.conninfo import make_conninfo

HERE = Path(__file__).resolve().parent
SQL_DIR, DATA_DIR = HERE / "sql", HERE / "data"
# Foreign-key order: parents first.
TABLES = ["customers", "customer_identity", "products", "transactions", "exchange_rates", "service_agents", "kb_chunks"]
CHUNK = 1 << 20  # 1 MiB per COPY write


def setup_logging() -> None:
    logger.remove()
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    logger.add(sys.stderr, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level: <7}</level> | {message}")
    log_file = os.environ.get("LOG_FILE", "load_db.log")
    if log_file:
        logger.add(HERE / log_file, level="DEBUG", rotation="10 MB", retention=5, encoding="utf-8")


def env(name: str, default: str | None = None, required: bool = False) -> str:
    value = os.environ.get(name, default)
    if required and not value:
        logger.error("Missing environment variable {} (see .env.example)", name)
        sys.exit(2)
    return value or ""


def conninfo() -> str:
    return make_conninfo(
        host=env("DB_HOST", "localhost"), port=env("DB_PORT", "5432"), dbname=env("DB_NAME", required=True),
        user=env("DB_ADMIN_USER", required=True), password=env("DB_ADMIN_PASSWORD", required=True),
        sslmode=env("DB_SSLMODE", "prefer"), application_name="nicebank-load-db", connect_timeout=15)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(CHUNK):
            h.update(block)
    return h.hexdigest()


def check_bundle(manifest: dict) -> None:
    """Every CSV must exist and match the manifest exactly: a truncated or edited file stops the load."""
    for table in TABLES:
        meta = manifest["tables"][table]
        path = DATA_DIR / meta["file"]
        if not path.exists():
            logger.error("{} is missing from the bundle", path.name)
            sys.exit(3)
        started = time.monotonic()
        digest = sha256(path)
        if digest != meta["sha256"]:
            logger.error("{}: SHA-256 does not match the manifest (corrupted or edited file)", path.name)
            sys.exit(3)
        logger.info("bundle ok  {:<20} {:>12,} rows  {:>8.1f} MB  ({:.1f} s)", table, meta["rows"],
                    path.stat().st_size / 1e6, time.monotonic() - started)


def ensure_privileges(cur: psycopg.Cursor) -> None:
    cur.execute("SELECT rolsuper OR rolbypassrls, current_user FROM pg_roles WHERE rolname = current_user")
    allowed, user = cur.fetchone()
    if not allowed:
        logger.error("{} is neither superuser nor BYPASSRLS: the tables force row-level security, so loading as "
                     "this role would be refused. Use the database owner (POSTGRES_USER of the container).", user)
        sys.exit(4)


def ensure_roles(cur: psycopg.Cursor, app_user: str, app_password: str, dbname: str) -> None:
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (app_user,))
    if cur.fetchone():
        logger.info("role {} already exists (password unchanged)", app_user)
    else:
        cur.execute(sql.SQL("CREATE ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
            sql.Identifier(app_user), sql.Literal(app_password)))
        logger.success("role {} created (no superuser, no BYPASSRLS)", app_user)
    cur.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(sql.Identifier(dbname), sql.Identifier(app_user)))
    cur.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(app_user)))


def ensure_schema(cur: psycopg.Cursor, app_user: str) -> bool:
    """Creates tables, RLS, grants and functions on an empty database. Returns True when it created them."""
    cur.execute("SELECT to_regclass('public.customers') IS NOT NULL")
    if cur.fetchone()[0]:
        logger.info("schema already present: tables are kept, only data will be loaded")
        cur.execute((SQL_DIR / "migrations.sql").read_text(encoding="utf-8"))
        return False
    cur.execute((SQL_DIR / "01_schema.sql").read_text(encoding="utf-8"))
    logger.success("tables created (sql/01_schema.sql)")
    rls = (SQL_DIR / "02_rls.sql").read_text(encoding="utf-8")
    cur.execute(rls.replace(":app_user", sql.Identifier(app_user).as_string(cur)))
    logger.success("row-level security, grants and functions created (sql/02_rls.sql) for {}", app_user)
    return True


def table_rows(cur: psycopg.Cursor, table: str) -> int:
    cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
    return cur.fetchone()[0]


def load_table(cur: psycopg.Cursor, table: str, meta: dict) -> None:
    path = DATA_DIR / meta["file"]
    columns = sql.SQL(", ").join(sql.Identifier(c) for c in meta["columns"])
    copy_sql = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(sql.Identifier(table), columns)
    size, sent, next_log = path.stat().st_size, 0, 0.0
    started = time.monotonic()
    with path.open("rb") as f, cur.copy(copy_sql) as copy:
        while block := f.read(CHUNK):
            copy.write(block)
            sent += len(block)
            if size and sent / size >= next_log:
                logger.debug("  {} {:>3.0f}%", table, 100 * sent / size)
                next_log += 0.25
    logger.info("loaded     {:<20} {:>12,} rows  ({:.1f} s)", table, meta["rows"], time.monotonic() - started)
    if meta.get("serial"):  # keep sequences ahead of the loaded ids
        cur.execute(sql.SQL("SELECT setval(pg_get_serial_sequence({}, 'id'), coalesce(max(id), 1)) FROM {}").format(
            sql.Literal(table), sql.Identifier(table)))


def decrypts(key_b64: str, customer_id: str, blob: bytes, key_version: int) -> bool:
    """The backend decrypts names with PII_KEY: a different key would leave every name unreadable."""
    try:
        key = base64.b64decode(key_b64)
        if len(key) != 32:
            raise ValueError
    except ValueError:
        logger.error("PII_KEY must be 32 bytes in base64 (the same key the bundle was built with)")
        sys.exit(5)
    try:
        AESGCM(key).decrypt(blob[:12], blob[12:], f"{customer_id}|first_name|v{key_version}".encode())
        return True
    except InvalidTag:
        return False


def check_pii_key_in_bundle(key_b64: str, key_version: int) -> None:
    """Before connecting: one encrypted name from the CSV, so a wrong key fails in a second, not after the load."""
    with (DATA_DIR / "customer_identity.csv").open(encoding="utf-8", newline="") as f:
        row = next(csv.DictReader(f), None)
    blob = bytes.fromhex(row["first_name_ct"].removeprefix("\\x")) if row else b""  # COPY writes bytea as \x<hex>
    if row and not decrypts(key_b64, row["customer_id"], blob, key_version):
        logger.error("PII_KEY does not decrypt the names in the bundle: use the key the bundle was built with "
                     "(the backend would show no names and send no emails). Nothing was changed.")
        sys.exit(5)
    logger.success("PII_KEY decrypts the customer names in the bundle")


def check_pii_key(cur: psycopg.Cursor, key_b64: str, key_version: int) -> None:
    cur.execute("SELECT customer_id, first_name_ct FROM customer_identity ORDER BY customer_id LIMIT 1")
    row = cur.fetchone()
    if row and not decrypts(key_b64, row[0], bytes(row[1]), key_version):
        logger.error("PII_KEY does not decrypt the loaded names; rolling back")
        sys.exit(5)
    logger.success("PII_KEY decrypts the loaded customer names")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--replace", action="store_true",
                        help="empty the data tables (and the conversations, cases and audit that reference them) before loading")
    parser.add_argument("--check-only", action="store_true", help="only verify the bundle files; do not connect")
    args = parser.parse_args()
    load_dotenv(HERE / ".env")
    setup_logging()

    manifest = json.loads((DATA_DIR / "manifest.json").read_text(encoding="utf-8"))
    logger.info("bundle built {} from {} (key_version {})", manifest["built_at"], manifest["source"], manifest["key_version"])
    check_bundle(manifest)
    if args.check_only:
        logger.success("bundle verified; nothing loaded (--check-only)")
        return

    app_user, app_password = env("APP_DB_USER", required=True), env("APP_DB_PASSWORD", required=True)
    pii_key = env("PII_KEY", required=True)
    check_pii_key_in_bundle(pii_key, manifest["key_version"])
    started = time.monotonic()
    with psycopg.connect(conninfo()) as conn:
        info = conn.info
        logger.info("connected to {}:{}/{} as {} (PostgreSQL {})", info.host, info.port, info.dbname, info.user,
                    info.server_version // 10000)
        with conn.cursor() as cur:
            ensure_privileges(cur)
            ensure_roles(cur, app_user, app_password, info.dbname)
            ensure_schema(cur, app_user)
        conn.commit()

        with conn.cursor() as cur:  # one transaction for all the data: a failure leaves the database as it was
            existing = table_rows(cur, "customers")
            if existing and not args.replace:
                logger.error("the database already holds {:,} customers: run again with --replace to reload "
                             "(it also deletes conversations, cases and audit rows)", existing)
                sys.exit(6)
            if existing:
                cur.execute("TRUNCATE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE")
                logger.warning("--replace: data tables emptied (CASCADE)")
            for table in TABLES:
                load_table(cur, table, manifest["tables"][table])
            for table in TABLES:
                got, want = table_rows(cur, table), manifest["tables"][table]["rows"]
                if got != want:
                    logger.error("{}: {:,} rows in the database, {:,} in the manifest; rolling back", table, got, want)
                    sys.exit(7)
            check_pii_key(cur, pii_key, manifest["key_version"])
        conn.commit()
        logger.success("data committed")
        conn.autocommit = True
        conn.execute("ANALYZE")
        logger.info("ANALYZE done")
    total = sum(m["rows"] for m in manifest["tables"].values())
    logger.success("NiceBank database ready: {:,} rows in {} tables in {:.0f} s", total, len(TABLES), time.monotonic() - started)


if __name__ == "__main__":
    try:
        main()
    except psycopg.OperationalError as e:
        logger.error("cannot connect to Postgres: {}", str(e).strip())
        sys.exit(1)
    except psycopg.Error as e:
        logger.exception("database error, nothing from this run was committed: {}", e)
        sys.exit(1)
