\set ON_ERROR_STOP on

-- Run once as the database owner before the dedicated migration service.
-- Supply values with psql -v runtime_role=... -v runtime_password=...
SELECT format('CREATE ROLE %I LOGIN', :'runtime_role')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'runtime_role') \gexec

SELECT format(
  'ALTER ROLE %I PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION',
  :'runtime_role', :'runtime_password'
) \gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
SELECT format('GRANT CONNECT ON DATABASE %I TO %I', current_database(), :'runtime_role') \gexec
SELECT format('GRANT USAGE ON SCHEMA public TO %I', :'runtime_role') \gexec
SELECT format(
  'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO %I',
  :'runtime_role'
) \gexec
SELECT format(
  'GRANT USAGE, SELECT, UPDATE ON ALL SEQUENCES IN SCHEMA public TO %I',
  :'runtime_role'
) \gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO %I',
  :'runtime_role'
) \gexec
SELECT format(
  'ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT, UPDATE ON SEQUENCES TO %I',
  :'runtime_role'
) \gexec
