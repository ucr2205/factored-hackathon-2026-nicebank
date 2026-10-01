"""ml-service — trained dispute-type classifier and multilingual embeddings (contract C2).

/classify averages two logistic regressions trained by ml/train.py (model M3 in MLflow):
    - over multilingual-e5-small sentence embeddings (the same model /embed serves), and
    - over TF-IDF word (1-2) + character (2-5) n-grams.
Both are loaded from model/classifier.json (plain JSON, no pickle). The e5 weights are pinned by revision and
baked into the image at build time, so the service never downloads anything at runtime.

Abstention: the service abstains below the confidence threshold frozen at training time (validation precision
>= 0.95 plus a 0.02 margin). An abstained "out_of_scope" is returned as "other_in_scope": the backend ends the
conversation on out_of_scope without looking at `abstain`, and a low-confidence guess must lead to a question,
not to a refusal.
"""

from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import Literal

import numpy as np
import scipy.sparse as sp
from fastapi import FastAPI
from prometheus_client import Counter, Histogram, make_asgi_app
from pydantic import BaseModel, Field
from sklearn.feature_extraction.text import TfidfVectorizer

MODEL_FILE = Path(os.getenv("MODEL_FILE", Path(__file__).parent / "model" / "classifier.json"))
EMBED_DIM = 384
PASSAGE_PREFIX = "passage: "


def _softmax(z: np.ndarray) -> np.ndarray:
    z = z - z.max(axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


class Model:
    """Everything /classify and /embed need, loaded once at startup."""

    def __init__(self, path: Path) -> None:
        import torch
        from sentence_transformers import SentenceTransformer

        torch.set_num_threads(int(os.getenv("TORCH_THREADS", "2")))
        cfg = json.loads(path.read_text(encoding="utf-8"))
        self.version: str = cfg["model_version"]
        self.classes: list[str] = cfg["classes"]
        self.abstain_below: float = cfg["abstain_below"]
        e5 = cfg["e5"]
        self.query_prefix: str = e5["query_prefix"]
        self.embed_name = f"{e5['model']}@{e5['revision'][:7]}"
        self.encoder = SentenceTransformer(e5["model"], revision=e5["revision"], device="cpu")
        self.e5_coef = np.asarray(e5["coef"], dtype=np.float32)
        self.e5_intercept = np.asarray(e5["intercept"], dtype=np.float32)
        self.tfidf: list[TfidfVectorizer] = []
        if "tfidf" in cfg:
            for v in cfg["tfidf"]["vectorizers"]:
                params = dict(v["params"])
                params["ngram_range"] = tuple(params["ngram_range"])
                vec = TfidfVectorizer(vocabulary=v["vocabulary"], **params)
                vec.idf_ = np.asarray(v["idf"])
                self.tfidf.append(vec)
            self.tfidf_coef = np.asarray(cfg["tfidf"]["coef"], dtype=np.float32)
            self.tfidf_intercept = np.asarray(cfg["tfidf"]["intercept"], dtype=np.float32)

    def encode(self, texts: list[str], prefix: str) -> np.ndarray:
        return self.encoder.encode([prefix + t for t in texts], normalize_embeddings=True, show_progress_bar=False,
                                   convert_to_numpy=True)

    def proba(self, text: str) -> np.ndarray:
        p = _softmax(self.encode([text], self.query_prefix)[0] @ self.e5_coef.T + self.e5_intercept)
        if self.tfidf:
            features = sp.hstack([vec.transform([text]) for vec in self.tfidf]).tocsr()
            p = (p + _softmax(np.asarray(features @ self.tfidf_coef.T).ravel() + self.tfidf_intercept)) / 2
        return p


MODEL = Model(MODEL_FILE)


def _keep_warm(every_s: float) -> None:
    """After a few idle minutes the first request took ~1.4 s instead of ~20 ms (weights paged out, cold thread pool),
    long enough to time out the backend's call. One tiny inference at startup and then every `every_s` seconds keeps
    the model resident; it costs a few ms of CPU per interval."""
    MODEL.proba("warm up")
    while every_s > 0:
        time.sleep(every_s)
        try:
            MODEL.proba("warm up")
        except Exception:  # noqa: BLE001  (a failed warm-up must never kill the service)
            pass


KEEP_WARM_SECONDS = float(os.getenv("KEEP_WARM_SECONDS", "30"))
threading.Thread(target=_keep_warm, args=(KEEP_WARM_SECONDS,), daemon=True, name="keep-warm").start()

app = FastAPI(title="ml-service", version=MODEL.version)
app.mount("/metrics", make_asgi_app())

CLASSIFY_TOTAL = Counter("ml_classify_total", "Classification requests", ["label", "abstain"])
CLASSIFY_SECONDS = Histogram("ml_classify_seconds", "Classification latency",
                             buckets=(0.005, 0.01, 0.02, 0.05, 0.1, 0.25, 0.5, 1.0))


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    lang: Literal["es", "pt"] | None = None  # accepted for C2 compatibility; the model is multilingual


class ClassifyResponse(BaseModel):
    label: str
    confidence: float
    abstain: bool
    model_version: str


class EmbedRequest(BaseModel):
    texts: list[str] = Field(min_length=1, max_length=64)
    kind: Literal["query", "passage"] = "query"


class EmbedResponse(BaseModel):
    vectors: list[list[float]]
    model: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL.version}


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    start = time.perf_counter()
    p = MODEL.proba(req.text)
    best = int(p.argmax())
    label, confidence = MODEL.classes[best], float(p[best])
    abstain = confidence < MODEL.abstain_below
    if abstain and label == "out_of_scope":
        label = "other_in_scope"
    CLASSIFY_SECONDS.observe(time.perf_counter() - start)
    CLASSIFY_TOTAL.labels(label=label, abstain=str(abstain).lower()).inc()
    return ClassifyResponse(label=label, confidence=round(confidence, 4), abstain=abstain, model_version=MODEL.version)


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    prefix = MODEL.query_prefix if req.kind == "query" else PASSAGE_PREFIX
    vectors = MODEL.encode(req.texts, prefix)
    return EmbedResponse(vectors=[[round(float(x), 6) for x in v] for v in vectors], model=MODEL.embed_name)
