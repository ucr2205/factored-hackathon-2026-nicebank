"""Evaluate retrieval over kb_chunks: recall@1/3/5 and MRR for the labeled queries in ml/rag/eval_queries.jsonl.

Dense retrieval: e5 query vector (ml-service /embed, kind=query) ranked by pgvector cosine distance, grouping
chunks by doc_id (a dispute type has one chunk per language). A TF-IDF character n-gram ranker over the same
chunks is reported as a lexical baseline. Results are printed and logged to MLflow (experiment "rag").

Usage (after ml/rag/index.py): poetry run python ml/rag/evaluate.py [--ml-url http://127.0.0.1:8000]
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

import mlflow
import numpy as np
import psycopg
from sklearn.feature_extraction.text import TfidfVectorizer

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "etl"))
from seed_demo import PG_DSN  # noqa: E402

QUERIES = Path(__file__).with_name("eval_queries.jsonl")
KS = (1, 3, 5)


def embed_query(ml_url: str, text: str) -> list[float]:
    body = json.dumps({"texts": [text], "kind": "query"}).encode()
    req = urllib.request.Request(f"{ml_url}/embed", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["vectors"][0]


def ranked_docs(rows: list[tuple[str, float]]) -> list[str]:
    seen, out = set(), []
    for doc, _ in rows:
        if doc not in seen:
            seen.add(doc)
            out.append(doc)
    return out


def score(ranks: list[list[str]], queries: list[dict]) -> dict[str, float]:
    out = {}
    for k in KS:
        out[f"recall_at_{k}"] = float(np.mean([any(e in r[:k] for e in q["expected"]) for r, q in zip(ranks, queries)]))
    rr = []
    for r, q in zip(ranks, queries):
        pos = [r.index(e) + 1 for e in q["expected"] if e in r]
        rr.append(1 / min(pos) if pos else 0.0)
    out["mrr"] = float(np.mean(rr))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ml-url", default="http://127.0.0.1:8000")
    args = ap.parse_args()
    queries = [json.loads(line) for line in QUERIES.read_text(encoding="utf-8").splitlines() if line.strip()]

    with psycopg.connect(PG_DSN) as pg, pg.cursor() as cur:
        cur.execute("SELECT doc_id, text, version FROM kb_chunks WHERE doc_id LIKE 'policy:%' OR doc_id LIKE 'faq:%'")
        chunks = cur.fetchall()
        if not chunks:
            raise SystemExit("kb_chunks is empty: run ml/rag/index.py first")
        dense = []
        for q in queries:
            vec = str(embed_query(args.ml_url, q["query"]))
            cur.execute("SELECT doc_id, embedding <=> %s::vector AS d FROM kb_chunks "
                        "WHERE doc_id LIKE 'policy:%%' OR doc_id LIKE 'faq:%%' ORDER BY d LIMIT 20", (vec,))
            dense.append(ranked_docs(cur.fetchall()))

    docs = [c[0] for c in chunks]
    tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), strip_accents="unicode", sublinear_tf=True)
    m = tfidf.fit_transform([c[1] for c in chunks])
    lexical = []
    for q in queries:
        sims = (m @ tfidf.transform([q["query"]]).T).toarray().ravel()
        lexical.append(ranked_docs([(docs[i], -sims[i]) for i in np.argsort(-sims)]))

    results = {}
    for name, ranks in (("dense_e5", dense), ("lexical_tfidf", lexical)):
        res = {"all": score(ranks, queries)}
        for lang in ("es", "pt"):
            idx = [i for i, q in enumerate(queries) if q["lang"] == lang]
            res[lang] = score([ranks[i] for i in idx], [queries[i] for i in idx])
        res["misses_at_3"] = [{"query": q["query"], "expected": q["expected"], "top3": r[:3]}
                              for r, q in zip(ranks, queries) if not any(e in r[:3] for e in q["expected"])]
        results[name] = res

    mlflow.set_tracking_uri((ROOT / "ml" / "mlruns").as_uri())
    mlflow.set_experiment("rag")
    for name, res in results.items():
        with mlflow.start_run(run_name=name):
            mlflow.log_params({"queries": len(queries), "chunks": len(chunks), "index_version": chunks[0][2]})
            for scope in ("all", "es", "pt"):
                mlflow.log_metrics({f"{scope}_{k}": v for k, v in res[scope].items()})
            mlflow.log_dict({"misses_at_3": res["misses_at_3"]}, "misses_at_3.json")

    print(f"{len(queries)} queries over {len(chunks)} chunks ({chunks[0][2]})")
    for name, res in results.items():
        a = res["all"]
        print(f"{name:<14} R@1 {a['recall_at_1']:.2f}  R@3 {a['recall_at_3']:.2f}  R@5 {a['recall_at_5']:.2f}  MRR {a['mrr']:.2f}"
              f"  | R@3 es {res['es']['recall_at_3']:.2f} pt {res['pt']['recall_at_3']:.2f}")
        for miss in res["misses_at_3"]:
            print(f"   miss: {miss['query']!r} expected {miss['expected']} got {miss['top3']}")


if __name__ == "__main__":
    main()
