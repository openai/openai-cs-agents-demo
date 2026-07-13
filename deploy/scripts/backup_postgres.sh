#!/usr/bin/env bash
set -euo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

backup_dir="${BACKUP_DIR:-./backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="${backup_dir}/enterprise-agent-${timestamp}.dump"

umask 077
mkdir -p "${backup_dir}"
pg_dump --dbname="${DATABASE_URL}" --format=custom --no-owner --file="${backup_path}"
shasum -a 256 "${backup_path}" > "${backup_path}.sha256"

printf '%s\n' "${backup_path}"
