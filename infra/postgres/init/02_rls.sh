#!/bin/bash
# Row-level security. The backend connects as $APP_DB_USER (not the owner, no BYPASSRLS) and sets, per
# transaction, `app.customer_id` from the verified token claim, or `app.staff_role` for agent/supervisor
# requests. Rows are only visible when those settings match.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
-- Customer-owned tables: only the customer in the current transaction sees their rows.
DO \$\$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['customers','products','transactions','chat_sessions','messages',
                           'pending_actions','dispute_cases','card_blocks']
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

GRANT SELECT ON customers, products, transactions, exchange_rates, service_agents, kb_chunks TO ${APP_DB_USER};
GRANT UPDATE (product_status) ON products TO ${APP_DB_USER};
GRANT SELECT, INSERT, UPDATE ON chat_sessions, messages, pending_actions, dispute_cases, card_blocks,
      handoffs, audit_events TO ${APP_DB_USER};
GRANT USAGE ON ALL SEQUENCES IN SCHEMA public TO ${APP_DB_USER};
SQL
