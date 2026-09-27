#!/bin/bash
# Runs once on first container start. Creates the pgvector extension and the non-owner application role.
# The app role has no BYPASSRLS, so row-level security policies (added in the schema scripts) always apply.
# Values are passed as psql variables and quoted by format(%I/%L), never spliced into the SQL text.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  -v app_user="$APP_DB_USER" -v app_password="$APP_DB_PASSWORD" -v db="$POSTGRES_DB" <<'SQL'
CREATE EXTENSION IF NOT EXISTS vector;
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', :'app_user', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'app_user') \gexec
GRANT CONNECT ON DATABASE :"db" TO :"app_user";
GRANT USAGE ON SCHEMA public TO :"app_user";
SQL
