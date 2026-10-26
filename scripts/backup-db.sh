#!/usr/bin/env bash
set -euo pipefail

CONTAINER="notetask"
DB_PATH="/data/notetask.db"
BACKUP_DIR="/data/backups"
TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${BACKUP_DIR}/notetask-${TIMESTAMP}.db"

docker exec "${CONTAINER}" mkdir -p "${BACKUP_DIR}"

docker exec "${CONTAINER}" python -c "
import sqlite3
src = sqlite3.connect('${DB_PATH}')
dst = sqlite3.connect('${BACKUP_FILE}')
with dst:
    src.backup(dst)
src.close()
dst.close()
print('Backup written to ${BACKUP_FILE}')
"

docker exec "${CONTAINER}" find "${BACKUP_DIR}" -name 'notetask-*.db' -mtime +14 -delete
