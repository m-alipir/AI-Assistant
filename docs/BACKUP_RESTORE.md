# Encrypted PostgreSQL backup and restore

These commands are an operator runbook for a Linux VPS. The repository tests only verify the
scripts and configuration offline; every real backup/restore acceptance item remains
`pending VPS validation`.

## Backup

Use the migration/owner DSN file, not the runtime application role. Keep the age private identity
off the VPS and store it separately from encrypted backups and the Fernet application key.

```sh
export DATABASE_MIGRATION_URL_FILE=/run/secrets/database_migration_url
export AGE_RECIPIENT='age1...'
export BACKUP_DIR=/var/backups/personal-intelligence
./ops/backup-postgres.sh
```

Copy both `.dump.age` and `.dump.age.sha256` to protected off-host storage. The script creates a
custom-format dump with no ownership/ACL records, encrypts it before completion, hashes the
encrypted artifact, and removes its temporary plaintext on success, failure, or interruption.

## Isolated restore drill

Create an empty database on an isolated host/network with no production clients. Put its
migration/owner DSN in a protected file. Never point the restore script at production; the explicit
confirmation variable is a guard, not proof of isolation.

```sh
export DATABASE_MIGRATION_URL_FILE=/run/secrets/isolated_restore_database_url
export AGE_IDENTITY_FILE=/run/secrets/backup_age_identity
export ENCRYPTED_BACKUP=/var/backups/personal-intelligence/postgres-YYYYMMDDTHHMMSSZ.dump.age
export RESTORE_CONFIRM_ISOLATED=yes
./ops/restore-postgres.sh
alembic current
alembic upgrade head
```

Acceptance remains `pending VPS validation` until an operator verifies checksum validation,
successful restore, Alembic head, representative provenance queries, retention compatibility,
recovery time, and removal of the isolated database. Record only dates, durations, revision IDs,
and aggregate results; never record DSNs, tokens, email data, or decrypted dump contents.
