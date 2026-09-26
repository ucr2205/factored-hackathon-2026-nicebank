"""ml-service — Phase 0 stub.

Implements the C2 contract with a keyword baseline so the backend can integrate from day 1.
Person 3 replaces the classifier with the trained model (embeddings + logistic regression) and
implements real multilingual embeddings in /embed.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Literal

from fastapi import FastAPI
from prometheus_client import Counter, make_asgi_app
from pydantic import BaseModel, Field

MODEL_VERSION = "keyword-stub-0"
EMBED_DIM = 384
ABSTAIN_BELOW = 0.5

# Placeholder taxonomy (C6 is frozen on D3). Keywords cover Spanish and Portuguese.
KEYWORDS: dict[str, list[str]] = {
    "unrecognized_charge": ["no reconozco", "no reconocido", "nao reconheco", "nao reconhecida",
                            "no hice", "nao fiz", "fraude", "no autorice", "nao autorizei"],
    "duplicate_charge": ["dos veces", "doble", "duplicado", "duas vezes", "cobrado dos", "cobraram duas"],
    "wrong_amount": ["monto incorrecto", "cobraron de mas", "valor errado", "cobraram a mais"],
    "not_received": ["no llego", "no recibi", "nao chegou", "nao recebi"],
    "atm_cash_not_dispensed": ["cajero", "no entrego", "caixa eletronico", "nao liberou"],
    "out_of_scope": ["prestamo", "credito", "emprestimo", "inversion", "investimento"],
}

app = FastAPI(title="ml-service", version=MODEL_VERSION)
app.mount("/metrics", make_asgi_app())

CLASSIFY_TOTAL = Counter("ml_classify_total", "Classification requests", ["label", "abstain"])


class ClassifyRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    lang: Literal["es", "pt"] | None = None


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


def normalize(text: str) -> str:
    stripped = unicodedata.normalize("NFKD", text.lower())
    return re.sub(r"\s+", " ", "".join(c for c in stripped if not unicodedata.combining(c)))


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "model_version": MODEL_VERSION}


@app.post("/classify", response_model=ClassifyResponse)
def classify(req: ClassifyRequest) -> ClassifyResponse:
    text = normalize(req.text)
    hits = {label: sum(kw in text for kw in kws) for label, kws in KEYWORDS.items()}
    best, score = max(hits.items(), key=lambda kv: kv[1])
    if score == 0:
        best, confidence = "other_in_scope", 0.0
    else:
        confidence = min(0.5 + 0.2 * score, 0.9)
    abstain = confidence < ABSTAIN_BELOW
    CLASSIFY_TOTAL.labels(label=best, abstain=str(abstain).lower()).inc()
    return ClassifyResponse(label=best, confidence=confidence, abstain=abstain, model_version=MODEL_VERSION)


@app.post("/embed", response_model=EmbedResponse)
def embed(req: EmbedRequest) -> EmbedResponse:
    # Deterministic pseudo-embeddings so integration tests are stable. NOT semantically meaningful.
    vectors = []
    for text in req.texts:
        digest = hashlib.sha256(f"{req.kind}:{normalize(text)}".encode()).digest()
        vectors.append([((digest[i % len(digest)] / 255.0) * 2 - 1) for i in range(EMBED_DIM)])
    return EmbedResponse(vectors=vectors, model=MODEL_VERSION)
