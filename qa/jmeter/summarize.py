"""Summarize a JMeter .jtl (CSV) per sampler: count, errors, p50/p95/p99, throughput.

Usage: poetry run python qa/jmeter/summarize.py qa/jmeter/results/load-fake.jtl [more.jtl ...]
"""

from __future__ import annotations

import csv
import math
import sys
from collections import defaultdict


def pct(values: list[int], p: float) -> int:
    s = sorted(values)
    return s[min(len(s) - 1, max(0, math.ceil(p / 100 * len(s)) - 1))] if s else 0


def main() -> None:
    for path in sys.argv[1:]:
        rows = list(csv.DictReader(open(path, encoding="utf-8")))
        by = defaultdict(list)
        for r in rows:
            by[r["label"]].append(r)
        span_s = (max(int(r["timeStamp"]) for r in rows) - min(int(r["timeStamp"]) for r in rows)) / 1000 or 1
        print(f"\n{path}: {len(rows)} samples in {span_s:.0f} s ({len(rows) / span_s:.1f}/s)")
        print(f"| Sampler | n | Errors | p50 | p95 | p99 | Throughput |\n|---|---|---|---|---|---|---|")
        for label in sorted(by):
            rs = by[label]
            el = [int(r["elapsed"]) for r in rs]
            err = sum(r["success"] != "true" for r in rs)
            print(f"| {label} | {len(rs)} | {err} ({100 * err / len(rs):.1f}%) | {pct(el, 50)} ms | {pct(el, 95)} ms | "
                  f"{pct(el, 99)} ms | {len(rs) / span_s:.1f}/s |")


if __name__ == "__main__":
    main()
