# ADR 0003 — Pseudonymized customer identity

Status: accepted (2026-09-27, before the C1 freeze)

## Context

Access tokens carried the bank's `customer_id`, which is readable by anyone holding the token (the browser, logs of
any proxy). Customer names were stored in plain text next to the bank data, and nothing distinguished "the code can
query this customer's rows" from "the code knows who this person is". Human agents need a customer's identity only
to contact them, and only for cases they own.

## Decision

1. **Opaque subject.** Keycloak carries `customer_ref` (`cr_` + 24 random URL-safe characters) instead of
   `customer_id`. `store.WithCustomer` calls `resolve_customer(ref)`, a `SECURITY DEFINER` function, inside the
   transaction and pins `app.customer_id` from its result. `app_user` cannot read the mapping table's ref column,
   so it can translate a ref it already holds but cannot list or scan the mapping. An unknown ref pins nothing
   and the request fails with 403.
2. **The backend never sends the bank id.** System tables default `customer_id` to
   `current_setting('app.customer_id')`; row-level security's `WITH CHECK` still enforces it.
3. **Encrypted names.** `customers` has no names. `customer_identity` stores `first_name`/`last_name` as
   AES-256-GCM ciphertext (`nonce || ct || tag`) with associated data `"<customer_id>|<column>|v<key_version>"`,
   so ciphertext moved to another row or column fails authentication. The key is `PII_KEY` (environment only;
   `make env` generates a local one). The backend decrypts names in memory only to greet the customer and to mask
   names before any text reaches a model.
4. **Reveal on claim.** Handoffs contain no identity. `POST /api/handoffs/{id}/identity` calls
   `reveal_customer_identity(handoff)`, which returns the ciphertext only if the caller is the agent who claimed
   that handoff (`app.staff_user`), and writes an `identity / reveal_identity` audit event in the same call.

## Consequences

- Changing `PII_KEY` requires `make seed` (demo data is re-encrypted); a production system would use envelope
  encryption with a KMS and per-version keys (`key_version` is already in the schema).
- Lookups by name or document are impossible without a blind index; none is needed today. If one is added, use
  HMAC-SHA256 with its own key over normalized values, never a plain hash or the JWT key.
- Pattern adapted from the odonto-back project (encrypted identity fields, blind triage queue with reveal after
  claim), fixing its weaknesses: associated data on every field, no identity in tokens, no reused keys, and the
  reveal check and audit inside the database.
