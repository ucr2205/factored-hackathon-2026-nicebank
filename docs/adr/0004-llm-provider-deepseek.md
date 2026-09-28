# ADR 0004 — LLM provider: DeepSeek V4.1 Flash, V4 Pro as fallback

Status: accepted (2026-09-27)

## Context

The model only extracts facts (amount, date, merchant), resolves a candidate choice and optionally rewords a
reviewed reply (`llm.Provider`). The team has DeepSeek API access. Requirements: low latency per turn, JSON output,
cost per case reported, and a safe path when the provider fails.

## Decision

- `backend/internal/llm/deepseek.go` calls `https://api.deepseek.com/chat/completions` (OpenAI wire format) in
  **non-thinking** mode with `response_format: json_object` and temperature 0.
- Primary model `deepseek-flash` (DeepSeek V4.1 Flash; the older name `deepseek-v4-flash` is an alias). Fallback
  model `deepseek-v4-pro` on error, empty content or invalid JSON. If both fail, the deterministic `llm.Fake`
  answers, so an outage degrades extraction quality but never blocks a turn.
- `PickCandidate` resolves exact merchant names and ordinals locally first; the model is only asked otherwise.
- `Compose` defaults to the reviewed templates (`LLM_COMPOSE=template`). With `LLM_COMPOSE=ai` the model may reword
  a template, and the rewrite is used only if every verified fact appears verbatim; otherwise the template is sent.
- Extracted dates outside the last 13 months or in the future are dropped; every extracted value is still matched
  against the customer's records before anything happens.
- Cost is computed from the usage fields at peak prices (conservative) and reported per turn; calls are counted in
  `llm_calls_total{provider,model,op,status}` and traced as `llm.<op>` spans without text.
- Configuration: `LLM_PROVIDER=deepseek`, `DEEPSEEK_API_KEY` (local `.env` only), `LLM_MODEL`,
  `LLM_FALLBACK_MODEL`, `LLM_COMPOSE`. The backend refuses to start with `deepseek` and no key.

## Consequences

- Only masked text and verified facts leave the system. The dataset is synthetic; a real bank would need a data
  processing agreement and data-residency review for any external provider (see `docs/production_gap.md`).
- Evaluation must record `prompt_version` (`deepseek-prompts-v1`) and the model, and compare Flash vs Pro on the
  same held-out cases before the final configuration is frozen.

## Evidence (2026-09-27, `go run ./cmd/llmcheck`, 16 labeled ES/PT messages, prompts v1)

| Provider | Amount | Date | Merchant | p50 latency | Cost (16 calls) |
|---|---|---|---|---|---|
| fake (rules) | 81% | 87% | 0% | 0 ms | 0 |
| deepseek-flash | 100% | 93% | 100% | 1.0 s | USD 0.0017 |
| deepseek-v4-pro | 100% | 93% | 100% | 1.55 s | USD 0.0045 |

Flash matches Pro at lower latency and less than half the cost, so it stays primary with Pro as fallback. The
only miss for both is a range boundary ("semana passada" ending on day 9 vs 10). The fake extractor misses
amounts in words, "3 de enero"-style dates and merchants. Rerun after any prompt change and before the final
evaluation freeze.

### Prompt v2 and concurrent extraction (2026-09-27)

- `deepseek-prompts-v2` keeps the system prompt byte-identical on every call (today's date moved to the user turn) so
  DeepSeek's automatic context cache applies. Same accuracy as v1 (100% amount, 93% date, 100% merchant); p50 870 ms.
- The orchestrator starts the extraction together with classification (`orchestrator/speculative.go`); a turn takes
  max(classify, extract). Out-of-scope messages cancel the call within a few ms. JMeter (5 users, 60 s, DeepSeek
  Flash): dispute turns p50 970 ms / p95 1,299 ms, out-of-scope p50 12 ms / p95 138 ms, 0 errors.
- Metrics: `llm_speculative_extractions_total{outcome=used|discarded}`, `llm_calls_total{status="cancelled"}`.
