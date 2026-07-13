#!/usr/bin/env bash
set -euo pipefail

: "${RESTORE_DATABASE_URL:?RESTORE_DATABASE_URL is required}"
: "${BACKUP_PATH:?BACKUP_PATH is required}"
: "${CONFIRM_RESTORE:?Set CONFIRM_RESTORE=YES after verifying the target database}"

if [[ "${CONFIRM_RESTORE}" != "YES" ]]; then
  printf '%s\n' "Restore cancelled: CONFIRM_RESTORE must equal YES" >&2
  exit 2
fi

shasum -a 256 -c "${BACKUP_PATH}.sha256"
pg_restore \
  --dbname="${RESTORE_DATABASE_URL}" \
  --clean \
  --if-exists \
  --no-owner \
  "${BACKUP_PATH}"
