-- 2026-10-01: record the validated client IP on every audit event (validation and investigations).
-- Fresh databases get it from init/01_schema.sql; run this once on an existing one (as the owner):
--   docker compose exec -T postgres sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < infra/postgres/migrations/001_audit_client_ip.sql
ALTER TABLE audit_events
    ADD COLUMN IF NOT EXISTS client_ip inet DEFAULT nullif(current_setting('app.client_ip', true), '')::inet;
