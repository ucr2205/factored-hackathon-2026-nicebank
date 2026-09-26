#!/bin/bash
# Runs once on first container start. Creates the pgvector extension and the non-owner application role.
# The app role has no BYPASSRLS, so row-level security policies (added in the schema scripts) always apply.
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<SQL
CREATE EXTENSION IF NOT EXISTS vector;
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${APP_DB_USER}') THEN
    CREATE ROLE ${APP_DB_USER} LOGIN PASSWORD '${APP_DB_PASSWORD}' NOSUPERUSER NOBYPASSRLS;
  END IF;
END
\$\$;
GRANT CONNECT ON DATABASE ${POSTGRES_DB} TO ${APP_DB_USER};
GRANT USAGE ON SCHEMA public TO ${APP_DB_USER};
SQL
