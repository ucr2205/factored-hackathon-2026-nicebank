"""Create the local .env from .env.example (if missing) and generate a PII_KEY if it has none.

The PII_KEY encrypts customer names in customer_identity. It is a local development key: each developer has
their own, it never leaves .env (git-ignored), and `make seed` re-encrypts the demo data with it.
Secrets such as DEEPSEEK_API_KEY are never written by this script; paste them into .env yourself.

Usage: poetry run python scripts/make_env.py
"""

from __future__ import annotations

import base64
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV, EXAMPLE = ROOT / ".env", ROOT / ".env.example"


def main() -> None:
    if not ENV.exists():
        shutil.copyfile(EXAMPLE, ENV)
        print("Created .env from .env.example")
    lines = ENV.read_text(encoding="utf-8").splitlines()
    if any(line.startswith("PII_KEY=") and line.split("=", 1)[1].strip() for line in lines):
        print("PII_KEY already set; nothing to do")
        return
    key = base64.b64encode(os.urandom(32)).decode()
    lines = [line for line in lines if not line.startswith("PII_KEY=")] + [f"PII_KEY={key}"]
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    print("Generated PII_KEY in .env (then run: docker compose up -d backend && make seed)")


if __name__ == "__main__":
    main()
