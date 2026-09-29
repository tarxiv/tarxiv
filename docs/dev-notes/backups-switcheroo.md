# Plan: generic Couchbase backups (cbbackupmgr + scope-agnostic JSON dump)

> **For Claude running on a laptop checkout of `tarxiv-dev`.** This plan was written on the
> production server, which you can't reach. The facts under "Server facts" were checked
> there and can't be re-derived from the repo. Everything else can be verified locally.
> Follow `AGENTS.md`: use `uv`, run the Ruff/pytest checks, and ask the user before commits or pushes.
> The server also has an untracked `scripts/backup.crontab` (the live crontab). It is not in
> git, so edit `scripts/backup.crontab.example` only.

## Context
`scripts/db_utils.py --backup` only dumps two hardcoded layouts from `SCHEMA_LAYOUTS`
(`objects` and legacy `tns`), using ~400k sequential KV gets. The live bucket has more scopes
than that, so a restore today would silently lose data. The goal is a backup that covers
whatever scopes exist, now and in future, plus clear restore docs.

### Server facts (checked 2026-09-29 on the prod host)
- Couchbase **8.0.0-3777 Enterprise** (`couchbase:latest` image). `cbbackupmgr`, `cbexport` and `cbimport` are in `/opt/couchbase/bin`.
- Cluster services are `data,index,query,fts,analytics`, with **no backup service**. So use cron + `cbbackupmgr`, not the in-server Backup Service.
- Live `tarxiv` bucket scopes:

| scope | collections | in current backup? |
|---|---|---|
| objects | meta, lightcurves | yes |
| tns | objects, lightcurves | yes |
| misc | idx, active_settings | **no**. `misc.idx` holds the txv-id counters (`TarxivDB.get_txv_id`), so restoring without it risks duplicate IDs |
| xmatch | alerts, hits, idx | **no** |
| _default / _system | – | skip `_system` |

- `setup/init_server.sh` creates `tns`, `objects` and `xmatch`, but **not `misc`**. The code uses `misc` (`tarxiv/pipeline.py:140`, `tarxiv/database.py:279`). Add `misc.idx` and `misc.active_settings` creation to `init_server.sh` so the local stack matches prod and restores into a fresh cluster work.
- Prod backup dirs: `/data/db_backup/couchbase` and `/data/db_backup/postgres`.
- Python SDK is `couchbase==4.5.0` (`uv.lock`), which supports KV range scans (`RangeScan`).

Decision (user): `cbbackupmgr` is the primary nightly backup. `db_utils.py` also becomes
scope-agnostic, for portable JSON dumps and the example dataset.

## 1. `cbbackupmgr` runner service — `setup/docker-compose.yml`
Add a one-shot service under a new `backup` profile. The live `couchbase` container is never recreated:
```yaml
couchbase-backup:
  image: couchbase:latest          # same image => cbbackupmgr matches the cluster version
  profiles: [backup]
  entrypoint: ["/opt/couchbase/bin/cbbackupmgr"]
  volumes:
    - ${TARXIV_COUCHBASE_BACKUP_DIR:-../.data/couchbase/backups}:/backups:Z
  networks: [tarxiv_net]
```
Add `TARXIV_COUCHBASE_BACKUP_DIR` and `TARXIV_COUCHBASE_KEEP_MONTHS` to `setup/.env.sample`. Add the `backup` profile to the profile lists in `AGENTS.md` and `setup/README.md`.

## 2. New `scripts/backup_couchbase.sh`
Copy the structure of `scripts/backup_postgres.sh`: repo discovery, `setup/.env` loading, `docker compose` / `docker-compose` detection, `log()`, `set -euo pipefail`.
- Run `cbbackupmgr` via `"${COMPOSE[@]}" run --rm -T couchbase-backup <subcommand> ...`, with the cluster at `couchbase://couchbase`. Use `-u/-p` from `TARXIV_COUCHBASE_ADMIN_*`, since `cbbackupmgr` needs Full Admin or Data Backup & Restore.
- **One repo per month**, `tarxiv-YYYY-MM`. If it's missing, run `config -a /backups -r <repo> --include-data tarxiv`. The first backup in a repo is full; later ones are incremental.
- Nightly: `backup -a /backups -r <repo> -c couchbase://couchbase -u .. -p .. --purge --no-progress-bar --threads 4`. `--purge` drops an interrupted previous run, in place of the `.partial` pattern.
- Retention: keep the current and previous month at daily granularity. For older repos, `merge` all backups into one (a monthly snapshot). `remove` repos older than `TARXIV_COUCHBASE_KEEP_MONTHS` (default 12).
- End with `cbbackupmgr info -a /backups` so the cron log shows the archive state.
- The header comment points to the README restore section (step 6).
- **Verify every flag against `docker compose run --rm couchbase-backup <cmd> --help`** before relying on it (`backup`, `merge`, `remove`, `restore`, `info`). Flags were chosen from Couchbase 7.x/8.x docs, not tested.

## 3. Scope-agnostic `scripts/db_utils.py`
Keep `--dump` / `--load` / `--legacy`, which use the example-dataset meta+lc format (`SCHEMA_LAYOUTS`), unchanged. Replace the backup path:
- `list_collections(db, include=None)`: use `db.conn.collections().get_all_scopes()` (`db.conn` is the bucket, see `tarxiv/database.py:55`). Skip `_system`, and skip `_default._default` when it's empty. Return `[(scope, collection), ...]`, optionally filtered by `--scope` glob(s).
- `dump_collections(filename, collections)`: stream `bucket.scope(s).collection(c).scan(RangeScan())` for each collection. This is a KV range scan: no primary index needed, and much faster than per-id gets. Write **JSON Lines**, one `{"scope","collection","id","doc"}` per line, gzipped if the name ends in `.gz`. If a collection's scan times out, retry it with backoff (reuse the `GET_ATTEMPTS` / `_TIMEOUT_EXCEPTIONS` idea). If it still fails, report the collection as failed.
- `load_collections(filename, scope_map=None)`: stream lines into `db.upsert(id, doc, scope, collection)`. `--map old=new` remaps scopes, like `cbbackupmgr --map-data`. Add a `--load-all` CLI flag.
- `--backup`: one generic dump to `couchbase-tarxiv-YYYYMMDD-HHMMSS.jsonl.gz`. Write a `.partial` file, then `os.replace`, then `_gfs_rotate`. Widen `_BACKUP_STAMP_RE` to match `.jsonl` / `.jsonl.gz`. Any failed collection means a non-zero exit from `main`.
- Delete the `layouts` loop in `backup_couchbase`. `SCHEMA_LAYOUTS` stays, but only for `--dump`/`--load`. Update the module docstring.
- Check that the pipeline user's role in `setup/init_server.sh` (user-manage, around line 165) can read `misc` and `xmatch`. If it can't, add a `--admin` option or document using admin creds.

## 4. Cron — `scripts/backup.crontab.example`
- 03:00 daily: `scripts/backup_couchbase.sh` (primary).
- Sunday 04:00, optional: `db_utils.py --backup`, a portable, version-independent JSONL copy.
- Update the notes: `$TARXIV_COUCHBASE_BACKUP_DIR` is now a `cbbackupmgr` archive, so rsync the whole directory and don't cherry-pick files.

## 5. Tests — `tarxiv/tests/test_db_utils.py`
Keep the existing dump/load/legacy tests, which use MagicMock `TarxivDB`. Replace the layout-based backup tests (`test_backup_reports_scope_that_keeps_timing_out`, `test_backup_skips_missing_scope_without_failing`, `test_main_backup_exits_nonzero_on_failed_scope`) with:
- `list_collections`: a fake `get_all_scopes` with `_system`, `misc`, `xmatch` and `objects` returns everything except `_system`; the `--scope` filter works.
- A generic dump over several fake collections (fake `scan` results) writes valid JSONL/gz that round-trips through `load_collections`; `scope_map` remaps.
- A collection whose scan keeps timing out is reported as failed, and `main(["--backup"])` exits non-zero.
- `_gfs_rotate` handles `.jsonl.gz` names.

## 6. Restore docs — `setup/README.md` (new "Backups & restore" section)
Cover both backup kinds, with copy-pasteable commands run from `setup/`. Let `CB='-c couchbase://couchbase -u $TARXIV_COUCHBASE_ADMIN_USERNAME -p $TARXIV_COUCHBASE_ADMIN_PASSWORD'`.

**What gets backed up / where:** the archive layout (`tarxiv-YYYY-MM` repos, one backup per night, older months merged), the retention env vars, and the Postgres pointer to `scripts/backup_postgres.sh`.

**cbbackupmgr restores:**
1. *List restore points:* `docker compose run --rm couchbase-backup info -a /backups [-r tarxiv-2026-09]`.
2. *Restore drill (safe; do this first):* restore into scratch scopes without touching live data, e.g. `restore -a /backups -r tarxiv-2026-09 $CB --map-data tarxiv.misc=tarxiv.misc_restore_test`. Compare counts with `SELECT COUNT(*) FROM tarxiv.misc_restore_test.idx`, then drop the scratch scope.
3. *Roll the live bucket back to a point in time:* stop writers first (`docker compose stop tarxiv-api` plus the TNS ingest cron/pipeline). Then run `restore ... --start <backup> --end <backup> --force-updates`. Without `--force-updates`, docs that are newer on the cluster are kept. Explain that a restore never deletes docs created after the backup, so for an exact rollback, flush the bucket or restore into a fresh cluster.
4. *Single scope/collection:* `--include-data tarxiv.xmatch` or `tarxiv.misc.idx`.
5. *Fresh/new server:* bring up `couchbase` (`init_server.sh` creates the bucket, scopes and users; users are not in the backup). Copy or rsync the archive into `$TARXIV_COUCHBASE_BACKUP_DIR`, then `restore` the latest repo. GSI index definitions are restored too. Then run `docker compose run --rm tarxiv-migrate` for Postgres separately.
6. *Old schema data:* the legacy `tns` scope is restored as-is; `--map-data tarxiv.tns=tarxiv.objects` is **not** equivalent (the collection names differ), so don't do it.

**JSONL restores (`db_utils.py`):** `uv run --env-file setup/.env scripts/db_utils.py --load-all -f couchbase-tarxiv-....jsonl.gz [--scope misc] [--map misc=misc_restore_test]`. Note that it's slower, doesn't include indexes, and works across Couchbase versions.

**Verify after any restore:** per-collection `COUNT(*)` against `cbbackupmgr info` doc counts; the API `/health` or a known object lookup; `misc.idx` counters ≥ the highest existing txv id.

Verify each `cbbackupmgr` flag used in the README against `--help` (see step 2). In particular, check whether `restore` needs `--auto-create-buckets` on a fresh cluster.

## Verification (laptop)
1. `uv sync --frozen --extra dev`; `uv run ruff format --check tarxiv/ bin/`; `uv run ruff check --statistics tarxiv/ bin/`; also `uv run ruff check scripts/` and `uv run ruff format --check scripts/`.
2. `uv run pytest tarxiv/tests/test_db_utils.py`, then the full `uv run pytest --log-cli-level=INFO`.
3. `shellcheck scripts/backup_couchbase.sh`; `docker compose -f setup/docker-compose.yml config` to validate the compose change.
4. Local stack (per `AGENTS.md`, macOS may need ~12 GB for Docker). Copy `setup/.env.sample` to `setup/.env` and set `TARXIV_COUCHBASE_BACKUP_DIR` to a local dir. Run `docker compose up -d couchbase`, wait for the pipeline user, then load `uv run --env-file setup/.env scripts/db_utils.py -l -f setup/example_dataset.json` and put a doc in `misc.idx`.
   - Run `scripts/backup_couchbase.sh` twice. `info` should show a full backup, then an incremental, with counts for every scope.
   - Walk through README restore steps 1, 2 and 4 as written, to check the docs are correct.
   - Run `db_utils.py --backup --backup-dir <tmp>`, then `--load-all --map objects=objects_rt` into a scratch scope, and compare counts.
5. Tell the user what to run on the server after merging: `git pull`, set `TARXIV_COUCHBASE_BACKUP_DIR=/data/db_backup/couchbase` in `setup/.env`, one manual `scripts/backup_couchbase.sh` run, then update the live crontab. The existing JSON backups in that dir are left alone, so use a subdirectory, e.g. `/data/db_backup/couchbase/cbbackupmgr`, to keep the archive separate.
