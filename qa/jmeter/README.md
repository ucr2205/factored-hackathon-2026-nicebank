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

## Last recorded run (2026-09-27, smoke profile: 5 users, 60 s, LLM = DeepSeek Flash)

| Sampler | n | Errors | p50 | p95 |
|---|---|---|---|---|
| Keycloak token | 5 | 0 | 115 ms | 116 ms |
| GET account overview | 38 | 0 | 5 ms | 9 ms |
| POST chat, unrecognized charge (ES) | 38 | 0 | 970 ms | 1,299 ms |
| POST chat, out of scope (PT) | 34 | 0 | 12 ms | 138 ms |

With `LLM_PROVIDER=fake` the chat samplers answer in ~15-65 ms; the difference is the model call.
