-- Operational schema (contract C1, v0). Bank data tables hold a demo subset loaded by etl/seed_demo.py
-- until the full loader (P2) replaces it. System tables are written by the backend.

-- ---------- Bank data (organizer synthetic dataset) ----------
-- No names here: identity lives encrypted in customer_identity (see below).
CREATE TABLE customers (
    customer_id      text PRIMARY KEY,
    country          text NOT NULL,
    segment          text NOT NULL,
    detected_accent  text,
    customer_status  text NOT NULL
);

CREATE TABLE products (
    product_id      text PRIMARY KEY,
    customer_id     text NOT NULL REFERENCES customers (customer_id),
    product_type    text NOT NULL,
    card_last4      text,
    currency        text NOT NULL,
    product_status  text NOT NULL,
    credit_limit    numeric(15, 2),
    card_brand      text CHECK (card_brand IN ('visa', 'mastercard', 'amex', 'other'))  -- from the BIN at load
);
CREATE INDEX products_customer_idx ON products (customer_id);

CREATE TABLE transactions (
    transaction_id       text PRIMARY KEY,
    customer_id          text NOT NULL REFERENCES customers (customer_id),
    product_id           text NOT NULL REFERENCES products (product_id),
    transaction_date     timestamptz NOT NULL,
    transaction_type     text NOT NULL,
    amount               numeric(15, 2) NOT NULL,
    currency             text NOT NULL,
    amount_usd           numeric(15, 2),
    merchant_name        text,
    merchant_category    text,
    transaction_country  text,
    transaction_city     text,
    transaction_status   text NOT NULL,
    channel              text,
    origin               text NOT NULL DEFAULT 'organizer_synthetic'
                         CHECK (origin IN ('organizer_synthetic', 'team_generated'))
);
CREATE INDEX transactions_customer_date_idx ON transactions (customer_id, transaction_date DESC);

CREATE TABLE exchange_rates (
    rate_date        date NOT NULL,
    source_currency  text NOT NULL,
    target_currency  text NOT NULL,
    exchange_rate    numeric(18, 8) NOT NULL,
    source           text,
    PRIMARY KEY (rate_date, source_currency, target_currency)
);

CREATE TABLE service_agents (
    agent_id      text PRIMARY KEY,
    first_name    text NOT NULL,
    last_name     text NOT NULL,
    languages     text NOT NULL,
    specialty     text,
    agent_status  text NOT NULL
);

-- ---------- Customer identity (pseudonymization) ----------
-- Tokens carry only customer_ref, a random opaque id. Postgres translates it to customer_id inside each
-- transaction (resolve_customer, see 02_rls.sh), so the application never receives the bank's id from the
-- client. Names are AES-256-GCM ciphertext (nonce || ct || tag) written by the loader and decrypted in the
-- backend with PII_KEY; the associated data binds each value to its row and column
-- ("<customer_id>|<column>|v<key_version>"), so ciphertext copied to another row or column fails to decrypt.
CREATE TABLE customer_identity (
    customer_ref   text PRIMARY KEY,
    customer_id    text NOT NULL UNIQUE REFERENCES customers (customer_id),
    first_name_ct  bytea NOT NULL,
    last_name_ct   bytea NOT NULL,
    email_ct       bytea,             -- contact address for notifications (same scheme)
    key_version    integer NOT NULL DEFAULT 1
);

-- ---------- System tables ----------
-- customer_id defaults to the customer pinned in the current transaction; the backend never sends it.
CREATE TABLE chat_sessions (
    session_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       text NOT NULL DEFAULT current_setting('app.customer_id', true) REFERENCES customers (customer_id),
    lang              text NOT NULL,
    state             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at        timestamptz NOT NULL DEFAULT now(),
    last_activity_at  timestamptz NOT NULL DEFAULT now(),
    closed_at         timestamptz
);

CREATE TABLE messages (
    id           bigserial PRIMARY KEY,
    session_id   uuid NOT NULL REFERENCES chat_sessions (session_id),
    customer_id  text NOT NULL DEFAULT current_setting('app.customer_id', true),
    role         text NOT NULL CHECK (role IN ('customer', 'assistant')),
    text         text NOT NULL,
    outcome      text,
    mode         text,
    latency_ms   integer,
    lang         text,
    created_at   timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX messages_session_idx ON messages (session_id, id);

CREATE TABLE pending_actions (
    action_id    uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id   uuid NOT NULL REFERENCES chat_sessions (session_id),
    customer_id  text NOT NULL DEFAULT current_setting('app.customer_id', true),
    action_type  text NOT NULL CHECK (action_type IN ('open_dispute_case', 'block_card')),
    payload      jsonb NOT NULL,
    status       text NOT NULL DEFAULT 'pending'
                 CHECK (status IN ('pending', 'cancelled', 'executed', 'failed')),
    created_at   timestamptz NOT NULL DEFAULT now(),
    decided_at   timestamptz
);

CREATE SEQUENCE dispute_case_seq START 1000;
CREATE TABLE dispute_cases (
    case_id          text PRIMARY KEY DEFAULT 'DSP-' || lpad(nextval('dispute_case_seq')::text, 6, '0'),
    customer_id      text NOT NULL DEFAULT current_setting('app.customer_id', true),
    transaction_id   text NOT NULL REFERENCES transactions (transaction_id),
    dispute_type     text NOT NULL,
    description      text NOT NULL,
    status           text NOT NULL DEFAULT 'open',
    idempotency_key  text NOT NULL UNIQUE,
    created_at       timestamptz NOT NULL DEFAULT now()
);

CREATE SEQUENCE card_block_seq START 5000;
CREATE TABLE card_blocks (
    block_id     text PRIMARY KEY DEFAULT 'BLK-' || lpad(nextval('card_block_seq')::text, 6, '0'),
    customer_id  text NOT NULL DEFAULT current_setting('app.customer_id', true),
    product_id   text NOT NULL REFERENCES products (product_id),
    reason       text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE handoffs (
    handoff_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  text NOT NULL DEFAULT current_setting('app.customer_id', true),
    session_id   uuid NOT NULL REFERENCES chat_sessions (session_id),
    language     text NOT NULL,
    reason       text NOT NULL,
    priority     text NOT NULL,
    payload      jsonb NOT NULL,
    status       text NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'claimed', 'closed')),
    claimed_by   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    claimed_at   timestamptz
);

CREATE TABLE audit_events (
    id              bigserial PRIMARY KEY,
    ts              timestamptz NOT NULL DEFAULT now(),
    session_id      uuid,
    customer_id     text NOT NULL DEFAULT current_setting('app.customer_id', true),
    step            text NOT NULL,
    tool            text,
    summary         text NOT NULL,
    result          text,
    policy_rule_id  text,
    trace_id        text,
    latency_ms      integer,
    lang            text,
    mode            text,
    -- Where the request came from, for validation and investigations: the HTTP layer's validated IP
    -- (TRUSTED_PROXIES rules), pinned per transaction like app.customer_id. NULL for background work (emails).
    client_ip       inet DEFAULT nullif(current_setting('app.client_ip', true), '')::inet
);
CREATE INDEX audit_session_idx ON audit_events (session_id, id);

-- Outbox for customer notifications. Rows are written in the same transaction as the case, block or handoff
-- they announce, so a notification exists if and only if the action committed. The notifier worker claims
-- them with claim_notifications() (02_rls.sh) and records each attempt; payload holds verified facts only.
CREATE TABLE notifications (
    id           bigserial PRIMARY KEY,
    customer_id  text NOT NULL DEFAULT current_setting('app.customer_id', true),
    session_id   uuid REFERENCES chat_sessions (session_id),
    kind         text NOT NULL CHECK (kind IN ('case_opened', 'card_blocked', 'handoff_created')),
    lang         text NOT NULL,
    payload      jsonb NOT NULL,
    status       text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sending', 'sent', 'failed')),
    attempts     integer NOT NULL DEFAULT 0,
    last_error   text,
    created_at   timestamptz NOT NULL DEFAULT now(),
    next_try_at  timestamptz NOT NULL DEFAULT now(),
    sent_at      timestamptz
);
CREATE INDEX notifications_pending_idx ON notifications (next_try_at) WHERE status = 'pending';

CREATE TABLE kb_chunks (
    id         bigserial PRIMARY KEY,
    doc_id     text NOT NULL,
    lang       text NOT NULL,
    section    text,
    text       text NOT NULL,
    embedding  vector(384),
    version    text NOT NULL
);
