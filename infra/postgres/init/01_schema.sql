-- Operational schema (contract C1, v0). Bank data tables hold a demo subset loaded by etl/seed_demo.py
-- until the full loader (P2) replaces it. System tables are written by the backend.

-- ---------- Bank data (organizer synthetic dataset) ----------
CREATE TABLE customers (
    customer_id      text PRIMARY KEY,
    first_name       text NOT NULL,
    last_name        text NOT NULL,
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
    credit_limit    numeric(15, 2)
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

-- ---------- System tables ----------
CREATE TABLE chat_sessions (
    session_id        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id       text NOT NULL REFERENCES customers (customer_id),
    lang              text NOT NULL,
    state             jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at        timestamptz NOT NULL DEFAULT now(),
    last_activity_at  timestamptz NOT NULL DEFAULT now(),
    closed_at         timestamptz
);

CREATE TABLE messages (
    id           bigserial PRIMARY KEY,
    session_id   uuid NOT NULL REFERENCES chat_sessions (session_id),
    customer_id  text NOT NULL,
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
    customer_id  text NOT NULL,
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
    customer_id      text NOT NULL,
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
    customer_id  text NOT NULL,
    product_id   text NOT NULL REFERENCES products (product_id),
    reason       text NOT NULL,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE handoffs (
    handoff_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id  text NOT NULL,
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
    customer_id     text NOT NULL,
    step            text NOT NULL,
    tool            text,
    summary         text NOT NULL,
    result          text,
    policy_rule_id  text,
    trace_id        text,
    latency_ms      integer,
    lang            text,
    mode            text
);
CREATE INDEX audit_session_idx ON audit_events (session_id, id);

CREATE TABLE kb_chunks (
    id         bigserial PRIMARY KEY,
    doc_id     text NOT NULL,
    lang       text NOT NULL,
    section    text,
    text       text NOT NULL,
    embedding  vector(384),
    version    text NOT NULL
);
