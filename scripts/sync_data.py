"""Sync the organizer dataset from S3 into data/raw/.

Incremental and idempotent: `aws s3 sync` only downloads new or changed objects, so re-running it
picks up late-arriving partitions. Credentials come from the AWS CLI profile, never from this repo.

Usage: python scripts/sync_data.py [--tables call_center_interactions complaints ...]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "data" / "raw"
BUCKET = os.environ.get("DATA_BUCKET", "factored-datathon-2026-s3-157725502942-us-east-2-an")
PROFILE = os.environ.get("AWS_PROFILE", "factored")
REGION = os.environ.get("AWS_REGION", "us-east-2")

PARTITIONED_TABLES = {
    "call_center_interactions", "call_transcripts", "campaign_sends", "complaints",
    "digital_events", "satisfaction_surveys", "transactions",
}


def find_aws_cli() -> str:
    found = shutil.which("aws")
    if found:
        return found
    windows_default = Path(r"C:\Program Files\Amazon\AWSCLIV2\aws.exe")
    if windows_default.exists():
        return str(windows_default)
    sys.exit("AWS CLI not found. Install it (e.g. `winget install Amazon.AWSCLI`) and open a new terminal.")


def sync(aws: str, source: str, dest: Path, extra: list[str]) -> None:
    cmd = [aws, "s3", "sync", source, str(dest), "--profile", PROFILE, "--region", REGION,
           "--only-show-errors", *extra]
    print("->", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tables", nargs="*", help="Only sync these tables (default: everything).")
    args = parser.parse_args()

    aws = find_aws_cli()
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    base = f"s3://{BUCKET}/data/"

    if not args.tables:
        sync(aws, base, RAW_DIR, [])
        return

    for table in args.tables:
        if table in PARTITIONED_TABLES:
            sync(aws, f"{base}{table}/", RAW_DIR / table, [])
        else:
            sync(aws, base, RAW_DIR, ["--exclude", "*", "--include", f"{table}.csv"])


if __name__ == "__main__":
    main()
