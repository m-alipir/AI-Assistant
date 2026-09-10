#!/bin/sh
set -eu

umask 077
: "${DATABASE_MIGRATION_URL_FILE:?set DATABASE_MIGRATION_URL_FILE}"
: "${AGE_RECIPIENT:?set AGE_RECIPIENT}"
: "${BACKUP_DIR:?set BACKUP_DIR}"

test -f "$DATABASE_MIGRATION_URL_FILE"
mkdir -p "$BACKUP_DIR"
database_url=$(sed 's#^postgresql+asyncpg://#postgresql://#' "$DATABASE_MIGRATION_URL_FILE")
stamp=$(date -u +%Y%m%dT%H%M%SZ)
encrypted="$BACKUP_DIR/postgres-$stamp.dump.age"
plain=$(mktemp "$BACKUP_DIR/.postgres-$stamp.XXXXXX.dump")
cleanup() { rm -f -- "$plain"; }
trap cleanup EXIT HUP INT TERM

pg_dump --dbname="$database_url" --format=custom --no-owner --no-privileges --file="$plain"
age --encrypt --recipient "$AGE_RECIPIENT" --output "$encrypted" "$plain"
sha256sum "$encrypted" > "$encrypted.sha256"
printf '%s\n' "$encrypted"
