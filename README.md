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

118 held-out test cases (ES/PT), each an invented customer sentence anchored on a **real transaction** of a demo
customer, with the expected outcome derived from that row and the policy. The same cases run against the system and
against a rules-only baseline that sends every dispute to a human. Definitions: [`eval/RUBRIC.md`](eval/RUBRIC.md);
full report with breakdowns by language, segment, country and category: [`eval/reports/`](eval/reports/).

| Metric (test split, 95% Wilson CI) | System | Baseline |
|---|---|---|
| Correct outcome (outcome + action + policy rule) | **88.1%** (104/118; 81–93%) | 3.4% (4/118) |
| Safe automated resolution | **82.6%** (38/46; 69–91%) | 0% (0/46) |
| Unsafe outcomes | **0%** (0/118; 0–3%) | 0% (0/118) |
| Escalation recall / precision | **96.4%** (27/28) / **100%** (27/27) | 7.1% / 5.7% |
| Sent to a human | 22.9% | 29.7% |
| Latency p50 / p95 per turn | 852 / 1,234 ms | 2 / 17 ms |
| LLM cost per case | USD 0.00008 | 0 |

Versions: policy 0.2.0, classifier `e5-tfidf-avg-1dd695a4`, DeepSeek Flash with `deepseek-prompts-v2`,
`LLM_COMPOSE=template`. Two test cases have known label errors (documented in `eval/cases/manifest.json`); without
them accuracy is 89.8%. Most remaining errors are paraphrases of "wrong amount" that the classifier abstains on:
the assistant asks instead of acting.

Component results: classifier test macro-F1 0.94 vs 0.52 for the keyword baseline ([`docs/ml_report.md`](docs/ml_report.md));
retrieval recall@3 0.93 over policy + FAQ; DeepSeek Flash extraction 100% amount / 96% date / 100% merchant on 26
messages (ADR 0004). Reproduce: `make train`, `make test-ml`, `make rag`, `make eval`;
backend integration tests: `cd backend && go test -tags integration ./internal/orchestrator/` (see the test file
header for `TEST_DATABASE_URL`).

## Limitations and production gap

Synthetic data with no real dispute text, a team-written evaluation set, an external LLM, simulated card networks,
test identities and single-host infrastructure. Details and what each would need: [`docs/production_gap.md`](docs/production_gap.md).
