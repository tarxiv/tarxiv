#!/usr/bin/env bash
#
# Back up the tarxiv Postgres database to a compressed logical dump, with
# rotation. Intended to be run from cron / a systemd timer on the Docker host.
#
# It shells into the running ``postgres`` compose service and runs ``pg_dump``
# in custom format (``-Fc``), so the resulting file is compressed and can be
# restored selectively/in parallel with ``pg_restore``.
#
# Usage:
#   scripts/backup_postgres.sh [backup_dir]
#
# Rotation follows a grandfather-father-son (GFS) scheme:
#   * every backup from the last week is kept (daily),
#   * then one backup per week is kept back to 3 months,
#   * then one backup per month is kept back to a year,
#   * anything older than a year is removed.
#
# Environment (read from setup/.env automatically, or the current environment):
#   TARXIV_POSTGRES_USER       Postgres user           (default: tarxiv)
#   TARXIV_POSTGRES_DB         Database to dump         (default: tarxiv)
#   TARXIV_BACKUP_DIR          Where to write dumps     (default: ./.data/postgres/backups)
#   TARXIV_KEEP_DAILY_DAYS     Keep all dumps newer than N days   (default: 7)
#   TARXIV_KEEP_WEEKLY_DAYS    Keep weekly dumps up to N days      (default: 90)
#   TARXIV_KEEP_MONTHLY_DAYS   Keep monthly dumps up to N days     (default: 365)
#   TARXIV_COMPOSE_FILE        Compose file to use      (default: setup/docker-compose.yml)
#   TARXIV_POSTGRES_SERVICE    Compose service name     (default: postgres)
#
# Restore a dump with:
#   docker compose -f setup/docker-compose.yml exec -T postgres \
#     pg_restore -U tarxiv -d tarxiv --clean --if-exists < backup.dump
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
PG_SERVICE="${TARXIV_POSTGRES_SERVICE:-postgres}"
PG_USER="${TARXIV_POSTGRES_USER:-tarxiv}"
PG_DB="${TARXIV_POSTGRES_DB:-tarxiv}"
BACKUP_DIR="${1:-${TARXIV_BACKUP_DIR:-${REPO_DIR}/.data/postgres/backups}}"
KEEP_DAILY_DAYS="${TARXIV_KEEP_DAILY_DAYS:-7}"
KEEP_WEEKLY_DAYS="${TARXIV_KEEP_WEEKLY_DAYS:-90}"
KEEP_MONTHLY_DAYS="${TARXIV_KEEP_MONTHLY_DAYS:-365}"

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
DEST="${BACKUP_DIR}/${PG_DB}-${TIMESTAMP}.dump"
TMP="${DEST}.partial"

log() { printf '[%s] %s\n' "$(date +'%Y-%m-%dT%H:%M:%S%z')" "$*" >&2; }

# Days since 1970-01-01 for a civil (Y M D) date, using Howard Hinnant's
# days_from_civil algorithm. Pure integer arithmetic so it needs no GNU date
# and works identically on the macOS/BSD and Linux hosts. ``10#`` forces base-10
# so zero-padded months/days (e.g. 06, 09) aren't misread as octal.
days_from_civil() {
  local y=$((10#$1)) m=$((10#$2)) d=$((10#$3))
  if (( m <= 2 )); then y=$(( y - 1 )); fi
  local era=$(( (y >= 0 ? y : y - 399) / 400 ))
  local yoe=$(( y - era * 400 ))
  local mp=$(( m > 2 ? m - 3 : m + 9 ))
  local doy=$(( (153 * mp + 2) / 5 + d - 1 ))
  local doe=$(( yoe * 365 + yoe / 4 - yoe / 100 + doy ))
  echo $(( era * 146097 + doe - 719468 ))
}

# GFS rotation over "${dir}/${prefix}-YYYYMMDD-HHMMSS.<ext>" files. Iterates
# newest-first; since the files are date-sorted, every dump in a given week (or
# month) is contiguous, so tracking only the last-kept week/month bucket is
# enough to keep the first (newest) of each and drop the rest. This avoids
# associative arrays so it also runs on the bash 3.2 shipped with macOS.
gfs_rotate() {
  local dir="$1" prefix="$2" ext="$3"
  local today_day
  today_day="$(days_from_civil "$(date +%Y)" "$(date +%m)" "$(date +%d)")"

  local last_week="" last_month=""
  local f base fy fm fd file_day age wk mo
  while IFS= read -r f; do
    [[ -e "$f" ]] || continue
    base="$(basename "$f")"
    if [[ "$base" =~ -([0-9]{4})([0-9]{2})([0-9]{2})-[0-9]{6}\.${ext}$ ]]; then
      fy="${BASH_REMATCH[1]}"; fm="${BASH_REMATCH[2]}"; fd="${BASH_REMATCH[3]}"
    else
      continue
    fi
    file_day="$(days_from_civil "$fy" "$fm" "$fd")"
    age=$(( today_day - file_day ))

    if (( age <= KEEP_DAILY_DAYS )); then
      continue  # daily tier: keep everything from the last week
    elif (( age <= KEEP_WEEKLY_DAYS )); then
      wk=$(( file_day / 7 ))
      if [[ "$wk" == "$last_week" ]]; then
        rm -f -- "$f" && log "Rotated (weekly duplicate): $base"
      else
        last_week="$wk"
      fi
    elif (( age <= KEEP_MONTHLY_DAYS )); then
      mo=$(( 10#$fy * 12 + 10#$fm ))
      if [[ "$mo" == "$last_month" ]]; then
        rm -f -- "$f" && log "Rotated (monthly duplicate): $base"
      else
        last_month="$mo"
      fi
    else
      rm -f -- "$f" && log "Rotated (older than ${KEEP_MONTHLY_DAYS}d): $base"
    fi
  done < <(ls -1 "${dir}/${prefix}-"*".${ext}" 2>/dev/null | sort -r)
}

mkdir -p "${BACKUP_DIR}"

# --- Pick a compose command -------------------------------------------------
if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose -f "${COMPOSE_FILE}")
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose -f "${COMPOSE_FILE}")
else
  log "ERROR: neither 'docker compose' nor 'docker-compose' is available."
  exit 1
fi

# --- Sanity-check the DB is reachable before we start -----------------------
if ! "${COMPOSE[@]}" exec -T "${PG_SERVICE}" pg_isready -U "${PG_USER}" >/dev/null 2>&1; then
  log "ERROR: Postgres service '${PG_SERVICE}' is not ready. Is the stack up?"
  exit 1
fi

# --- Dump -------------------------------------------------------------------
# Write to a .partial file first so a failed/interrupted dump never looks like
# a usable backup. -T disables TTY allocation so this is cron-safe.
log "Dumping '${PG_DB}' as '${PG_USER}' -> ${DEST}"
if "${COMPOSE[@]}" exec -T "${PG_SERVICE}" \
     pg_dump -U "${PG_USER}" -Fc "${PG_DB}" > "${TMP}"; then
  mv "${TMP}" "${DEST}"
  log "Backup complete: ${DEST} ($(du -h "${DEST}" | cut -f1))"
else
  rm -f "${TMP}"
  log "ERROR: pg_dump failed; no backup written."
  exit 1
fi

# --- Rotate -----------------------------------------------------------------
# GFS rotation. Only matches our own naming pattern so nothing else in the
# directory is touched.
log "Rotating (GFS: ${KEEP_DAILY_DAYS}d daily / ${KEEP_WEEKLY_DAYS}d weekly / ${KEEP_MONTHLY_DAYS}d monthly)"
gfs_rotate "${BACKUP_DIR}" "${PG_DB}" "dump"

log "Done. Current backups:"
ls -1t "${BACKUP_DIR}/${PG_DB}-"*.dump 2>/dev/null | head -n 20 >&2 || true
