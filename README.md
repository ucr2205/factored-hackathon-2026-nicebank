# AI-First Banking Customer Service — Transaction Dispute Intake

Factored AI & Data Hackathon 2026 submission.

An AI-first (not chatbot) customer-service system for a LATAM bank that handles **transaction dispute intake**
in Spanish and Portuguese. The system follows **Understand → Decide → Act → Verify → Escalate**:
AI is used where natural language requires it, while authentication, permissions, policy decisions and
actions are enforced by deterministic code. The system never moves money or issues refunds.

> Status: Phase 0 scaffolding (2026-09-26). Sections marked *TBD* are filled in during the sprint.

## Architecture (summary)

| Component | Tech | Role |
|---|---|---|
| `backend/` | Go | API, sessions, orchestrator (state machine), policy engine, simulated bank tools, audit |
| `frontend/` | React + Vite + TS | Customer login + chat, internal agent console (handoffs, audit) |
| `ml/` | Python, FastAPI | `ml-service`: `/classify` (learned dispute-type classifier), `/embed` (multilingual embeddings) |
| `etl/` | Python, DuckDB, Polars, Pandera | S3 → raw → silver (contracts, dedup, quarantine, lineage) → Postgres loader |
| `infra/` | Keycloak, Postgres + pgvector, OTel, Jaeger, Prometheus | Identity (OIDC + PKCE + TOTP step-up), row-level security, tracing, metrics |
| `eval/` | Python | Held-out evaluation harness: baseline vs system |

Key decisions are recorded in [`docs/adr/`](docs/adr/).

## Quick start

Prerequisites: Git, Docker Desktop, Python 3.12+, AWS CLI v2 (plus Go 1.23+ and Node 22 for backend/frontend work).

```bash
cp .env.example .env                      # local dev values; never commit .env
aws configure --profile factored          # read-only dataset credentials (shared privately by the team lead)
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
make data                                 # sync the full dataset (~5.3 GB) into data/raw/
make inventory                            # regenerate docs/data_inventory.md
docker compose up -d                      # TBD: full stack
```

No `make` on Windows? Every target is a single `python scripts/...` command — see the [`Makefile`](Makefile).

## Data

- Source: organizer-provided **synthetic** dataset (read-only S3 bucket), 13 tables, Mexico/Colombia/Argentina,
  June 2023 – June 2026. See [`docs/data_inventory.md`](docs/data_inventory.md).
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

*TBD* — safe automated resolution, containment, escalation quality, unsafe outcomes (counts and denominators),
p50/p95 latency and cost per case, broken down by language and customer segment.

## Limitations and production gap

*TBD* — see `docs/production_gap.md`.
