#!/usr/bin/env bash
#
# Back up the tarxiv Couchbase bucket (every scope/collection) with cbbackupmgr.
# Intended to be run nightly from cron on the Docker host.
#
# cbbackupmgr runs in the one-shot ``couchbase-backup`` compose service (profile
# ``backup``), which uses the same image as the cluster. The archive holds one
# repo per month (``tarxiv-YYYY-MM``): the first backup in a repo is full, the
# rest are incremental. Repos older than TARXIV_COUCHBASE_KEEP_MONTHS are removed.
#
# Restore instructions: setup/README.md, "Backups & restore".
#
# Usage:
#   scripts/backup_couchbase.sh
#
# Environment (read from setup/.env automatically, or the current environment):
#   TARXIV_COUCHBASE_ADMIN_USERNAME / _PASSWORD   Credentials (need Data Backup & Restore or Full Admin)
#   TARXIV_COUCHBASE_ARCHIVE_DIR   Archive dir, relative paths are from setup/ (default: ./.data/couchbase-archive)
#   TARXIV_COUCHBASE_KEEP_MONTHS   Monthly repos to keep, including the current one (default: 12)
#   TARXIV_COMPOSE_FILE            Compose file to use (default: setup/docker-compose.yml)
#
set -euo pipefail

# --- Locate the repo so the script works regardless of CWD ------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# --- Load setup/.env if present (without clobbering already-set vars) --------
ENV_FILE="${REPO_DIR}/setup/.env"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

# --- Config with defaults ---------------------------------------------------
COMPOSE_FILE="${TARXIV_COMPOSE_FILE:-${REPO_DIR}/setup/docker-compose.yml}"
KEEP_MONTHS="${TARXIV_COUCHBASE_KEEP_MONTHS:-12}"
ARCHIVE_DIR="${TARXIV_COUCHBASE_ARCHIVE_DIR:-./.data/couchbase-archive}"
# Compose resolves relative bind mounts from setup/, so do the same here.
[[ "${ARCHIVE_DIR}" = /* ]] || ARCHIVE_DIR="${REPO_DIR}/setup/${ARCHIVE_DIR}"
CLUSTER="couchbase://couchbase"
REPO="tarxiv-$(date +%Y-%m)"

# cbbackupmgr reads credentials from these, which keeps them out of `ps`.
export CB_USERNAME="${TARXIV_COUCHBASE_ADMIN_USERNAME:?not set}"
export CB_PASSWORD="${TARXIV_COUCHBASE_ADMIN_PASSWORD:?not set}"

log() { printf '[%s] %s\n' "$(date +'%Y-%m-%dT%H:%M:%S%z')" "$*" >&2; }

# --- Pick a compose command -------------------------------------------------
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "${COMPOSE_FILE}")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f "${COMPOSE_FILE}")
else
  log "ERROR: neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

cbbackupmgr() {
  "${COMPOSE[@]}" run --rm -T -e CB_USERNAME -e CB_PASSWORD couchbase-backup "$@"
}

# Create it here rather than letting docker create it as root.
mkdir -p "${ARCHIVE_DIR}"

# --- Monthly repo -------------------------------------------------------------
if [[ ! -d "${ARCHIVE_DIR}/${REPO}" ]]; then
  log "Creating repo ${REPO}"
  cbbackupmgr config -a /backups -r "${REPO}" --include-data tarxiv
fi

# --- Backup -------------------------------------------------------------------
# --purge discards an interrupted previous run instead of resuming it.
log "Backing up bucket 'tarxiv' -> ${ARCHIVE_DIR}/${REPO}"
cbbackupmgr backup -a /backups -r "${REPO}" -c "${CLUSTER}" \
  --purge --no-progress-bar --threads 4

# --- Retention ----------------------------------------------------------------
# ponytail: old months are kept as-is (full + incrementals), not merged into one
# snapshot; add `cbbackupmgr merge` here if the archive gets too big.
now_month=$(( 10#$(date +%Y) * 12 + 10#$(date +%m) ))
for dir in "${ARCHIVE_DIR}"/tarxiv-[0-9][0-9][0-9][0-9]-[0-9][0-9]; do
  [[ -d "${dir}" ]] || continue
  name="$(basename "${dir}")"
  y="${name:7:4}"; m="${name:12:2}"
  if (( now_month - (10#$y * 12 + 10#$m) >= KEEP_MONTHS )); then
    log "Removing repo ${name} (older than ${KEEP_MONTHS} months)"
    cbbackupmgr remove -a /backups -r "${name}"
  fi
done

log "Done. Archive state:"
cbbackupmgr info -a /backups >&2
