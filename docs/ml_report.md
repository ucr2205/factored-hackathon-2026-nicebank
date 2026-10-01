# ML report (P3) — classifier, retrieval and LLM

Date: 2026-09-30. Everything below is reproducible with the commands in section 6; runs are logged in MLflow
(`ml/mlruns`, experiments `dispute-classifier` and `rag`). Corpus and labeling protocol: `docs/ml_labels.md`.

## 1. Dispute-type classifier (ml-service `e5-tfidf-avg-1dd695a4`)

Served model M3 = mean of the probabilities of two logistic regressions (multilingual-e5-small embeddings;
TF-IDF word 1-2 + char 2-5). Abstains below 0.48 (validation precision ≥ 0.95 + 0.02 margin).

| Model | Val macro-F1 | Test macro-F1 | Test ES | Test PT | Dev external acc. | ms/msg (CPU) |
|---|---|---|---|---|---|---|
| B0 majority | 0.03 | 0.03 | 0.03 | 0.03 | 0.04 | – |
| B1 keyword stub | 0.44 | 0.52 | 0.49 | 0.53 | 0.96* | – |
| M1 TF-IDF + LogReg | 0.88 | 0.91 | 0.91 | 0.92 | 0.92 | 1 |
| M2 e5 + LogReg | 0.89 | 0.91 | 0.90 | 0.93 | 0.84 | 13 |
| **M3 mean(M1, M2)** | **0.93** | **0.94** | **0.89** | **0.98** | **0.92** | 15 |

\* The dev external set is the 25 messages of `smoke_chat.py`/`llmcheck`, for which the stub was written.

**At the frozen threshold (0.48)**: validation precision 0.972 / coverage 0.871; test 0.973 / 0.896; dev external
1.00 / 0.88. In the container, p50 22 ms / p95 47 ms (C2 target p95 < 100 ms).

### Error analysis (test split, messages the model acts on)

| Language | Messages | Abstained | Wrong when acting | Precision when acting |
|---|---|---|---|---|
| ES | 166 | 14 (8%) | 8 | 0.947 |
| PT | 160 | 20 (13%) | 0 | 1.000 |

- 6 of the 8 Spanish errors are one confusion: **unrecognized_charge → not_received** (a held-out family of
  "no hice esa compra"-style phrasings). The other two are wrong_amount → unrecognized_charge / not_received.
- Portuguese abstains more but never acts wrongly on test. Per-class test F1: duplicate, ATM, lost/stolen and
  out_of_scope 1.00; other_in_scope 0.95; not_received 0.90; wrong_amount 0.82; unrecognized_charge 0.81.
- Dev external: no wrong answer among the messages the model acts on; the two deliberately ambiguous messages ("hay un cargo raro…",
  "el lunes me cobraron 38 dólares…") get 0.41 and abstain, so the orchestrator asks what happened.
- Behavior checks that the stub failed now pass (service tests): "tarjeta de crédito" no longer means out of scope,
  "cobro indebido" → wrong_amount, follow-ups like "fue la segunda" never set a dispute type.

### Country, segment and accent

The classifier sees only the masked text, never country, segment or accent, so it cannot condition on them. The
organizer data has no dispute text by country/segment/accent to measure disparities, and the P4 held-out cases
(`eval/cases/`, which carry those fields in format C4) do not exist yet. **This breakdown is pending on the P4
set**; `eval/run_eval.py` should report it with the same denominators.

### Variability

- Classifier: deterministic at inference (same input → same probabilities; checked) and at training (lbfgs, fixed
  corpus seed 20260930, pinned e5 revision 614241f).
- LLM (three `llmcheck` runs): identical accuracy in all runs; only latency varies (Flash p50 735–785 ms).

### Known limitations

- The corpus is template-generated; our test split shares slots and noise with train, so its numbers are optimistic.
  The P4 held-out set is the independent measure (see the leakage rules in `docs/ml_labels.md`).
- One data iteration (templates v1 → v2) was made after reading validation errors; test was never inspected first.
- Spanish recall of unrecognized_charge is the weakest point; more paraphrase families would help.

## 2. Retrieval (RAG over `kb_chunks`)

Index: `ml/rag/index.py` — 51 chunks from `policies/disputes.yaml` (dispute types in ES/PT; rules, status rules and
global guarantees in EN + ES + PT), embedded by ml-service `/embed` (kind=passage). The FAQ (`knowledge/faq/`) is
indexed automatically when P4 writes it (0 files today). Evaluation: `ml/rag/evaluate.py`, 30 labeled questions
(15 ES / 15 PT).

| Ranker | R@1 | R@3 | R@5 | MRR | R@3 ES | R@3 PT |
|---|---|---|---|---|---|---|
| Dense e5 (pgvector cosine) | 0.60 | **0.87** | 0.87 | 0.74 | 0.87 | 0.87 |
| Lexical TF-IDF (baseline) | 0.70 | 0.87 | 0.90 | 0.80 | 0.87 | 0.87 |

- With rules indexed only in English, dense R@3 was 0.50: Spanish/Portuguese questions never reached English rule
  text. Adding the team's Spanish wording (supervisor console) and a Portuguese translation fixed it.
- Dense and lexical tie at R@3 and miss different questions (amount-threshold questions go to escalation rules;
  "pendente" questions go to dispute types), so a hybrid ranker is the natural next step.
- The backend does not query `kb_chunks` yet; wiring retrieval into the chat is a backend task.

## 3. LLM (DeepSeek, prompts v2)

See ADR 0004 for the full tables. Summary of the 30 Sep runs:

- `llmcheck` extended to 26 messages (10 new: amounts in words, dates without year, merchant typos). Flash and Pro:
  100% amount, 96% date, 100% merchant, the same in 3 runs; Flash costs ~40% of Pro at ~60% of its latency.
  Prompt stays `deepseek-prompts-v2`.
- `LLM_COMPOSE=ai` passes the smoke scenarios but drops the decisive sentence in 3 of 11 replies (reversed charge,
  declined attempt, verification-code notice). **Keep `LLM_COMPOSE=template`.**

## 4. End-to-end

`scripts/smoke_chat.py`: 24/24 checks with the trained classifier, both with `LLM_COMPOSE=template` and `ai`,
against Mailpit. Note: with the real SMTP server configured in `.env`, the Mailpit check fails by design (the email
goes to `MAIL_REDIRECT_TO`), and Keycloak occasionally rejects a demo TOTP code reused within one 30-second window
(retry after the window).

## 5. Open items for other roles

- P4: write `eval/cases/` and `knowledge/faq/{es,pt}`; check corpus overlap before freezing the test set.
- Lead: optionally `&& !cls.Abstain` in `orchestrator.go` for out_of_scope (the service already maps an abstained
  out_of_scope to other_in_scope); wire `kb_chunks` retrieval if the RAG is used in replies; tighten `keepsFacts` if
  `LLM_COMPOSE=ai` is wanted.

## 6. Reproduce

```bash
poetry install --with ml
poetry run python ml/data/generate_utterances.py
poetry run python ml/train.py                      # writes ml/service/model/{classifier,golden}.json
poetry run pytest ml/service/tests -q
docker compose build ml-service && docker compose up -d ml-service
poetry run python ml/rag/index.py && poetry run python ml/rag/evaluate.py
cd backend && go run ./cmd/llmcheck                # needs DEEPSEEK_API_KEY in the environment
```
