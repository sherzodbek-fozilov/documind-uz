#!/bin/bash
# Runs once, when the PostgreSQL volume is empty (docker-entrypoint-initdb.d).
#
# Roles:
#   $POSTGRES_USER (documind)  owns the main database; used only by the one-off jobs
#                              (ingest) in the "ops" service
#   documind_api               used by the API: SELECT only on the main database, so the
#                              evaluation corpus is read-only for the service in every
#                              mode; owns the separate "documind_user" database (uploads)
#
# Changing DOCUMIND_API_DB_PASSWORD later needs ALTER ROLE (see docs/deploy.md).
set -euo pipefail
: "${DOCUMIND_API_DB_PASSWORD:?DOCUMIND_API_DB_PASSWORD must be set}"

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
     -v owner="$POSTGRES_USER" -v maindb="$POSTGRES_DB" \
     -v api_password="$DOCUMIND_API_DB_PASSWORD" <<'SQL'
CREATE ROLE documind_api LOGIN PASSWORD :'api_password';
REVOKE ALL ON DATABASE :"maindb" FROM PUBLIC;
GRANT CONNECT ON DATABASE :"maindb" TO documind_api;
GRANT USAGE ON SCHEMA public TO documind_api;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO documind_api;
-- tables are created later by the ingest job (as the owner)
ALTER DEFAULT PRIVILEGES FOR ROLE :"owner" IN SCHEMA public
    GRANT SELECT ON TABLES TO documind_api;
CREATE DATABASE documind_user OWNER documind_api;
REVOKE ALL ON DATABASE documind_user FROM PUBLIC;
SQL
