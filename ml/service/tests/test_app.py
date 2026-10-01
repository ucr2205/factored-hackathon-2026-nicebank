"""Tests for ml-service: contract C2, parity with training, known stub failures and latency.

Run from the repository root (needs `poetry install --with ml`):
    poetry run pytest ml/service/tests -q
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

SERVICE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVICE))

import app as service  # noqa: E402

C6 = {"unrecognized_charge", "duplicate_charge", "wrong_amount", "not_received", "atm_cash_not_dispensed",
      "card_lost_stolen", "other_in_scope", "out_of_scope"}
GOLDEN = json.loads((SERVICE / "model" / "golden.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(service.app)


def classify(client: TestClient, text: str, lang: str | None = "es") -> dict:
    body = {"text": text} if lang is None else {"text": text, "lang": lang}
    r = client.post("/classify", json=body)
    assert r.status_code == 200, r.text
    return r.json()


# --- Contract C2 ---------------------------------------------------------------------------------------------

def test_health_reports_model_version(client: TestClient) -> None:
    r = client.get("/health").json()
    assert r == {"status": "ok", "model_version": service.MODEL.version}
    assert not r["model_version"].startswith("keyword-stub")


def test_classify_response_shape(client: TestClient) -> None:
    out = classify(client, "No reconozco un cobro de 385,71 de hoy")
    assert set(out) == {"label", "confidence", "abstain", "model_version"}
    assert out["label"] in C6
    assert isinstance(out["confidence"], float) and 0.0 <= out["confidence"] <= 1.0
    assert isinstance(out["abstain"], bool)
    assert out["model_version"] == service.MODEL.version


def test_lang_is_optional(client: TestClient) -> None:
    assert classify(client, "Me robaron la tarjeta", lang=None)["label"] == "card_lost_stolen"


@pytest.mark.parametrize("body", [{"text": ""}, {"text": "x" * 4001}, {"text": "hola", "lang": "en"}, {}])
def test_classify_rejects_invalid_input(client: TestClient, body: dict) -> None:
    assert client.post("/classify", json=body).status_code == 422


def test_embed_shape_and_normalization(client: TestClient) -> None:
    r = client.post("/embed", json={"texts": ["no reconozco un cargo", "não reconheço uma cobrança"], "kind": "query"})
    assert r.status_code == 200
    out = r.json()
    assert out["model"].startswith("intfloat/multilingual-e5-small@")
    vectors = np.array(out["vectors"])
    assert vectors.shape == (2, service.EMBED_DIM)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-3)


def test_embed_is_semantic_across_languages(client: TestClient) -> None:
    texts = ["no reconozco un cargo en mi tarjeta", "não reconheço uma cobrança no meu cartão", "quiero invertir en fondos"]
    v = np.array(client.post("/embed", json={"texts": texts}).json()["vectors"])
    assert v[0] @ v[1] > v[0] @ v[2]


def test_embed_query_and_passage_differ(client: TestClient) -> None:
    q = client.post("/embed", json={"texts": ["cargo duplicado"], "kind": "query"}).json()["vectors"][0]
    p = client.post("/embed", json={"texts": ["cargo duplicado"], "kind": "passage"}).json()["vectors"][0]
    assert q != p


def test_embed_rejects_too_many_texts(client: TestClient) -> None:
    assert client.post("/embed", json={"texts": ["a"] * 65}).status_code == 422


# --- Parity with the training run (ml/train.py wrote model/golden.json) --------------------------------------

@pytest.mark.parametrize("case", GOLDEN, ids=[c["text"][:40] for c in GOLDEN])
def test_matches_training_predictions(case: dict) -> None:
    p = service.MODEL.proba(case["text"])
    assert service.MODEL.classes[int(p.argmax())] == case["label"]
    assert abs(float(p.max()) - case["confidence"]) < 2e-3


# --- Behavior the keyword stub got wrong ---------------------------------------------------------------------

def test_credit_card_mention_is_not_out_of_scope(client: TestClient) -> None:
    out = classify(client, "tengo un cargo en mi tarjeta de crédito que no reconozco")
    assert out["label"] == "unrecognized_charge" and not out["abstain"]


def test_undue_charge_is_wrong_amount(client: TestClient) -> None:
    out = classify(client, "me hicieron un cobro indebido de 50 dólares")
    assert out["label"] == "wrong_amount" and not out["abstain"]


@pytest.mark.parametrize("reply", ["fue la segunda", "sí, ese", "o primeiro", "correcto"])
def test_follow_up_replies_never_set_a_dispute_type(client: TestClient, reply: str) -> None:
    out = classify(client, reply)
    assert out["abstain"] or out["label"] == "other_in_scope", out


def test_loan_request_is_out_of_scope(client: TestClient) -> None:
    out = classify(client, "Quero um empréstimo", lang="pt")
    assert out["label"] == "out_of_scope" and not out["abstain"]


def test_abstained_out_of_scope_becomes_other_in_scope(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(service.MODEL, "abstain_below", 1.01)  # force abstention
    out = classify(client, "Quero um empréstimo", lang="pt")
    assert out == {**out, "label": "other_in_scope", "abstain": True}


# --- Latency (contract target: p95 < 100 ms on CPU) ----------------------------------------------------------

def test_p95_latency_under_100ms(client: TestClient) -> None:
    texts = [c["text"] for c in GOLDEN] * 3
    classify(client, texts[0])  # warm-up
    times = []
    for text in texts:
        start = time.perf_counter()
        classify(client, text)
        times.append((time.perf_counter() - start) * 1000)
    p95 = statistics.quantiles(times, n=20)[18]
    assert p95 < 100, f"p95={p95:.1f} ms"
