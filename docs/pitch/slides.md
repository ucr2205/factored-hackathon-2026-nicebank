---
marp: true
theme: default
paginate: true
title: NiceBank — AI-first dispute intake
---

<!-- Draft deck (6 slides). Export with Marp: `npx @marp-team/marp-cli docs/pitch/slides.md --pptx` (or --pdf). -->

# NiceBank: AI-first card dispute intake

**Spanish and Portuguese · Mexico, Colombia, Argentina**

AI understands the customer. Written rules decide. Code verifies every action.
When it is not sure, it asks; when a human is needed, the human gets everything.

Factored AI & Data Hackathon 2026

---

# The problem

- **40.4% of all complaints** in the dataset are card-charge disputes (27,133 in 3 years): unrecognized charges and
  undue charges, about 20% each, with a median of ~15 days to resolve.
- Today every dispute goes to a person, even "I was charged twice at the supermarket yesterday".
- The organizer data has **no dispute text** and the call transcripts are balance inquiries:
  we cannot simply train on history.

**Goal:** resolve the routine disputes automatically and safely, and send the rest to a specialist with the work
already done.

---

# How it works: AI proposes, code decides

1. **Guard**: mask personal data; block instruction-override attempts.
2. **Understand**: trained classifier (dispute type, abstains when unsure) + DeepSeek Flash (amount, date, merchant).
3. **Decide**: search the customer's own transactions (row-level security) and apply `policies/disputes.yaml`:
   explain reversed/declined/pending charges, escalate high amounts or old charges, otherwise open a case.
4. **Act**: only after the customer confirms; blocking a card also needs a TOTP code.
5. **Verify**: read the result back before telling the customer.
6. **Escalate**: handoff with verified facts and evidence; identity revealed only to the claiming agent, audited.

The assistant **never** refunds, transfers money or shows another customer's data.

---

# What we built

- Customer web app: cards, recent movements, chat, **"Mis disputas"** with the specialist's resolution.
- Agent console: prioritized queue, claim, protected identity, close with outcome and note, full audit trail.
- Supervisor view: active policy and models, live metrics.
- ml-service: TF-IDF + multilingual-e5 classifier (corpus test macro-F1 **0.90** vs 0.43 keywords), embeddings for a
  policy + FAQ retrieval index (recall@3 **0.93**).
- Keycloak (PKCE + TOTP), Postgres with row-level security, encrypted identity, OpenTelemetry, email outbox.

---

# Results (120 held-out cases, new wordings, anchored on real transactions)

| | System | Rules-only baseline |
|---|---|---|
| Correct outcome | **86.7%** (CI 79–92%) | 5.8% |
| Safe automated resolution | **82%** | 0% |
| Unsafe outcomes | **0 / 120** | 0 / 120 |
| Attacks and other people's data refused | **26 / 26** | 0 / 26 |
| Escalation recall / precision | **89% / 93%** | 25% / 15% |
| p50 latency per turn · cost per case | 0.97 s · USD 0.0001 | — |

No error is a wrong action: when unsure, the assistant **asks instead of acting**. On fresh wordings we started at
65% with 2 unsafe outcomes. Retraining, a refusal screen and a second opinion from the LLM (used only when it agrees
with the classifier) took it to 87% with none. Checked on messages written by an independent author: 60/60 attacks
refused, 0/60 real customers refused, dispute type right 89% vs 79% for the classifier alone.

---

# Honest limits and next steps

- Trained on a team-written corpus (the data has no dispute text); the next step is real, consented messages
  and a blind test set written outside the team.
- External LLM sees masked text only; production needs a data-processing agreement or a self-hosted model.
- Card networks and chargebacks are simulated; single-host infrastructure; test identities.

Repository: README · `docs/architecture.md` · `eval/RUBRIC.md` · `docs/production_gap.md`
