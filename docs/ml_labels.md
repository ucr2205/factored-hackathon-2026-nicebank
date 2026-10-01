# ML labels and training corpus (P3)

## 1. The dataset labels cannot train a dispute classifier

Evidence from the Gate 1 EDA and the P2 profiling (`docs/eda_findings.md`, `docs/data_quality_report.md`):

- `call_transcripts.customer_text`: 171,321 rows but only **42 distinct texts**, all Spanish, all balance
  inquiries generated from 2 templates. No text describes a disputed charge.
- `detected_intents` has a **single value** (`consulta_general`); `contact_reason` has 6 generic categories
  (Queja, Transaccional, Producto, Técnico, Comercial, Retención) that do not say whether a contact is about a charge.
- Therefore the label-quality question (is `detected_intents` circular with `contact_reason`?) is moot: neither
  carries dispute types. The transcripts are used only as **out_of_scope** examples.

## 2. Taxonomy (C6, frozen 28 Sep)

`unrecognized_charge, duplicate_charge, wrong_amount, not_received, atm_cash_not_dispensed, card_lost_stolen,
other_in_scope, out_of_scope`. "Cobro indebido" (complaints `Fees`) maps to `wrong_amount`
(`analysis/mappings/contact_reason_to_flow.csv`).

`other_in_scope` covers vague dispute requests ("tengo un problema con un cargo") **and short follow-up replies**
("fue la segunda", "sí, ese"). The orchestrator classifies every turn and overwrites the dispute type when the
classifier is confident about a known type, so follow-ups must never be labeled as a dispute type.

## 3. Generation protocol (`ml/data/generate_utterances.py`, templates-v3)

- Each label has 5–10 **families** of core phrasings per language (ES and PT), written by the team (P3, assisted by
  an AI coding agent), never copied from evaluation cases.
- Slots: amounts (digits in both decimal formats, words, `$`, `R$`, pesos, reais, USD), dates (relative, `12/06`,
  without year), merchants, card type (incl. "tarjeta de crédito", which the keyword stub misread as out_of_scope).
- Noise: openers/closers, missing accents (30%), 1–2 typos (25%), lower/upper case, and the masking placeholders the
  backend produces (`[NAME]`, `[EMAIL]`, `[NUMBER]`, always uppercase).
- **Split by family**: per label and language, one family goes to test, one to validation, the rest to train. Test
  and validation therefore contain phrasings the model never saw.
- Transcript texts are masked with the backend rules, split 5/1/1 and written only to `ml/data/build/` (git-ignored).
- `ml/data/build/manifest.json` records seed, counts per split/label/language, families per split and SHA-256 per
  text and for the whole corpus. Current corpus: 3,442 rows (2,470 train / 486 val / 486 test),
  `corpus_sha256 = 273b2af3…`.

Iterations:
- templates-v1 → v2 (30 Sep): families added to every label after looking at **validation** errors only.
- templates-v2 → v3 (1 Oct): after eval **test v1** was scored, its error summary showed abstentions on paraphrases
  of `wrong_amount` and `not_received` (9 of 14 errors). v3 adds 6 + 5 families for those two labels (discounts,
  tips, exchange rate, unit count; tracking, vanished sellers, services never started, cancellations) and one family
  for each other label. Because test v1 informed this change, **test v1 is no longer a clean held-out set for the
  v3 model**; eval case set v2 (`eval/cases/v2/`, frozen in commit dc911a3 before v3 was written) is the measure.
- The served v3 model is refit on train + val + test of the corpus (`ml/train.py --refit`) after C and the threshold
  were chosen on validation; the corpus metrics in section 6 are those of the train-only fit.

## 4. External sanity set (`ml/data/dev_external.jsonl`)

25 messages already in the repo (`scripts/smoke_chat.py`, `backend/cmd/llmcheck`), hand-labeled; 3 are tagged
`ambiguous` and labeled `other_in_scope`. They were visible to the corpus author, so they are a sanity check, not an
independent test. The keyword stub was written for these same messages, which explains its high score there.

## 5. No leakage with the P4 held-out set

- P4's ~200 cases (`eval/cases/`) must be written by different people/instructions, **not** from these templates.
- Before freezing the P4 test set, check overlap: normalized exact matches and near-duplicates (character 4-gram
  Jaccard > 0.8) between `eval/cases/*.jsonl` turns and `ml/data/build/corpus.jsonl` must be zero.
- The P4 set is the independent measure of the classifier; numbers on our own test split are optimistic by design
  (same templates' slots and noise).

## 6. Model and threshold (summary; details in MLflow, `ml/mlruns`, experiment `dispute-classifier`)

| Model | Test macro-F1 (es / pt) | Dev external acc. |
|---|---|---|
| B0 majority | 0.04 | 0.00 |
| B1 keyword stub | 0.43 | 0.96 |
| M1 TF-IDF + LogReg | 0.84 | 0.88 |
| M2 multilingual-e5-small + LogReg | 0.87 | 0.88 |
| **M3 mean(M1, M2) — served** | **0.90 (0.90 / 0.89)** | **0.88** |

templates-v3, train-only fit. These are lower than the templates-v2 numbers (M3 0.94) because the split by family
changed with the new families and the held-out families are harder; the two corpora are not comparable. Eval case
set v2 (README, "Evaluation results") is the comparison between models.

Threshold **0.65**: the lowest value whose validation precision is ≥ 0.97 (target 0.95 + 0.02 margin) there and at
every higher threshold. Validation precision/coverage 0.973 / 0.681; test 0.979 / 0.683. The served model
`e5-tfidf-avg-273b2af3-all` is the same M3 refit on all corpus splits with that threshold. The previous model
(templates-v2, `e5-tfidf-avg-1dd695a4`, threshold 0.48) is in MLflow and git history.
