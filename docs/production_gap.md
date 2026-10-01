# Production gap

What separates this hackathon build from a system a bank could run. Ordered by risk.

## 1. Data and models

| Gap | Today | Needed for production |
|---|---|---|
| Dispute language | The organizer data has no dispute text; the classifier is trained on a team-generated, template-based ES/PT corpus (`docs/ml_labels.md`). | Train and validate on real, consented customer messages; label with domain experts; double labeling with agreement measured. |
| Independent evaluation | Held-out cases are anchored on real rows, but the sentences were written by the same team (and AI assistant) that wrote the training corpus. An overlap check guards against near-duplicates only. | A blind test set written by people outside the ML team, plus shadow-mode evaluation on live traffic before any automation. |
| Weakest behavior | Paraphrases of "wrong amount" and "not received" often abstain (the assistant asks instead of acting): 9 of 14 test errors. Safe, but lower automation. | More paraphrase coverage; error analysis on production logs; per-type thresholds. |
| Drift and retraining | Model versions are pinned (`model_version`, e5 revision, prompt version); no monitoring of input drift or abstention rate over time. | Dashboards and alerts on abstention, label mix, escalation rate per segment; scheduled re-evaluation and retraining with approval gates. |
| Fairness | The classifier sees only masked text, never segment or country; per-segment accuracy is reported but samples are small (11–53 cases per group). | Larger evaluation per segment, country and accent; fairness review before each model release. |
| Retrieval | Policy + FAQ are indexed in `kb_chunks` (recall@3 0.93 on 30 questions) but the chat does not use retrieval yet. | Wire retrieval into answers to policy questions with citations; evaluate faithfulness. |
| AI-written replies | Off (`LLM_COMPOSE=template`): the rewrite kept facts but dropped the decisive sentence in 3 of 11 replies. | Outcome-aware guard (required key phrase per intent) before enabling it. |

## 2. Third parties and compliance

- **External LLM.** DeepSeek receives masked text only, but a bank would need a data-processing agreement,
  data-residency review and a vendor risk assessment, or a self-hosted model. Flash is primary, Pro is fallback,
  and the local fake is the last resort; a provider outage degrades extraction quality, it does not stop the flow.
- **Card networks.** Opening a "case" writes to a local table; there is no integration with chargeback systems,
  card processors or the core banking ledger. Card blocks are simulated.
- **Regulation.** Dispute deadlines and thresholds come from a team-generated policy (`origin: team_generated`), not
  from a bank's legal rules per country. Consumer-protection timelines, required disclosures and record retention
  must be reviewed per jurisdiction.

## 3. Security and operations

| Gap | Today | Needed |
|---|---|---|
| Secrets | `.env` on the developer machine; `PII_KEY` is a local key. | Secret manager, key management service with rotation, no shared credentials. |
| Test identities | Demo customers with known TOTP seeds, load-test users without TOTP, the `eval-harness` client with direct grants. | Remove all test realms, users and the direct-grant client; enforce MFA policies in the identity provider. |
| Transport | HTTP on localhost; Keycloak in dev mode. | TLS everywhere, HSTS, Keycloak in production mode behind a hardened proxy, public URLs for email links. |
| Availability | Single Docker host; one instance of each service; no backups configured. | Managed Postgres with replicas, point-in-time recovery, multiple backend and ml-service replicas, health-based routing. |
| Abuse | No rate limiting per customer or IP. | Rate limits and bot protection on login and chat. |
| Access reviews | Agent and supervisor roles exist; reveals and closures are audited. | Periodic access reviews, retention policy for audit and messages, SIEM integration. |

## 4. Capacity

Measured on one laptop (`qa/jmeter/README.md`): 25 concurrent users with DeepSeek Flash, 0 errors, dispute turn
p50 1.0 s / p95 1.3 s (the model call is most of it). With the fake LLM, 25 users: chat p95 70 ms; 100 users: still
0 errors but p95 1.1 s, with the classifier's p95 rising from 47 ms to 248 ms (one worker, CPU only) and host CPU
contention. Production needs several ml-service replicas, autoscaling on latency, and load tests from separate
machines. These are not production estimates.

## 5. Product

- Channels: web chat only (no WhatsApp, voice or mobile app); notifications by email only.
- Languages: Spanish and Brazilian Portuguese.
- The agent console closes handoffs with accepted/rejected and a note; there is no case-management workflow
  (SLAs, reassignment, refunds executed by back office) behind it.
