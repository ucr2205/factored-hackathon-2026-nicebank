"""Build the database bundle for a server: the loader, the schema SQL and one CSV per data table, in one zip.

Run it on a machine where `make seed` ran (the local Postgres holds the full dataset). The zip goes to the
user's Downloads folder (or --out) and is unpacked and run on the server with deploy/dbload/README.md.

What goes in (nothing secret: names and emails stay AES-GCM ciphertext, the PII_KEY is not included):
  load_db.py, pyproject.toml, poetry.lock, .env.example, README.md   from deploy/dbload/
  sql/01_schema.sql, sql/02_rls.sql, sql/migrations.sql              from infra/postgres/ (psql variables resolved
                                                                     to a placeholder the loader fills in)
  data/<table>.csv, data/manifest.json                               exported with COPY, with rows and SHA-256
  keycloak/latam-bank-realm.json, keycloak/demo_customers.csv        the realm whose demo users match the data

Usage: `make db-bundle`, or poetry run python scripts/build_db_bundle.py [--out <dir>]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg import sql

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "etl"))
from seed_demo import KEY_VERSION, PG_DSN  # noqa: E402

STAGE = REPO_ROOT / "data" / "db_bundle" / "nicebank-db-bundle"
TABLES = ["customers", "customer_identity", "products", "transactions", "exchange_rates", "service_agents", "kb_chunks"]
LOADER_FILES = ["load_db.py", "pyproject.toml", "poetry.lock", ".env.example", "README.md"]


def log(msg: str) -> None:
    """Print `msg` with an HH:MM:SS prefix, flushed immediately."""
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def rls_sql() -> str:
    """The SQL inside infra/postgres/init/02_rls.sh (a psql heredoc), runnable from Python."""
    script = (REPO_ROOT / "infra/postgres/init/02_rls.sh").read_text(encoding="utf-8")
    body = re.search(r"<<SQL\n(.*)\nSQL\s*$", script, re.S)
    if not body:
        raise SystemExit("02_rls.sh: heredoc not found")
    text = body.group(1).replace("\\$\\$", "$$").replace(':"app_user"', ":app_user")
    leftovers = sorted(set(re.findall(r":['\"]\w+['\"]", text)))  # psql variables the loader would not fill
    if leftovers or "\\$" in text:
        raise SystemExit(f"02_rls.sh changed shape (psql variables {leftovers} or escapes left): update this builder")
    return text + "\n"


def write_sql() -> None:
    """Stage sql/: the schema, the RLS SQL extracted from 02_rls.sh and all migrations concatenated."""
    target = STAGE / "sql"
    target.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "infra/postgres/init/01_schema.sql", target / "01_schema.sql")
    (target / "02_rls.sql").write_text(rls_sql(), encoding="utf-8", newline="\n")
    migrations = sorted((REPO_ROOT / "infra/postgres/migrations").glob("*.sql"))
    (target / "migrations.sql").write_text(
        "-- Idempotent migrations for databases created before them (all use IF NOT EXISTS).\n\n"
        + "\n".join(m.read_text(encoding="utf-8") for m in migrations), encoding="utf-8", newline="\n")
    log(f"sql: 01_schema.sql, 02_rls.sql, migrations.sql ({len(migrations)} migration(s))")


def export_data(conn: psycopg.Connection) -> dict:
    """COPY each table in TABLES to data/<table>.csv; returns per-table file, rows, columns, SHA-256, serial."""
    target = STAGE / "data"
    target.mkdir(parents=True)
    tables = {}
    with conn.cursor() as cur:
        for table in TABLES:
            cur.execute("""SELECT column_name, column_default FROM information_schema.columns
                           WHERE table_schema = 'public' AND table_name = %s ORDER BY ordinal_position""", (table,))
            cols = cur.fetchall()
            if not cols:
                raise SystemExit(f"table {table} not found: is this the NiceBank database?")
            names = [c[0] for c in cols]
            serial = any(c[0] == "id" and (c[1] or "").startswith("nextval(") for c in cols)
            path = target / f"{table}.csv"
            order = "id" if "id" in names else names[0]
            query = sql.SQL("COPY (SELECT {} FROM {} ORDER BY {}) TO STDOUT WITH (FORMAT csv, HEADER true)").format(
                sql.SQL(", ").join(sql.Identifier(n) for n in names), sql.Identifier(table), sql.Identifier(order))
            started, digest = time.monotonic(), hashlib.sha256()
            with path.open("wb") as f, cur.copy(query) as copy:
                for block in copy:
                    f.write(block)
                    digest.update(block)
            cur.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table)))
            rows = cur.fetchone()[0]
            tables[table] = {"file": path.name, "rows": rows, "columns": names, "sha256": digest.hexdigest(),
                             "serial": serial}
            log(f"data: {table:<18} {rows:>10,} rows  {path.stat().st_size / 1e6:>8.1f} MB  ({time.monotonic() - started:.1f} s)")
    return tables


def main() -> None:
    """Stage the loader, SQL, data and Keycloak files, write the manifest and zip them into `--out`."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=Path.home() / "Downloads", help="folder for the zip")
    args = parser.parse_args()

    if STAGE.parent.exists():
        shutil.rmtree(STAGE.parent)
    STAGE.mkdir(parents=True)
    for name in LOADER_FILES:
        shutil.copy2(REPO_ROOT / "deploy/dbload" / name, STAGE / name)
    write_sql()
    kc = STAGE / "keycloak"
    kc.mkdir()
    shutil.copy2(REPO_ROOT / "infra/keycloak/latam-bank-realm.json", kc / "latam-bank-realm.json")
    shutil.copy2(REPO_ROOT / "etl/seeds/demo_customers.csv", kc / "demo_customers.csv")

    with psycopg.connect(PG_DSN) as conn:
        conn.read_only = True
        source = f"{conn.info.dbname}@{conn.info.host}:{conn.info.port}"
        log(f"exporting from {source}")
        tables = export_data(conn)
    manifest = {"built_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "source": source, "key_version": KEY_VERSION,
                "tables": tables}
    (STAGE / "data" / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    args.out.mkdir(parents=True, exist_ok=True)
    zip_path = args.out / f"nicebank-db-bundle-{datetime.now():%Y%m%d-%H%M}.zip"
    log(f"compressing into {zip_path}")
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as z:
        for path in sorted(STAGE.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(STAGE.parent).as_posix())
    total = sum(t["rows"] for t in tables.values())
    log(f"done: {zip_path.name} ({zip_path.stat().st_size / 1e6:.0f} MB, {total:,} rows in {len(tables)} tables)")


if __name__ == "__main__":
    main()
