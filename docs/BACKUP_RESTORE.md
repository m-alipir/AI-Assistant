# Encrypted PostgreSQL backup and restore

These commands are an operator runbook for a Linux VPS. Production recovery was validated on
2026-09-20 with an off-host age identity and an isolated PG17 restore target.

## Recovery identity management

- Generate the age identity only on a trusted off-host operator device. Keep the identity file
  outside the repository and outside the encrypted-backup tree with directory mode `700` and file
  mode `600`. The current operator convention is
  `~/.local/share/personal-intelligence-recovery/production-backup.agekey`; this records a location
  expectation, not the private key.
- Never copy the private identity to the VPS, application containers, backup directory, logs,
  tickets, prompts, or Git. Keep it separate from `APP_ENCRYPTION_KEY`; rotating one must not replace
  or reveal the other. A second protected offline/password-manager copy is recommended for device
  loss, under the same access restrictions.
- Derive the public recipient with `age-keygen -y <identity-file>`. Only this public recipient may be
  provisioned on the VPS, currently at `/etc/personal-intelligence/backup_age_recipient`. Public
  recipients are configuration, not recovery secrets.
- Store encrypted backup artifacts separately from the identity. The VPS staging location is
  `/var/backups/personal-intelligence`; copy each `.dump.age` and `.sha256` pair to protected
  off-host backup storage and verify the checksum there.

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

When the identity must remain off the VPS, decrypt on the trusted operator device and stream the
plaintext archive over SSH directly into a disposable restore container. The container must have no
production volume or network, and its data directory should use tmpfs. The private identity never
crosses SSH. Remove the disposable container after verification so its plaintext archive and
restored database do not persist; retain the encrypted backup and checksum.

Production acceptance was observed on 2026-09-20: off-host checksum validation and decryption
produced a PG custom archive; a network-disabled, tmpfs-backed PG17 container restored it through
revision `20260914_0027`; 34 public tables and representative aggregate counts matched production;
the disposable plaintext/restore target was removed while production remained healthy. Record only
dates, revision IDs, durations, and aggregate results; never record DSNs, tokens, email data,
decrypted dump contents, or the private identity.
