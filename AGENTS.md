# AGENTS.md — shared context for AI coding agents (opencode, Claude Code, others)

Read this before changing anything. It is the team's working memory: what exists, the rules, and who owns what.
Last updated: 2026-09-27 (sprint day 2 of 10). Submission deadline: **2026-10-05**; code freeze **2026-10-04 20:00**.

## What we are building

NiceBank (fictitious bank) — an AI-first customer-service system for **card transaction dispute intake** in
Spanish and Portuguese, for the Factored AI & Data Hackathon 2026. Every turn follows
**Understand → Decide → Act → Verify → Escalate**. The LLM only proposes (extracts facts, words replies);
deterministic Go code decides, executes simulated bank tools, verifies each write by reading it back, and audits.
The system never moves money or issues refunds.

Required demo cases: normal resolution (ES), ambiguous/unsupported request (PT), human escalation with TOTP
step-up and structured handoff. Metrics must compare a baseline and the system on held-out cases.

## Hard rules

1. **Language**: everything in the repo (code, identifiers, comments, commits, docs) is **English**. Only
   customer-facing text (chat replies, FAQ, policy display names, test-case utterances) is Spanish/Portuguese.
2. **Python = Poetry only.** `poetry install` (ML deps: `poetry install --with ml`), `poetry add <pkg>`
   (`--group ml` / `--group dev`), `poetry run python ...`. Never `pip install`, `requirements.txt` or manual venvs.
   Commit `pyproject.toml` and `poetry.lock` together.
3. **Never commit** `data/`, `.env`, credentials, organizer PDFs, `team/`, `*.duckdb`, `ml/mlruns/`.
4. **Leakage**: `is_fraud`, `was_resolved`, `was_escalated`, complaint `resolution`/`status`/`compensation_granted`
   are evaluation labels only — never model or system inputs.
5. **Security invariants** (do not weaken): the customer identity comes only from the verified token claim
   `customer_ref` (opaque; Postgres resolves it, ADR 0003); every customer query runs in `store.WithCustomer`
   (RLS via `SET LOCAL app.customer_id`); the backend never writes `customer_id` itself (column defaults);
   names are only in `customer_identity` as AES-GCM ciphertext (`PII_KEY`) and agents see them only through
   the audited reveal of a handoff they claimed; logs never carry message text, names, emails, tokens or card data
   (use `slog.*Context` so records get `request_id`/`trace_id`; new routes must be added to `openapi.yaml`); emails go only through the notifications outbox and never to
   dataset addresses on a real SMTP server (`MAIL_REDIRECT_TO`);
   actions require explicit customer confirmation; `block_card` requires `acr >= 2` (TOTP); the password-reset
   flow verifies the existing TOTP and must never reset it; no personal data in traces or metric labels.
6. **Contracts** below are frozen after 2026-09-28; changing one needs a note to the team lead first.
7. **Commits**: Conventional Commits in English (`feat(etl): ...`), small and atomic. Commits are made with
   opencode. Label team-made data `origin: team_generated`.

## Repository map

| Path | What | Owner |
|---|---|---|
| `backend/` | Go API: `internal/{auth,store,pii,notify,policy,llm,guard,mlclient,tools,orchestrator,httpapi,telemetry,audit,contract}` | Lead |
| `frontend/` | React 19 + Vite + TS + MUI + lucide-react: customer chat, agent console, supervisor view | Lead |
| `infra/keycloak/` | Realm `latam-bank` + `nicebank` login/email theme (PKCE, LoA step-up, verified reset flow) | Lead |
| `infra/postgres/init/` | Schema (C1) and row-level security | Lead |
| `ml/service/` | `ml-service` (FastAPI, contract C2) — currently a keyword **stub** | P3 |
| `etl/` | `inventory.py`, `seed_demo.py` (temporary demo subset), future raw→silver pipeline | P2 |
| `analysis/` | Reproducible EDA scripts (to be created) | P2 / P3 |
| `policies/disputes.yaml` | Dispute policy (C3) — **v0 draft by the lead** | P4 |
| `eval/` | Evaluation harness and held-out cases (to be created) | P4 |
| `scripts/` | `sync_data.py`, `smoke_chat.py` (end-to-end scenarios; good base for the eval harness) | Lead |
| `qa/jmeter/` | JMeter load plan (`nicebank-load.jmx`), load users `users.csv`, profiles and KPIs in its README | Lead + P4 |
| `docs/` | `data_inventory.md`, `api/contracts.md`, `adr/0001`..`0005`, `brand/` | All |
| `vault/` | Obsidian team documentation (Spanish): architecture, modules, per-member guides, plans, QA | All |

## How to run

```bash
poetry install
make env             # creates .env with a local PII_KEY (paste DEEPSEEK_API_KEY there yourself)
make data            # full dataset from S3 into data/raw/ (AWS profile "factored")
docker compose up -d --build
make seed            # 20 demo customers into Postgres (resets demo data)
make smoke           # reseed + 22 end-to-end API checks in 9 scenarios (must stay green)
make test            # Go unit tests + frontend build
make load            # JMeter smoke load test (needs jmeter on PATH)
```
Web app http://localhost:5173 (dev) or :8088 (container) · API :8081 (Swagger UI at `/api/docs`, spec at
`backend/internal/httpapi/openapi.yaml`) · Keycloak :8080 · Mailpit :8025 ·
Jaeger :16686 · Prometheus :9090 · Postgres host port **5433**. Test users: `cliente01..20`, `agente01..02`,
`supervisor01`, and `carga01..20` for load tests only (no TOTP, so they can never pass step-up). Local test realm
only; the team lead has the handout.

## Contracts

| # | Contract | Where | Owner |
|---|---|---|---|
| C1 | Operational schema + RLS | `infra/postgres/init/01_schema.sql`, `02_rls.sh` | Lead (P2 loads it) |
| C2 | `POST /classify {text, lang}` → `{label, confidence, abstain, model_version}`; `POST /embed {texts, kind}` → `{vectors, model}` (384 dims) | `ml/service/app.py`, `backend/internal/mlclient` | P3 |
| C3 | Policy file: dispute types, USD thresholds, eligibility, escalation rule ids | `policies/disputes.yaml`, `backend/internal/policy` | P4 |
| C4 | Test case JSONL `{id, lang, segment, country, customer_user, origin, turns[], expected{outcome, action, dispute_type, must_not[]}, tags[]}` | `eval/cases/` (to create) | P4 |
| C5 | Handoff JSON (verified facts, actions, evidence, open questions, suggested agents) | `docs/api/contracts.md`, `backend/internal/contract` | Lead |
| C6 | Dispute taxonomy: `unrecognized_charge, duplicate_charge, wrong_amount, not_received, atm_cash_not_dispensed, card_lost_stolen, other_in_scope, out_of_scope` | policy + classifier | P2 + P3 + P4 |

Outcomes returned per turn: `resolve | clarify | abstain | escalate | confirm`. `POST /api/chat?mode=baseline`
runs the rules-only baseline (every in-scope dispute goes to a human) on the same workload.

## Current status (2026-09-27)

Done: full dataset synced (7,671 CSV files, 5 GB) and inventoried; Docker stack (Postgres+pgvector, Keycloak,
ml-service stub, backend, frontend, Mailpit, OTel collector, Jaeger, Prometheus); backend orchestrator with policy
engine, verified tools, handoffs, audit trail, tracing and metrics; prompt-injection guard; customer chat with
account panel, agent console, supervisor view; NiceBank-branded Keycloak login, TOTP step-up and password
recovery; pseudonymized identity (opaque `customer_ref`, encrypted names, reveal-on-claim); DeepSeek provider
(`LLM_PROVIDER=deepseek`, Flash with Pro fallback, Fake as last resort; default is still `fake`); Go unit
tests; customer email notifications (outbox + worker, HTML template, `NiceBank <nicebank@evon.solutions>`,
Mailpit locally, real SMTP only with `MAIL_REDIRECT_TO`, ADR 0005); `make smoke` 22/22 green. The classifier is still a **keyword stub** behind contract C2.

Data findings to explain (P2): fact tables hold 84–88% of the published row counts, `digital_events` 156%,
`daily_exchange_rates` 439% (12 currency pairs per day); every table has one header across partitions (look for
schema evolution in content); Mexico transactions are all in USD; "Mexico" vs "México"; `complaints` has no
`transaction_id`.

## Workstreams (what each person owns next)

### P2 — Data / ETL / data quality
- `analysis/01_profile.py` → `docs/data_quality_report.md` (nulls, duplicates by PK, orphans, schema drift by
  month, late arrivals, the row-count deviations above).
- `analysis/02_business.py` → `docs/eda_findings.md`: share of dispute-related `contact_reason`, FCR/escalation/SLA
  for those contacts, cuts by country/segment/channel/month, and the complaint↔transaction matching experiment.
  **Gate 1 (2026-09-28 18:00)**: confirm the dispute flow with data or switch to plan B (card support).
- `etl/pipeline/`: raw → silver Parquet with Pandera contracts, dedup, quarantine, lineage (`etl_runs`),
  incremental watermark, USD normalization (ADR 0002), late-arrival test fixture; `docs/freshness_policy.md`.
- Replace `etl/seed_demo.py` with a loader into C1 that keeps its idempotency and the demo mapping file.

### P3 — AI / ML
- Label quality of `detected_intents` vs `contact_reason` (circularity), dataset without leakage, temporal split.
- Baselines (majority, keywords) vs TF-IDF+LogReg vs multilingual-e5-small+LogReg, tracked in MLflow; confidence
  threshold for precision ≥ 0.95; evaluate on Portuguese dev cases.
- Replace the stub in `ml/service/app.py` keeping contract C2 exactly (the backend already calls it).
- RAG over `policies/` + `knowledge/faq/{es,pt}` into `kb_chunks` (pgvector); versioned prompts in `prompts/`.
- LLM provider is DeepSeek (ADR 0004, `backend/internal/llm/deepseek.go`): tune `deepseek-prompts-v2` (rerun
  `go run ./cmd/llmcheck` after any prompt change), compare `deepseek-flash` vs `deepseek-v4-pro` (and `LLM_COMPOSE=template|ai`) on dev cases, keep masked input only.

### P4 — Policies / evaluation / docs / pitch
- Own `policies/disputes.yaml` (v0 exists; keep rule ids stable, amounts in USD, fairness: no rule by segment,
  country or accent). Write `knowledge/faq/es` and `knowledge/faq/pt`.
- `eval/RUBRIC.md` (safe automated resolution, unsafe outcome, escalation quality) and ~200 held-out cases in C4
  format (ES/PT, normal, ambiguous, human-required, adversarial); 20% double-labeled; freeze test set hash.
- `eval/run_eval.py` + `eval/metrics.py` built from `scripts/smoke_chat.py` (tokens via the `eval-harness`
  client); system vs `?mode=baseline`; metrics with denominators, Wilson CI, p50/p95, cost, per language/segment.
- README sections, `docs/architecture.md`, `docs/production_gap.md`, slides (4–6) and the video pitch.

### Lead — backend / frontend / security / infra
- Real LLM provider wiring, session-expiry and tool-failure tests, RLS integration test in Go, frontend polish,
  observability dashboard (optional), reviews of every PR, contracts and gates.

## Team documentation

The human-facing documentation lives in the Obsidian vault at `vault/` (open that folder as a vault in Obsidian):
global architecture, one note per module, one note per teammate with ready-to-use prompts, the
infrastructure/code/test backlogs, the QA strategy and the JMeter guide. It is the one deliberate exception to the
English rule: it is written in Spanish, in plain language, for the team. Keep this file and the vault consistent at
every gate, and never put secrets in it (per-user Obsidian files are git-ignored).

## Gates

2026-09-28 Gate 1 (flow confirmed, contracts frozen) · 2026-09-30 Gate 2 (normal case end to end with real
components where ready) · 2026-10-02 Gate 3 (feature complete + first full evaluation) · 2026-10-04 20:00 code
freeze · 2026-10-05 submission.
