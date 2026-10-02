"""Check that no evaluation sentence near-duplicates a classifier training sentence (leakage guard).

Compares every turn in eval/cases/**/*.jsonl with every row of ml/data/build/corpus.jsonl after normalization
(lowercase, no accents, digits -> 0, placeholders removed): exact matches and character 4-gram Jaccard > 0.8 fail.

Usage: poetry run python ml/data/generate_utterances.py && poetry run python eval/check_overlap.py
(`make eval` runs it before eval/run_eval.py --split test.)
Exit code 1 when an overlap is found.
"""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "ml" / "data" / "build" / "corpus.jsonl"
THRESHOLD = 0.8


def norm(text: str) -> str:
    """Lowercase, strip accents, drop [NAME]/[EMAIL]/[NUMBER], digits -> 0, keep only letters, 0 and spaces."""
    t = unicodedata.normalize("NFKD", text.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"\[(name|email|number)\]", " ", t)
    t = re.sub(r"\d", "0", t)
    return re.sub(r"[^a-z0 ]+", " ", re.sub(r"\s+", " ", t)).strip()


def grams(text: str) -> set[str]:
    """Character 4-grams of `text` padded with one space on each side."""
    t = f" {text} "
    return {t[i:i + 4] for i in range(len(t) - 3)}


def main() -> int:
    """Compare every eval turn with the training corpus; print the max Jaccard and overlaps, return 1 if any."""
    if not CORPUS.exists():
        raise SystemExit("ml/data/build/corpus.jsonl missing: run ml/data/generate_utterances.py first")
    train = [norm(json.loads(line)["text"]) for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip()]
    train_grams = [grams(t) for t in train]
    train_set = set(train)
    worst, hits = 0.0, []
    for path in sorted((ROOT / "eval" / "cases").glob("**/*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            case = json.loads(line)
            for turn in case["turns"]:
                n = norm(turn)
                g = grams(n)
                best = max((len(g & tg) / len(g | tg) for tg in train_grams), default=0.0)
                worst = max(worst, best)
                if n in train_set or best > THRESHOLD:
                    hits.append((case["id"], round(best, 3), turn))
    print(f"max 4-gram Jaccard vs training corpus: {worst:.3f} (threshold {THRESHOLD})")
    for h in hits:
        print("  OVERLAP", h)
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
