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
- Evaluation must record `prompt_version` (currently `deepseek-prompts-v4`) and the model, and compare Flash vs Pro on the
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

### Evidence (2026-09-30, P3): 26 messages, 3 runs, and LLM_COMPOSE template vs ai

- `llmcheck` now has 26 messages (ES 15 / PT 11): 10 new ones with amounts in words, dates without a year and
  merchants with typos. Three runs, prompts v2 unchanged (no v3 needed):

| Provider | Amount | Date | Merchant | p50 | p95 | Cost (26 calls) |
|---|---|---|---|---|---|---|
| fake (rules) | 69% | 76% | 0% | 0 ms | 0 ms | 0 |
| deepseek-flash | 100% | 96% | 100% | 735–785 ms | 0.92–1.10 s | USD 0.0029 |
| deepseek-v4-pro | 100% | 96% | 100% | 1.24–1.29 s | 1.37–1.48 s | USD 0.0075–0.0078 |

  Identical accuracy in all three runs; the only miss is still the "semana passada" boundary. Flash stays primary.
- `LLM_COMPOSE=ai` vs `template` on the smoke scenarios (`scripts/smoke_chat.py`, both 24/24 green against Mailpit):
  the AI rewrite keeps the verified facts (amount, merchant, date, card) but **drops the decisive message** in three
  of eleven replies: the reversed charge reply no longer says the money is back, the declined-attempt reply no
  longer says nothing was charged, and the card-block proposal loses the verification-code notice. `keepsFacts`
  only checks facts, not the outcome sentence. **Decision: keep `LLM_COMPOSE=template`** until the guard also
  requires the outcome-specific key phrase (or the rewrite is limited to tone around the template's sentences).

### Evidence (2026-10-01): prompts v3 add the refusal screen

- Eval test v2 showed 12 errors where another person's data or attempts to change the assistant's rules, in new
  wordings, got a question instead of a refusal: the regex guard only knows fixed phrases. A small classifier trained
  on our templates did not generalize (grouped cross-validation: half of the attacks caught only with 115 false
  refusals), so the model already called on every message now also answers `refuse`: `third_party_data`,
  `instruction_override`, `bypass_process` or null. Same call, a few more output tokens. The orchestrator waits for
  the extraction after classification (disputes needed it anyway) and refuses (`SEC-INJ-01`) when it is set; a
  third-party request gets its own reply ("solo puedo ayudarte con tus propias tarjetas"). The value is never stored
  in the conversation state.
- The regex guard no longer matches refund words: "no me reembolsaron" is a real complaint and was being refused.
- `backend/cmd/screencheck` measures the screen. Development set (`eval/screen/dev.jsonl`, team-written): 60/60
  refusals caught, 6/48 false refusals, all of the form "my mother asked me to complain for her" (the refusal reply
  tells that person to write from their own session, which is the right guidance, but they are counted as errors).
  Independent holdout (`eval/screen/holdout.jsonl`, 120 messages written by a separate agent with no access to the
  repository, measured once, three runs): **60/60 refusals caught, 0/60 false refusals** in each run; the old regex
  alone caught 0/60. Cost about USD 0.0001 per message.
- `llmcheck` with v3 (Flash): 100% amount / 100% date / 100% merchant, p50 980 ms. Extraction did not degrade.

### Evidence (2026-10-01): prompts v4 add a second opinion on the dispute type

- After the refusal screen, 20 of the 25 test v2 errors were dispute paraphrases the classifier abstained on. The
  extraction now also returns `dispute_type` (one of the six types, or null). The orchestrator keeps the classifier
  as the decider and adds one rule: when the classifier abstains, its best guess is used if the model's reading
  names the same type. Any disagreement still asks the customer. Using the model alone was measured as a reference
  but not served: a single external model would then decide the type, and the type sets deadlines and limits.
- `backend/cmd/typecheck` compares the rules with the live classifier and DeepSeek. The served rule was fixed on the
  dev cases (91 v1 + v2 dev turns: 79.1% -> 90.1%, no new wrong types) **before** the independent holdout was run.
- Independent holdout (`eval/typecheck/holdout.jsonl`, 140 messages written by a separate agent with no access to
  the repository, measured once):

| Rule | Right | Wrong type | Asks |
|---|---|---|---|
| classifier alone | 78.6% (110/140) | 2 | 28 |
| **agreement (served)** | **89.3% (125/140)** | **2** | 13 |
| model alone when the classifier abstains (reference) | 96.4% (135/140) | 2 | 3 |

  The two wrong types are the same in all rules, both from a confident classifier: a new card that never arrived
  (labeled lost/stolen, read as not received) and a cancelled gym membership still charged (labeled not received,
  read as wrong amount). `wrong_amount` is still the weakest type (11/18 under agreement).
- With v4 the refusal screen is unchanged (holdout 60/60 and 0/60; dev 60/60 and 6/48) and `llmcheck` gives
  100% amount / 100% date / 100% merchant, p50 929 ms.
