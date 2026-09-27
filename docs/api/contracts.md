# API contracts (v0)

Owner: team lead. Consumers: frontend, evaluation harness (P4). Go structs live in
`backend/internal/contract/contract.go`; TypeScript types in `frontend/src/api/types.ts`. Keep the three in sync.

All endpoints except health require `Authorization: Bearer <Keycloak access token>` (audience `disputes-api`).
The customer identity is taken **only** from the token's `customer_ref` claim, an opaque pseudonym that Postgres
resolves to the bank's `customer_id` inside each transaction (ADR 0003). The bank id never reaches the client.

## Customer

### `POST /api/chat`
```jsonc
// request
{ "session_id": "uuid | null", "message": "No reconozco un cobro de 1.200 del martes", "lang": "es",
  "select_transaction_id": "TRX-... | null" }   // set when the customer picks a candidate card
// response (ChatTurn)
{
  "session_id": "uuid",
  "reply": "text shown to the customer (es/pt)",
  "outcome": "resolve | clarify | abstain | escalate | confirm",
  "candidates": [ { "transaction_id": "TRX-...", "date": "2026-06-09T14:10:00Z", "amount": 1200.0,
                    "currency": "MXN", "merchant": "Tienda General", "city": "Monterrey",
                    "country": "México", "card_last4": "6475" } ],
  "pending_action": { "id": "uuid", "type": "open_dispute_case | block_card",
                      "summary": "text", "requires_step_up": false },
  "actions_verified": [ { "type": "open_dispute_case", "reference": "DSP-000123", "verified_at": "..." } ],
  "case_id": "DSP-000123 | null",
  "handoff_id": "uuid | null",
  "rule_ids": ["DISP-AUTO-01"],
  "trace_id": "hex",
  "latency_ms": 42,
  "cost_usd": 0.0,
  "mode": "system | baseline"
}
```
`?mode=baseline` runs the rules-only baseline (no LLM) on the same workload, for the evaluation harness.

### `POST /api/chat/confirm`
`{ "session_id": "uuid", "action_id": "uuid", "confirm": true }` → `ChatTurn`.
Returns `403 {"error":"step_up_required","acr":"2"}` when the action needs step-up and the token's `acr` is below 2.

### `GET /api/sessions/{id}`
Rehydrates a conversation after a redirect (e.g. step-up): `{ "session_id", "lang", "messages": [{"role","text","at"}], "pending_action" }`.

## Agent console (role `agent` or `supervisor`)

- `GET /api/handoffs?status=open|claimed|closed` → `[HandoffSummary]`
- `GET /api/handoffs/{id}` → `Handoff` (C5 below)
- `POST /api/handoffs/{id}/claim` → `Handoff`
- `GET /api/sessions/{id}/audit` → `[AuditEvent]` `{ "ts", "step", "tool", "summary", "result", "rule_id", "trace_id", "latency_ms" }`

### C5 — Handoff
```json
{ "handoff_id": "uuid", "created_at": "...", "status": "open", "language": "pt",
  "reason": "possible_fraud_high_amount", "priority": "high",
  "customer_request": "one-line summary (masked)",
  "verified_facts": [ { "fact": "Card purchase TRX-... of 950.00 USD at Tienda General on 2026-06-10", "source": "transactions" } ],
  "actions_taken": [ { "action": "block_card", "status": "verified", "reference": "BLK-...", "at": "..." } ],
  "evidence": [ { "type": "policy_rule", "id": "DISP-ESC-01" } ],
  "open_questions": [ "Does the customer still have the physical card?" ],
  "suggested_queue": "fraud_pt",
  "suggested_agents": [ { "agent_id": "AGT-...", "name": "...", "languages": "español, portugués", "specialty": "Fraudes" } ],
  "session_id": "uuid", "trace_id": "hex" }
```
Never includes the raw transcript.

## Supervisor (role `supervisor`)
- `GET /api/admin/config` → active policy version and rules, prompt/template versions, classifier model version.
- `GET /api/admin/summary` → turn counts by outcome and language, p50/p95 latency.

## Errors
`{ "error": "<code>", "message": "..." }` with codes `session_expired` (401), `unauthorized` (401),
`forbidden` (403), `step_up_required` (403), `not_found` (404), `bad_request` (400), `dependency_unavailable` (503).

### `POST /api/handoffs/{id}/identity` (role `agent`)
Returns the customer's identity only to the agent who claimed the handoff; any other caller gets `404`. Every
call writes an `identity / reveal_identity` audit event (POST because it has that side effect).
```jsonc
{ "customer_ref": "cr_...", "first_name": "Lucas", "last_name": "Flores Luna" }
```

## Customer email notifications (outbox)
The orchestrator writes `notifications` rows (`case_opened | card_blocked | handoff_created`, `lang`, `payload`
with verified facts: `case_id, type, merchant, amount, date, card, block_id, reference`) in the action's
transaction; the backend worker delivers them (ADR 0005). Not exposed over HTTP.
