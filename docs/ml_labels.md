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

## 3. Generation protocol (`ml/data/generate_utterances.py`, templates-v2)

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
  text and for the whole corpus. Current corpus: 2,762 rows (2,110 train / 326 val / 326 test),
  `corpus_sha256 = 1dd695a4…`.

One iteration was made after looking at **validation** errors (templates-v1 → v2 added families to every label);
test errors were never inspected before freezing the model.

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
| B0 majority | 0.03 | 0.04 |
| B1 keyword stub | 0.52 | 0.96 |
| M1 TF-IDF + LogReg | 0.91 | 0.92 |
| M2 multilingual-e5-small + LogReg | 0.91 | 0.84 |
| **M3 mean(M1, M2) — served** | **0.94 (0.89 / 0.98)** | **0.92** |

Threshold **0.48**: the lowest value whose validation precision is ≥ 0.97 (target 0.95 + 0.02 margin) there and at
every higher threshold. Validation precision/coverage 0.972 / 0.871; test 0.973 / 0.896; the two ambiguous dev
messages (confidence 0.41) abstain. ml-service: `e5-tfidf-avg-1dd695a4`, p95 ≈ 47 ms in the container.
