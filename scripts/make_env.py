"""Create the local .env from .env.example (if missing) and generate the local secrets it lacks.

- PII_KEY encrypts customer names in customer_identity. It is a local development key: each developer has
  their own, it never leaves .env (git-ignored), and `make seed` re-encrypts the demo data with it.
- TOOLS_PASSWORD protects Jaeger, Prometheus and Mailpit behind the gateway (/jaeger, /prometheus, /mail).
  The gateway only gets its bcrypt hash (TOOLS_PASSWORD_HASH, made with Caddy's own hasher through Docker);
  the readable password stays in .env for the team. `--rotate-tools-password` replaces it.
Secrets such as DEEPSEEK_API_KEY are never written by this script; paste them into .env yourself.

Usage: poetry run python scripts/make_env.py [--rotate-tools-password]
"""

from __future__ import annotations

import base64
import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV, EXAMPLE = ROOT / ".env", ROOT / ".env.example"
CADDY_IMAGE = "caddy:2.9-alpine"  # same image as the gateway, so the hash format always matches


def has_value(lines: list[str], key: str) -> bool:
    return any(line.startswith(f"{key}=") and line.split("=", 1)[1].strip().strip("'\"") for line in lines)


def set_values(lines: list[str], values: dict[str, str]) -> list[str]:
    return [line for line in lines if line.split("=", 1)[0] not in values] + [f"{k}={v}" for k, v in values.items()]


def bcrypt_hash(password: str) -> str:
    out = subprocess.run(["docker", "run", "--rm", CADDY_IMAGE, "caddy", "hash-password", "--plaintext", password],
                         check=True, capture_output=True, text=True)
    return out.stdout.strip()


def main() -> None:
    if not ENV.exists():
        shutil.copyfile(EXAMPLE, ENV)
        print("Created .env from .env.example")
    lines = ENV.read_text(encoding="utf-8").splitlines()
    changed = False
    if has_value(lines, "PII_KEY"):
        print("PII_KEY already set")
    else:
        lines = set_values(lines, {"PII_KEY": base64.b64encode(os.urandom(32)).decode()})
        changed = True
        print("Generated PII_KEY in .env (then run: docker compose up -d backend && make seed)")
    if has_value(lines, "TOOLS_PASSWORD_HASH") and "--rotate-tools-password" not in sys.argv:
        print("TOOLS_PASSWORD_HASH already set (use --rotate-tools-password to replace it)")
    else:
        password = secrets.token_urlsafe(15)
        # Single quotes: Docker Compose reads the bcrypt "$" characters literally instead of as variables.
        lines = set_values(lines, {"TOOLS_USER": "equipo", "TOOLS_PASSWORD": password,
                                   "TOOLS_PASSWORD_HASH": f"'{bcrypt_hash(password)}'"})
        changed = True
        print("Generated the tools login (TOOLS_USER and TOOLS_PASSWORD in .env) for /jaeger, /prometheus and "
              "/mail; then run: docker compose up -d gateway")
    if changed:
        ENV.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
