#!/bin/bash
# Row-level security. The backend connects as $APP_DB_USER (not the owner, no BYPASSRLS) and sets, per
# transaction, `app.customer_id` from the verified token claim, or `app.staff_role` for agent/supervisor
# requests. Rows are only visible when those settings match.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" -v app_user="$APP_DB_USER" <<SQL
-- Customer-owned tables: only the customer in the current transaction sees their rows.
DO \$\$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['customers','customer_identity','products','transactions','chat_sessions','messages',
                           'pending_actions','dispute_cases','card_blocks','notifications']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY customer_isolation ON %I USING (customer_id = current_setting(''app.customer_id'', true)) '
                   'WITH CHECK (customer_id = current_setting(''app.customer_id'', true))', t);
  END LOOP;
END
\$\$;

-- Staff-visible tables: the owning customer, or a staff request (agent/supervisor role from the token).
DO \$\$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['handoffs','audit_events']
  LOOP
    EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY', t);
    EXECUTE format('ALTER TABLE %I FORCE ROW LEVEL SECURITY', t);
    EXECUTE format('CREATE POLICY owner_or_staff ON %I USING ('
                   'customer_id = current_setting(''app.customer_id'', true) '
                   'OR current_setting(''app.staff_role'', true) IN (''agent'', ''supervisor'')) '
                   'WITH CHECK ('
                   'customer_id = current_setting(''app.customer_id'', true) '
                   'OR current_setting(''app.staff_role'', true) IN (''agent'', ''supervisor''))', t);
  END LOOP;
END
\$\$;

GRANT SELECT ON customers, products, transactions, exchange_rates, service_agents, kb_chunks TO :"app_user";
GRANT UPDATE (product_status) ON products TO :"app_user";
GRANT SELECT, INSERT, UPDATE ON chat_sessions, pending_actions, dispute_cases, card_blocks, handoffs TO :"app_user";
-- Append-only for the app: the audit trail and the chat transcript can be written but never rewritten.
GRANT SELECT, INSERT ON messages, audit_events TO :"app_user";
GRANT INSERT ON notifications TO :"app_user";
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO :"app_user";
-- The app may read its own customer's ciphertext (RLS above), never the ref column or the whole mapping.
GRANT SELECT (customer_id, first_name_ct, last_name_ct, key_version) ON customer_identity TO :"app_user";

-- Pseudonym resolution: the only way from a token's customer_ref to a customer_id. SECURITY DEFINER runs it
-- as the owner, so app_user can translate one ref it already holds but cannot list or scan the mapping.
CREATE FUNCTION resolve_customer(ref text) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = public AS \$\$
  SELECT customer_id FROM customer_identity WHERE customer_ref = ref
\$\$;

-- Reveal-on-claim: an agent gets the customer's (encrypted) identity only for a handoff they claimed, and
-- every reveal is written to the audit trail in the same call. The backend decrypts the names.
CREATE FUNCTION reveal_customer_identity(p_handoff uuid)
RETURNS TABLE (customer_id text, customer_ref text, first_name_ct bytea, last_name_ct bytea, key_version integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS \$\$
#variable_conflict use_column
DECLARE h handoffs%ROWTYPE;
BEGIN
  SELECT * INTO h FROM handoffs WHERE handoff_id = p_handoff;
  IF NOT FOUND OR current_setting('app.staff_role', true) IS DISTINCT FROM 'agent'
     OR h.status <> 'claimed' OR h.claimed_by IS DISTINCT FROM current_setting('app.staff_user', true) THEN
    RETURN;
  END IF;
  INSERT INTO audit_events (session_id, customer_id, step, tool, summary, result, lang)
  VALUES (h.session_id, h.customer_id, 'identity', 'reveal_identity',
          format('customer identity revealed to %s for handoff %s', h.claimed_by, h.handoff_id), 'revealed', h.language);
  RETURN QUERY SELECT i.customer_id, i.customer_ref, i.first_name_ct, i.last_name_ct, i.key_version
    FROM customer_identity i WHERE i.customer_id = h.customer_id;
END
\$\$;

-- Notifier worker: claims due notifications across customers (SKIP LOCKED, so several backends can run it)
-- together with the encrypted contact data it needs, and reports each result. Only these two functions give
-- the worker cross-customer access; app_user still cannot read other customers' rows directly.
CREATE FUNCTION claim_notifications(p_limit integer)
RETURNS TABLE (id bigint, customer_id text, kind text, lang text, payload jsonb, attempts integer,
               email_ct bytea, first_name_ct bytea, key_version integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS \$\$
#variable_conflict use_column
BEGIN
  RETURN QUERY
  WITH due AS (
    SELECT n.id FROM notifications n
    -- 'sending' rows past their lease belong to a worker that died mid-send: retry them.
    WHERE n.status IN ('pending', 'sending') AND n.next_try_at <= now()
    ORDER BY n.next_try_at LIMIT p_limit FOR UPDATE SKIP LOCKED
  ), claimed AS (
    UPDATE notifications n SET status = 'sending', attempts = n.attempts + 1, next_try_at = now() + interval '5 minutes'
    FROM due WHERE n.id = due.id
    RETURNING n.id, n.customer_id, n.kind, n.lang, n.payload, n.attempts
  )
  SELECT c.id, c.customer_id, c.kind, c.lang, c.payload, c.attempts, i.email_ct, i.first_name_ct, i.key_version
  FROM claimed c LEFT JOIN customer_identity i ON i.customer_id = c.customer_id;
END
\$\$;

-- ok = sent; otherwise retry after p_retry_seconds, or fail for good when p_retry_seconds is null.
-- Every outcome is audited without the address (the recipient is personal data).
CREATE FUNCTION finish_notification(p_id bigint, p_ok boolean, p_error text, p_retry_seconds integer)
RETURNS void
LANGUAGE plpgsql SECURITY DEFINER SET search_path = public AS \$\$
DECLARE n notifications%ROWTYPE;
BEGIN
  UPDATE notifications SET
    status = CASE WHEN p_ok THEN 'sent' WHEN p_retry_seconds IS NULL THEN 'failed' ELSE 'pending' END,
    sent_at = CASE WHEN p_ok THEN now() END,
    last_error = CASE WHEN p_ok THEN NULL ELSE left(p_error, 300) END,
    next_try_at = now() + make_interval(secs => coalesce(p_retry_seconds, 0))
  WHERE id = p_id AND status = 'sending'
  RETURNING * INTO n;
  IF NOT FOUND THEN
    RETURN;
  END IF;
  INSERT INTO audit_events (session_id, customer_id, step, tool, summary, result, lang)
  VALUES (n.session_id, n.customer_id, 'notify', 'send_email',
          format('email %s #%s, attempt %s', n.kind, n.id, n.attempts), n.status, n.lang);
END
\$\$;

REVOKE ALL ON FUNCTION resolve_customer(text), reveal_customer_identity(uuid), claim_notifications(integer),
  finish_notification(bigint, boolean, text, integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION resolve_customer(text), reveal_customer_identity(uuid), claim_notifications(integer),
  finish_notification(bigint, boolean, text, integer) TO :"app_user";
SQL
