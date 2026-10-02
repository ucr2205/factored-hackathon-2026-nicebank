#!/bin/bash
# Usuario y BD propia de Keycloak (despliegue en servidor: deploy/evon/).
# Solo actúa si KEYCLOAK_DB_PASSWORD está definida: en el entorno local (docker-compose.yml de la raíz)
# Keycloak usa start-dev con H2 y este script no hace nada.
# Nota: docker-entrypoint "sourcea" los .sh no ejecutables, así que aquí no se usa `exit`.
set -euo pipefail

if [ -n "${KEYCLOAK_DB_PASSWORD:-}" ]; then
  psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
    -v kc_user="${KEYCLOAK_DB_USER:-keycloak}" -v kc_password="$KEYCLOAK_DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE', :'kc_user', :'kc_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'kc_user') \gexec
SELECT format('CREATE DATABASE %I OWNER %I ENCODING %L', 'keycloak', :'kc_user', 'UTF8')
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak') \gexec
SQL
  echo "03_keycloak_db: BD keycloak lista"
else
  echo "03_keycloak_db: KEYCLOAK_DB_PASSWORD no definida, se omite (entorno local)"
fi
