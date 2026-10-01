# Load testing with Apache JMeter

`nicebank-load.jmx` simulates customers using the dispute assistant:

1. `01 Keycloak token` — once per virtual user (direct grant with the `eval-harness` test client).
2. `02 GET account overview` — `/api/me/overview` (cards + recent movements, RLS-scoped).
3. `03 POST chat — unrecognized charge (ES)` — full orchestrator turn (classify, extract, find transactions, policy).
4. `04 POST chat — out of scope (PT)` — asserts the `abstain` outcome.

Each iteration waits a random 1–3 s think time. Users come from `users.csv`: `carga01..carga20`, load-test
accounts mapped to the 20 demo customers **without TOTP**, so a load test can never pass step-up or block cards.
They exist only in the local test realm (created by `etl/seed_demo.py`).

## Run

Requires Apache JMeter 5.6+ (Java 8+) on `PATH`. From the repo root, with the stack up (`docker compose up -d`):

```bash
make load                                   # smoke profile: 5 users, 60 s
jmeter -n -t qa/jmeter/nicebank-load.jmx -Jusers=25 -Jramp=60 -Jduration=600 \
       -l qa/jmeter/results/results.jtl -e -o qa/jmeter/results/report   # load profile
```

Open `qa/jmeter/results/report/index.html` for the HTML dashboard (percentiles, throughput, errors).
`qa/jmeter/results/` is git-ignored.

## Profiles

| Profile | users | ramp (s) | duration (s) | Purpose |
|---|---:|---:|---:|---|
| Smoke | 5 | 10 | 60 | The plan works end to end |
| Load | 25 | 60 | 600 | Expected demo-day concurrency |
| Stress | 100 | 120 | 600 | Find the breaking point |
| Soak | 20 | 60 | 3600 | Leaks and latency drift over time |

Parameters: `users`, `ramp`, `duration`, `think_min_ms`, `think_max_ms`, `api_host`, `api_port`, `kc_host`,
`kc_port`, `kc_client_secret`, `users_file`.

## Targets (local, fake LLM)

| KPI | Target |
|---|---|
| Error rate | < 1% |
| p95 `03 POST chat` | < 800 ms with the fake LLM; re-baseline once the real LLM is wired |
| p95 `02 GET overview` | < 300 ms |
| Throughput | report turns/s per profile |

Correlate with Prometheus (`chat_turn_duration_seconds`, `chat_turns_total`) and Jaeger traces during the run.
Results are offline local measurements, not production numbers.

The plan logs in again when the access token is older than 240 s (the realm issues 300 s tokens); with a single
login per virtual user every request after minute 5 failed with 401 (fixed 2026-09-30).
`poetry run python qa/jmeter/summarize.py <file.jtl>` prints the per-sampler tables below.

## Recorded runs (2026-09-30, trained classifier, one laptop: Docker Desktop + JMeter on the same machine)

**Load — 25 users, 600 s, `LLM_PROVIDER=fake`** (measures our services, not the LLM API): 7,007 samples, 11.7/s.

| Sampler | n | Errors | p50 | p95 | p99 |
|---|---|---|---|---|---|
| Keycloak token | 75 | 0 | 33 ms | 59 ms | 83 ms |
| GET account overview | 2,316 | 0 | 3 ms | 5 ms | 7 ms |
| POST chat, unrecognized charge (ES) | 2,311 | 0 | 29 ms | 70 ms | 152 ms |
| POST chat, out of scope (PT) | 2,305 | 0 | 28 ms | 71 ms | 158 ms |

All targets met (errors 0%, chat p95 70 ms < 800 ms, overview p95 5 ms < 300 ms).

**Stress — 100 users, 600 s, `LLM_PROVIDER=fake`**: 21,369 samples, 35.8/s, **0 errors**, but latency is the
saturation signal.

| Sampler | n | Errors | p50 | p95 | p99 |
|---|---|---|---|---|---|
| Keycloak token | 289 | 0 | 34 ms | 56 ms | 99 ms |
| GET account overview | 7,058 | 0 | 354 ms | 886 ms | 1,803 ms |
| POST chat, unrecognized charge (ES) | 7,030 | 0 | 571 ms | 1,117 ms | 2,243 ms |
| POST chat, out of scope (PT) | 6,992 | 0 | 594 ms | 1,138 ms | 2,153 ms |

Prometheus over the same window: classifier `ml_classify_seconds` p95 248 ms (47 ms single request) and server-side
turn `chat_turn_duration_seconds` p95 1.35 s. Saturation comes from the single ml-service worker (2 torch threads)
and from CPU contention on the host (JMeter runs on the same machine; even the model-free overview slows down).
Next step: several ml-service workers or replicas, and JMeter on a separate machine.

**Load — 25 users, 180 s, `LLM_PROVIDER=deepseek` (Flash)**: 1,754 samples, 9.9/s, 0 errors.

| Sampler | n | Errors | p50 | p95 | p99 |
|---|---|---|---|---|---|
| Keycloak token | 25 | 0 | 32 ms | 40 ms | 54 ms |
| GET account overview | 585 | 0 | 4 ms | 253 ms | 423 ms |
| POST chat, unrecognized charge (ES) | 577 | 0 | 1,017 ms | 1,317 ms | 1,474 ms |
| POST chat, out of scope (PT) | 567 | 0 | 29 ms | 267 ms | 457 ms |

With the real LLM a dispute turn takes about 1 s; the difference with the fake provider is the model call.
Out-of-scope turns cancel the speculative extraction and stay fast.
