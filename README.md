# AI-First Banking Customer Service — Transaction Dispute Intake

Factored AI & Data Hackathon 2026 submission.

An AI-first (not chatbot) customer-service system for a LATAM bank that handles **transaction dispute intake**
in Spanish and Portuguese. The system follows **Understand → Decide → Act → Verify → Escalate**:
AI is used where natural language requires it, while authentication, permissions, policy decisions and
actions are enforced by deterministic code. The system never moves money or issues refunds.

> Status (2026-10-01): all components real — trained dispute classifier (ml-service), DeepSeek Flash for fact
> extraction, policy engine, verified tools, TOTP step-up, audit, agent console with claim/reveal/close, customer
> "Mis disputas", policy + FAQ retrieval index, and a held-out evaluation against a rules-only baseline.

## Architecture (summary)

| Component | Tech | Role |
|---|---|---|
| `backend/` | Go | API, sessions, orchestrator (state machine), policy engine, simulated bank tools, audit |
| `frontend/` | React + Vite + TS | Customer login + chat, internal agent console (handoffs, audit) |
| `ml/` | Python, FastAPI | `ml-service`: `/classify` (learned dispute-type classifier), `/embed` (multilingual embeddings) |
| `etl/` | Python, DuckDB, Polars, Pandera | S3 → raw → silver (contracts, dedup, quarantine, lineage) → Postgres loader |
| `infra/` | Keycloak, Postgres + pgvector, OTel, Jaeger, Prometheus | Identity (OIDC + PKCE + TOTP step-up), row-level security, tracing, metrics |
| `eval/` | Python | Held-out evaluation harness: baseline vs system |

Full design: [`docs/architecture.md`](docs/architecture.md). Key decisions are recorded in [`docs/adr/`](docs/adr/).
**Technical overview** (stack and why, security, logs, data, AI, testing, operations, FAQ, with the process
flowchart): [`docs/technical_overview.md`](docs/technical_overview.md).

## Security and privacy (summary)

| Layer | How |
|---|---|
| Identity | **Keycloak** (OIDC, Authorization Code + PKCE S256; no implicit or password grant for the web app). Roles `customer`, `agent`, `supervisor`. Blocking a card needs **step-up to TOTP** (acr 2, valid 5 min), checked by the backend inside the transaction. Brute-force protection, password policy, 5-min tokens, password reset that verifies the existing TOTP instead of resetting it. Tokens kept in memory only in the browser. |
| Data isolation | **Postgres row-level security**: 10 customer tables with `FORCE ROW LEVEL SECURITY`; every request pins the customer with a transaction-local `set_config('app.customer_id', …, true)`. The app role has no superuser, no `BYPASSRLS`, no `DELETE`; `messages` and `audit_events` are insert-only. Staff see escalated cases, never customer rows. |
| Personal data | Tokens carry an opaque `customer_ref`, not the bank id. Names and email are **AES-256-GCM** encrypted with per-field associated data (`PII_KEY` from the environment only). Text is **masked** (`[NAME]`, `[EMAIL]`, `[NUMBER]`) before any model sees it. Identity is revealed only to the agent who claimed the case, and audited. |
| Actions | Only two actions exist (open a dispute, block a card), both after explicit customer confirmation, idempotent, and verified by reading back. There is no refund or transfer tool. |
| AI | Models propose, the versioned policy decides. Pattern guard + LLM refusal screen (independent test: 60/60 attacks refused, 0/60 real customers refused). Replies come from reviewed templates. The LLM is swappable: DeepSeek today, but any OpenAI-compatible cloud model or a local one (Ollama, vLLM) can be configured; switching is gated by the same quality checks. |
| Web | Strict CSP and security headers (nginx), exact CORS allow-list, body-size limits, server timeouts, generic errors, all ports bound to 127.0.0.1, distroless non-root backend image. Secrets only in `.env`; `gitleaks` in pre-commit. |

## Logs and observability (summary)

- **Structured JSON logs** (`log/slog`): one line per HTTP request (method, route, status, duration, role,
  `request_id`, `trace_id`) and one per chat turn (outcome, policy rules, latency, LLM cost). Customer text, names,
  emails, tokens and card data are never logged, and sensitive keys are redacted automatically as a safety net.
- **Correlation:** `X-Request-ID` and the OpenTelemetry `trace_id` appear in logs, error bodies and every audit event;
  the agent console links each case to its Jaeger trace.
- **Audit trail:** `audit_events` records every step (understand, extract, find, policy, propose, confirm, act,
  verify, hand off, respond, identity reveal, close) with its policy rule; insert-only, no personal data.
- **Traces and metrics:** OpenTelemetry → Collector (strips personal data) → Jaeger; Prometheus metrics for turns,
  latency, tool calls, LLM calls/tokens/cost, emails and the classifier. `/api/health` and `/api/ready`.

## Quick start

Prerequisites: Git, Docker Desktop, Python 3.12+ with **Poetry 2.x**, AWS CLI v2 (plus Go 1.26+ and Node 22 for backend/frontend work).

```bash
cp .env.example .env                      # local dev values; never commit .env
aws configure --profile factored          # read-only dataset credentials (shared privately by the team lead)
poetry install                            # Python deps into ./.venv (ML deps: poetry install --with ml)
make data                                 # sync the full dataset (~5.3 GB) into data/raw/
make inventory                            # regenerate docs/data_inventory.md
make profile                              # data-quality profile -> docs/data_quality_report.md (~4 min)
make eda                                  # Gate 1 business EDA -> docs/eda_findings.md (after make profile)
make etl                                  # raw -> silver: contracts, quarantine, lineage (docs/etl_rules.md)
docker compose up -d --build              # Postgres, Keycloak, ml-service, backend, frontend, Jaeger, Prometheus
make seed                                 # load the full silver dataset into Postgres (resets demo data)
make smoke                                # reseed + run the scripted end-to-end scenarios against the API
```

| URL | What |
|---|---|
| http://localhost:8088 | Web app (production build). For development: `cd frontend && npm run dev` → http://localhost:5173 |
| http://localhost:8081/api/health | Backend |
| http://localhost:16686 | Jaeger (traces) |
| http://localhost:9090 | Prometheus (metrics) |
| http://localhost:8080 | Keycloak (realm `latam-bank`) |
| http://localhost:8025 | Mailpit (test mailbox: password-reset emails) |

Test users (local test realm only, see [`infra/keycloak/README.md`](infra/keycloak/README.md)): `cliente01`–`cliente20`
(customers; card blocking asks for a TOTP code from the test seed), `agente01`, `agente02` (agents), `supervisor01`.
Postgres is exposed on host port **5433** to avoid clashing with a local PostgreSQL.

No `make` on Windows? Every target is a single `poetry run python ...` command — see the [`Makefile`](Makefile).
Python dependencies are managed **only with Poetry** (`poetry add <pkg>`, `poetry add --group ml <pkg>`); never `pip install`.

## Data

- Source: organizer-provided **synthetic** dataset (read-only S3 bucket), 13 tables, Mexico/Colombia/Argentina,
  June 2023 – June 2026. See [`docs/data_inventory.md`](docs/data_inventory.md) (files and partitions) and
  [`docs/data_quality_report.md`](docs/data_quality_report.md) (quality profile and the rules it sets for the ETL).
- Raw and processed data are **never committed** (`data/` is git-ignored). Everything is reproducible from scripts.
- Team-generated data (e.g. Portuguese test cases) is labeled `origin: team_generated`.
- `is_fraud` and resolution fields are used **only as evaluation labels**, never as system inputs.

## Repository layout

```
backend/    Go service                  frontend/   React app
ml/         ml-service + training       etl/        data pipeline
analysis/   reproducible EDA scripts    eval/       evaluation harness + cases
policies/   disputes.yaml (policy spec) prompts/    versioned LLM prompts
knowledge/  FAQ corpus (es/pt) for RAG  infra/      compose configs (Keycloak, Postgres, OTel...)
docs/       inventory, findings, architecture, ADRs
scripts/    task entry points used by the Makefile
```

## Evaluation

Held-out test cases (ES/PT), each an invented customer sentence anchored on a **real transaction** of a demo
customer, with the expected outcome derived from that row and the policy. The same cases run against the system and
against a rules-only baseline that sends every dispute to a human. Definitions: [`eval/RUBRIC.md`](eval/RUBRIC.md);
full reports with breakdowns by language, segment, country and category: [`eval/reports/`](eval/reports/).

There are two case sets. **v2** (`eval/cases/v2/`, 120 test cases) was written and frozen after v1 was scored and
before the current classifier was trained, so it is the headline number. **v1** (118 test cases) informed the last
training change (see `docs/ml_labels.md`), so it is no longer a clean held-out set and is kept for history.

| Metric (test v2, 95% Wilson CI) | Current system | Refusal screen, no second opinion | Retrained classifier only | First classifier | Baseline |
|---|---|---|---|---|---|
| Correct outcome (outcome + action + policy rule) | **86.7%** (104/120; 79–92%) | 79.2% (95/120) | 70.8% (85/120) | 65.0% (78/120) | 5.8% (7/120) |
| Safe automated resolution | **81.8%** (36/44; 68–90%) | 72.7% | 75.0% | 56.8% | 0% |
| Unsafe outcomes | **0%** (0/120; 0–3%) | 0% | 0% | 1.7% (2/120) | 0% |
| Adversarial cases (injection, other person's data) | **100%** (26/26) | 100% | 57.7% | 57.7% | 0% |
| Escalation recall / precision | **89.3%** (25/28) / **92.6%** (25/27) | 71.4% / 87.0% | 71.4% / 95.2% | 75.0% / 80.8% | 25.0% / 14.9% |
| Sent to a human | 22.5% | 19.2% | 17.5% | 21.7% | 39.2% |
| Latency p50 / p95 per turn | 969 / 1,251 ms | 1,034 / 1,314 ms | 774 / 1,199 ms | 803 / 1,200 ms | 1 / 15 ms |
| LLM cost per case | USD 0.00012 | USD 0.00010 | USD 0.00006 | USD 0.00007 | 0 |

The current system is the retrained classifier (`e5-tfidf-avg-273b2af3-all`) plus two answers from the DeepSeek call
that already extracts the facts (`deepseek-prompts-v4`): a refusal screen (another person's data, rewriting the
assistant's rules, money without a process) and a second opinion on the dispute type, used only when the classifier
is unsure and the two agree (ADR 0004). The middle columns are the same evaluation at each earlier step.

None of the 16 remaining errors is a wrong action: 11 are dispute paraphrases where the classifier was unsure and
the model did not confirm its guess (the assistant asks which problem it is), 3 are out-of-scope requests answered
with a question, 1 vague message is sent to a human, and 1 classifier call timed out (`ESC-TECH-01`, handed to a
human). On test v1 the retrained classifier without the model's answers scored 87.3% (103/118), 0 unsafe.

Both model answers were also measured on their own, on messages written by a separate agent with no access to the
repository and measured once: the refusal screen refused **60/60** attacks and **0/60** legitimate messages (the regex
guard alone caught 0/60); the dispute type was right for **89.3%** of 140 messages with the agreement rule versus
78.6% for the classifier alone, with no additional wrong types. Commands: `backend/cmd/screencheck`,
`backend/cmd/typecheck`.

The drop from v1 to v2 is the honest finding: the same team wrote the training phrasings and v1, so v1 overstated
how well the classifier handles new wordings. Both sets are still written by the team (and an AI assistant); a set
written by people outside the ML work is the next step (`docs/production_gap.md`).

Versions: policy 0.2.0, classifier `e5-tfidf-avg-273b2af3-all` (previous: `e5-tfidf-avg-1dd695a4`), DeepSeek Flash
with `deepseek-prompts-v4` (79.2%: v3; 70.8% and 65.0%: v2), `LLM_COMPOSE=template`.

Component results: classifier corpus test macro-F1 0.90 vs 0.43 for the keyword baseline ([`docs/ml_report.md`](docs/ml_report.md));
retrieval recall@3 0.93 over policy + FAQ; DeepSeek Flash extraction 100% amount / 100% date / 100% merchant on 26
messages (ADR 0004). Reproduce: `make train`, `make test-ml`, `make rag`, `make eval`;
backend integration tests: `cd backend && go test -tags integration ./internal/orchestrator/` (see the test file
header for `TEST_DATABASE_URL`).

## Limitations and production gap

Synthetic data with no real dispute text, a team-written evaluation set, an external LLM, simulated card networks,
test identities and single-host infrastructure. Details and what each would need: [`docs/production_gap.md`](docs/production_gap.md).
