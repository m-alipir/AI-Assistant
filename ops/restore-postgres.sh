#!/bin/sh
set -eu

umask 077
: "${DATABASE_MIGRATION_URL_FILE:?set DATABASE_MIGRATION_URL_FILE}"
: "${AGE_IDENTITY_FILE:?set AGE_IDENTITY_FILE}"
: "${ENCRYPTED_BACKUP:?set ENCRYPTED_BACKUP}"
: "${RESTORE_CONFIRM_ISOLATED:?set RESTORE_CONFIRM_ISOLATED=yes only for an isolated restore target}"

test "$RESTORE_CONFIRM_ISOLATED" = "yes"
test -f "$DATABASE_MIGRATION_URL_FILE"
test -f "$AGE_IDENTITY_FILE"
test -f "$ENCRYPTED_BACKUP"
test -f "$ENCRYPTED_BACKUP.sha256"
sha256sum --check "$ENCRYPTED_BACKUP.sha256"

database_url=$(sed 's#^postgresql+asyncpg://#postgresql://#' "$DATABASE_MIGRATION_URL_FILE")
plain=$(mktemp "${TMPDIR:-/tmp}/postgres-restore.XXXXXX.dump")
cleanup() { rm -f -- "$plain"; }
trap cleanup EXIT HUP INT TERM

age --decrypt --identity "$AGE_IDENTITY_FILE" --output "$plain" "$ENCRYPTED_BACKUP"
pg_restore --dbname="$database_url" --exit-on-error --no-owner --no-privileges "$plain"
