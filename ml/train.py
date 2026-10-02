"""Train and compare the dispute-type classifiers (taxonomy C6) and export the model ml-service serves.

Candidates, all evaluated on the same splits of ml/data/build/corpus.jsonl (split by template family) plus the
hand-labeled external dev set ml/data/dev_external.jsonl:
    B0  majority class
    B1  keyword stub (keyword-stub-0, frozen in ml/baselines.py)
    M1  TF-IDF (word 1-2 + char 2-5) + logistic regression
    M2  multilingual-e5-small embeddings + logistic regression

C is chosen on validation; test and dev_external are only reported. The confidence threshold for the served
model is the lowest one whose validation precision (over the messages it does not abstain on) is >= 0.95.
Everything is logged to MLflow (file:ml/mlruns). The chosen model is exported as plain JSON (no pickle) to
ml/service/model/classifier.json so the service image can be built from the repository.

Usage (`make train` runs both steps; needs `poetry install --with ml`):
    poetry run python ml/data/generate_utterances.py
    poetry run python ml/train.py [--serve auto|M2|M3] [--refit]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import mlflow
import numpy as np
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, f1_score
from sklearn.pipeline import FeatureUnion, make_pipeline

sys.path.insert(0, str(Path(__file__).resolve().parent))
from baselines import keyword_classify  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "ml" / "data" / "build"
DEV_EXTERNAL = ROOT / "ml" / "data" / "dev_external.jsonl"
SERVE_DIR = ROOT / "ml" / "service" / "model"
LABELS = ["unrecognized_charge", "duplicate_charge", "wrong_amount", "not_received",
          "atm_cash_not_dispensed", "card_lost_stolen", "other_in_scope", "out_of_scope"]
EMBED_MODEL = "intfloat/multilingual-e5-small"
EMBED_REVISION = "614241f622f53c4eeff9890bdc4f31cfecc418b3"  # pinned commit (HF main on 2026-09-30); the service loads the same one
TARGET_PRECISION = 0.95
PRECISION_MARGIN = 0.02
C_GRID = [0.25, 1.0, 4.0, 16.0, 64.0]


def load_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of dicts, skipping blank lines."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


class E5:
    """multilingual-e5-small with the "query: " prefix, L2-normalized, cached by text hash."""

    def __init__(self) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(EMBED_MODEL, revision=EMBED_REVISION, device="cpu")
        self.cache_path = BUILD / "e5_cache.npz"
        self.cache: dict[str, np.ndarray] = {}
        if self.cache_path.exists():
            data = np.load(self.cache_path)
            self.cache = {k: data[k] for k in data.files}

    def encode(self, texts: list[str]) -> np.ndarray:
        keys = [hashlib.sha256(t.encode()).hexdigest() for t in texts]
        missing = [(k, t) for k, t in zip(keys, texts) if k not in self.cache]
        if missing:
            vecs = self.model.encode(["query: " + t for _, t in missing], batch_size=64, normalize_embeddings=True,
                                     show_progress_bar=False)
            for (k, _), v in zip(missing, vecs):
                self.cache[k] = v.astype(np.float32)
            np.savez(self.cache_path, **self.cache)
        return np.stack([self.cache[k] for k in keys])


def tfidf_pipeline(c: float):
    """Model M1: word (1-2) + char_wb (2-5) TF-IDF into a class-balanced logistic regression with C=`c`."""
    features = FeatureUnion([
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=1, sublinear_tf=True, strip_accents="unicode", lowercase=True)),
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True, strip_accents="unicode", lowercase=True)),
    ])
    return make_pipeline(features, LogisticRegression(C=c, max_iter=3000, class_weight="balanced"))


def metrics(y_true: list[str], y_pred: list[str], langs: list[str]) -> dict[str, float]:
    """Accuracy and macro-F1 over LABELS, overall and per language (`*_es`, `*_pt`) when that language is present."""
    out = {"accuracy": accuracy_score(y_true, y_pred),
           "macro_f1": f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0)}
    for lang in ("es", "pt"):
        idx = [i for i, g in enumerate(langs) if g == lang]
        if idx:
            out[f"macro_f1_{lang}"] = f1_score([y_true[i] for i in idx], [y_pred[i] for i in idx], labels=LABELS,
                                               average="macro", zero_division=0)
            out[f"accuracy_{lang}"] = accuracy_score([y_true[i] for i in idx], [y_pred[i] for i in idx])
    return out


def pick_threshold(y_true: list[str], y_pred: list[str], conf: np.ndarray) -> tuple[float, float, float]:
    """Lowest threshold whose validation precision (over non-abstained messages) is >= target + margin at that
    threshold and at every higher one. The margin keeps the frozen value off the edge, where one message flips the
    result; returns (t, precision, coverage)."""
    correct = np.array([a == b for a, b in zip(y_true, y_pred)])
    best = (1.0, float("nan"), 0.0)
    for t in np.round(np.arange(0.0, 1.0001, 0.01), 2)[::-1]:  # from strict to loose; stop at the first failure
        keep = conf >= t
        if keep.sum() == 0:
            continue
        precision = correct[keep].mean()
        if precision < TARGET_PRECISION + PRECISION_MARGIN:
            break
        best = (float(t), float(precision), float(keep.mean()))
    return best


def coverage_at(y_true: list[str], y_pred: list[str], conf: np.ndarray, t: float) -> tuple[float, float]:
    """Return (precision over non-abstained messages, coverage) at threshold `t`; NaN precision if none kept."""
    correct = np.array([a == b for a, b in zip(y_true, y_pred)])
    keep = conf >= t
    return (float(correct[keep].mean()) if keep.any() else float("nan")), float(keep.mean())


def main() -> None:
    """Evaluate B0, B1, M1, M2 and M3, log each run to MLflow and export the `--serve` model to classifier.json."""
    ap = argparse.ArgumentParser()
    ap.add_argument("--serve", default="auto", help="model to export for ml-service: M2, M3 or auto (best val macro-F1)")
    ap.add_argument("--refit", action="store_true",
                    help="after choosing C and the threshold on validation, refit the exported model on train+val+test "
                         "(more phrasing families; the corpus metrics above stay those of the train-only model)")
    args = ap.parse_args()

    corpus = load_jsonl(BUILD / "corpus.jsonl")
    manifest = json.loads((BUILD / "manifest.json").read_text(encoding="utf-8"))
    dev = load_jsonl(DEV_EXTERNAL)
    sets = {s: [r for r in corpus if r["split"] == s] for s in ("train", "val", "test")}
    sets["dev_external"] = dev
    X = {s: [r["text"] for r in rows] for s, rows in sets.items()}
    Y = {s: [r["label"] for r in rows] for s, rows in sets.items()}
    G = {s: [r["lang"] for r in rows] for s, rows in sets.items()}

    mlflow.set_tracking_uri((ROOT / "ml" / "mlruns").as_uri())
    mlflow.set_experiment("dispute-classifier")
    common = {"corpus_sha256": manifest["corpus_sha256"], "corpus_rows": manifest["rows"],
              "templates_version": manifest["templates_version"], "split": "by_template_family",
              "python": platform.python_version()}
    results: dict[str, dict] = {}

    def log_run(name: str, params: dict, preds: dict[str, list[str]], conf: dict[str, np.ndarray] | None,
                latency_ms: float | None) -> dict:
        with mlflow.start_run(run_name=name):
            mlflow.set_tag("model", name)
            mlflow.log_params({**common, **params})
            row: dict = {}
            for s in ("val", "test", "dev_external"):
                m = metrics(Y[s], preds[s], G[s])
                mlflow.log_metrics({f"{s}_{k}": v for k, v in m.items()})
                row[s] = m
            if latency_ms is not None:
                mlflow.log_metric("latency_ms_per_message", latency_ms)
            if conf is not None:
                t, p, cov = pick_threshold(Y["val"], preds["val"], conf["val"])
                tp, tcov = coverage_at(Y["test"], preds["test"], conf["test"], t)
                dp, dcov = coverage_at(Y["dev_external"], preds["dev_external"], conf["dev_external"], t)
                mlflow.log_metrics({"threshold": t, "val_precision_at_t": p, "val_coverage_at_t": cov,
                                    "test_precision_at_t": tp, "test_coverage_at_t": tcov,
                                    "dev_external_precision_at_t": dp, "dev_external_coverage_at_t": dcov})
                row["threshold"] = {"t": t, "val": (p, cov), "test": (tp, tcov), "dev_external": (dp, dcov)}
            report = classification_report(Y["test"], preds["test"], labels=LABELS, zero_division=0, output_dict=True)
            cm = confusion_matrix(Y["test"], preds["test"], labels=LABELS).tolist()
            mlflow.log_dict({"labels": LABELS, "test_confusion_matrix": cm, "test_report": report}, "test_report.json")
            errors = [{"text": x, "label": y, "pred": p} for x, y, p in zip(X["dev_external"], Y["dev_external"],
                                                                          preds["dev_external"]) if y != p]
            mlflow.log_dict({"dev_external_errors": errors}, "dev_external_errors.json")
        row["latency_ms"] = latency_ms
        results[name] = row
        return row

    # B0 — majority class.
    b0 = DummyClassifier(strategy="most_frequent").fit(X["train"], Y["train"])
    log_run("B0-majority", {"strategy": "most_frequent"}, {s: list(b0.predict(X[s])) for s in X}, None, None)

    # B1 — keyword stub.
    b1 = {s: [keyword_classify(t) for t in X[s]] for s in X}
    log_run("B1-keywords", {"model_version": "keyword-stub-0"}, {s: [p for p, _ in b1[s]] for s in X},
            {s: np.array([c for _, c in b1[s]]) for s in X}, None)

    # M1 — TF-IDF + LogReg, C chosen on validation macro-F1.
    best_c, best_f1 = None, -1.0
    for c in C_GRID:
        f1 = f1_score(Y["val"], tfidf_pipeline(c).fit(X["train"], Y["train"]).predict(X["val"]), average="macro")
        if f1 > best_f1:
            best_c, best_f1 = c, f1
    m1 = tfidf_pipeline(best_c).fit(X["train"], Y["train"])
    t0 = time.perf_counter()
    for text in X["dev_external"]:
        m1.predict_proba([text])
    m1_lat = (time.perf_counter() - t0) * 1000 / len(X["dev_external"])
    m1_proba = {s: m1.predict_proba(X[s]) for s in X}
    m1_pred = {s: list(m1.classes_[p.argmax(1)]) for s, p in m1_proba.items()}
    log_run("M1-tfidf-logreg", {"C": best_c, "features": "word1-2+char_wb2-5", "class_weight": "balanced"},
            m1_pred, {s: p.max(1) for s, p in m1_proba.items()}, m1_lat)

    # M2 — e5 embeddings + LogReg, C chosen on validation macro-F1.
    e5 = E5()
    E = {s: e5.encode(X[s]) for s in X}
    best_c2, best_f12 = None, -1.0
    for c in C_GRID:
        clf = LogisticRegression(C=c, max_iter=3000, class_weight="balanced").fit(E["train"], Y["train"])
        f1 = f1_score(Y["val"], clf.predict(E["val"]), average="macro")
        if f1 > best_f12:
            best_c2, best_f12 = c, f1
    m2 = LogisticRegression(C=best_c2, max_iter=3000, class_weight="balanced").fit(E["train"], Y["train"])
    t0 = time.perf_counter()
    for text in X["dev_external"]:
        m2.predict_proba(e5.model.encode(["query: " + text], normalize_embeddings=True, show_progress_bar=False))
    m2_lat = (time.perf_counter() - t0) * 1000 / len(X["dev_external"])
    m2_proba = {s: m2.predict_proba(E[s]) for s in X}
    m2_pred = {s: list(m2.classes_[p.argmax(1)]) for s, p in m2_proba.items()}
    log_run("M2-e5-logreg", {"C": best_c2, "embed_model": EMBED_MODEL, "embed_revision": EMBED_REVISION,
                             "class_weight": "balanced"},
            m2_pred, {s: p.max(1) for s, p in m2_proba.items()}, m2_lat)

    # M3 — average of the M1 and M2 probabilities (same class order). No extra training.
    assert list(m1.classes_) == list(m2.classes_)
    m3_proba = {s: (m1_proba[s] + m2_proba[s]) / 2 for s in X}
    m3_pred = {s: list(m1.classes_[p.argmax(1)]) for s, p in m3_proba.items()}
    log_run("M3-avg-tfidf-e5", {"combination": "mean_proba(M1, M2)", "C_tfidf": best_c, "C_e5": best_c2,
                                "embed_model": EMBED_MODEL, "embed_revision": EMBED_REVISION},
            m3_pred, {s: p.max(1) for s, p in m3_proba.items()}, m1_lat + m2_lat)

    # Export the served model as JSON (no pickle). The service always needs e5 (it also serves /embed), so the
    # exportable choices are M2 alone or M3 (M2 + TF-IDF).
    serve = args.serve
    if serve == "auto":
        serve = "M3" if results["M3-avg-tfidf-e5"]["val"]["macro_f1"] >= results["M2-e5-logreg"]["val"]["macro_f1"] else "M2"
    if serve not in ("M2", "M3"):
        raise SystemExit("ml-service can serve M2 or M3 (it needs e5 for /embed); re-run with --serve M2 or M3.")
    run_name = {"M2": "M2-e5-logreg", "M3": "M3-avg-tfidf-e5"}[serve]
    th = results[run_name]["threshold"]
    rows_fit = len(X["train"])
    if args.refit:
        fit_x = X["train"] + X["val"] + X["test"]
        fit_y = Y["train"] + Y["val"] + Y["test"]
        m1 = tfidf_pipeline(best_c).fit(fit_x, fit_y)
        m2 = LogisticRegression(C=best_c2, max_iter=3000, class_weight="balanced").fit(
            np.vstack([E["train"], E["val"], E["test"]]), fit_y)
        assert list(m1.classes_) == list(m2.classes_)
        rows_fit = len(fit_x)
    SERVE_DIR.mkdir(parents=True, exist_ok=True)
    version = f"{'e5-logreg' if serve == 'M2' else 'e5-tfidf-avg'}-{manifest['corpus_sha256'][:8]}"
    if args.refit:
        version += "-all"
    export = {
        "model_version": version, "combination": "e5" if serve == "M2" else "mean(e5, tfidf)",
        "classes": list(m2.classes_), "abstain_below": th["t"],
        "e5": {"model": EMBED_MODEL, "revision": EMBED_REVISION, "query_prefix": "query: ",
               "coef": m2.coef_.round(6).tolist(), "intercept": m2.intercept_.round(6).tolist()},
        "trained_on": {"corpus_sha256": manifest["corpus_sha256"], "templates_version": manifest["templates_version"],
                       "rows_train": rows_fit, "refit_on_all_splits": args.refit, "C_e5": best_c2, "C_tfidf": best_c if serve == "M3" else None},
        "validation": {"macro_f1": results[run_name]["val"]["macro_f1"], "precision_at_threshold": th["val"][0],
                       "coverage_at_threshold": th["val"][1], "target_precision": TARGET_PRECISION,
                       "precision_margin": PRECISION_MARGIN},
    }
    if serve == "M3":
        union, logreg = m1.steps[0][1], m1.steps[1][1]
        export["tfidf"] = {
            "vectorizers": [{"name": name, "params": {k: v for k, v in vec.get_params().items()
                                                      if k in ("analyzer", "ngram_range", "sublinear_tf", "strip_accents",
                                                               "lowercase", "norm", "use_idf", "smooth_idf")},
                             "vocabulary": {t: int(i) for t, i in vec.vocabulary_.items()},
                             "idf": vec.idf_.round(6).tolist()} for name, vec in union.transformer_list],
            "coef": logreg.coef_.round(5).tolist(), "intercept": logreg.intercept_.round(6).tolist(),
        }
    (SERVE_DIR / "classifier.json").write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
    # Golden predictions for the service parity test: team-authored texts only (never transcript text).
    golden_texts = X["dev_external"] + [r["text"] for r in sets["test"] if r["source"].startswith("team")][:40:2]
    served = m3_proba if serve == "M3" else m2_proba
    golden_proba = {} if args.refit else {**dict(zip(X["dev_external"], served["dev_external"]))}
    extra = [t for t in golden_texts if t not in golden_proba]
    if extra:
        e_extra = e5.encode(extra)
        p_extra = m2.predict_proba(e_extra) if serve == "M2" else (m2.predict_proba(e_extra) + m1.predict_proba(extra)) / 2
        golden_proba.update(zip(extra, p_extra))
    golden = [{"text": t, "label": str(m2.classes_[golden_proba[t].argmax()]), "confidence": round(float(golden_proba[t].max()), 4)}
              for t in golden_texts]
    (SERVE_DIR / "golden.json").write_text(json.dumps(golden, ensure_ascii=False, indent=1), encoding="utf-8")

    summary = {k: {kk: vv for kk, vv in v.items()} for k, v in results.items()}
    (BUILD / "comparison.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=float), encoding="utf-8")
    print(f"\n{'model':<18}{'val F1':>8}{'test F1':>9}{'test es':>9}{'test pt':>9}{'dev F1':>8}{'dev acc':>9}{'ms/msg':>8}")
    for name, r in results.items():
        lat = f"{r['latency_ms']:.1f}" if r["latency_ms"] is not None else "-"
        print(f"{name:<18}{r['val']['macro_f1']:>8.3f}{r['test']['macro_f1']:>9.3f}{r['test'].get('macro_f1_es', 0):>9.3f}"
              f"{r['test'].get('macro_f1_pt', 0):>9.3f}{r['dev_external']['macro_f1']:>8.3f}{r['dev_external']['accuracy']:>9.3f}{lat:>8}")
        if "threshold" in r:
            t = r["threshold"]
            print(f"{'':<18}threshold {t['t']:.2f}: val prec/cov {t['val'][0]:.3f}/{t['val'][1]:.3f} | "
                  f"test {t['test'][0]:.3f}/{t['test'][1]:.3f} | dev {t['dev_external'][0]:.3f}/{t['dev_external'][1]:.3f}")
    print(f"\nexported {serve} as {version} (abstain_below={th['t']:.2f}) -> {SERVE_DIR / 'classifier.json'}")


if __name__ == "__main__":
    main()
