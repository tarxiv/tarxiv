# Setup Instructions

This directory contains the Docker configurations for the services required by the TarXiv pipeline and API. To start-up the services, run the following commands:

```commandline
docker compose run setup_elasticsearch     # one-shot Elasticsearch bootstrap
docker compose up -d                       # couchbase, postgres, redis
docker compose run --rm tarxiv-migrate     # apply Alembic migrations
docker compose --profile tarxiv up -d      # the API and dashboard
```

The second command will take about one minute to correctly start-up the Couchbase daemon.

###### You can access the Couchbase web interface at http://localhost:8091/.

## Service profiles

A bare `docker compose up` starts only the four backing stores needed by the dev loop. Everything else is opt-in via a profile:

| Profile | Services | Start with |
|---|---|---|
| *(default)* | couchbase, postgres, redis | `docker compose up -d` |
| `tarxiv` | tarxiv-migrate, tarxiv-api, tarxiv-dashboard | `docker compose --profile tarxiv up -d` |
| `tools` | adminer (DB browser on :8079) | `docker compose --profile tools up -d` |
| `logging` | elasticsearch, logstash, kibana | `docker compose --profile logging up -d` |
| `kafka` | kafka-broker, schema registry, connect, rest proxy, kafbat-ui, prometheus | `docker compose --profile kafka up -d` |
| `monitoring` | prometheus | `docker compose --profile monitoring up -d` |
| `backup` | couchbase-backup (one-shot `cbbackupmgr` runner) | `scripts/backup_couchbase.sh` |
| `proxy` | nginx-proxy, nginx-letsencrypt (deployment only) | `docker compose --profile proxy up -d` |
| `setup_elasticsearch` | one-shot Elasticsearch bootstrap | `docker compose run setup_elasticsearch` |

Naming a service on the command line auto-enables its profile, so `docker compose up -d tarxiv-api` works without `--profile tarxiv`. Profiles can be combined (`--profile kafka --profile logging`), and if you always want the same set you can pin it once in `.env` with `COMPOSE_PROFILES=tarxiv,tools`.

## Backups & restore

There are two kinds of Couchbase backup. Postgres is backed up separately by `scripts/backup_postgres.sh` (restore instructions are in its header). `scripts/backup.crontab.example` has the cron schedule for all of them.

| | cbbackupmgr (primary, nightly) | JSONL (optional, weekly) |
|---|---|---|
| Made by | `scripts/backup_couchbase.sh` | `scripts/db_utils.py --backup` |
| Where | `$TARXIV_COUCHBASE_ARCHIVE_DIR` | `$TARXIV_COUCHBASE_BACKUP_DIR` |
| Covers | the whole `tarxiv` bucket, including index definitions | every scope/collection, docs only |
| Layout | one repo per month (`tarxiv-YYYY-MM`): a full backup on the first night, incrementals after | one `couchbase-tarxiv-YYYYMMDD-HHMMSS.jsonl.gz` file per run |
| Retention | `TARXIV_COUCHBASE_KEEP_MONTHS` monthly repos (default 12) | GFS: `TARXIV_KEEP_{DAILY,WEEKLY,MONTHLY}_DAYS` |

Couchbase users are not in either backup. `init_server.sh` recreates them on a fresh cluster.

### cbbackupmgr restores

Run these from `setup/`. They need admin credentials and the `couchbase-backup` service:

```commandline
set -a; source .env; set +a
export CB_USERNAME=$TARXIV_COUCHBASE_ADMIN_USERNAME CB_PASSWORD=$TARXIV_COUCHBASE_ADMIN_PASSWORD
alias cbbackupmgr='docker compose run --rm -e CB_USERNAME -e CB_PASSWORD couchbase-backup'
```

1. **List restore points.** Backup names (e.g. `2026-09-29T03_00_01.123456789Z`) are shown per repo.
   ```commandline
   cbbackupmgr info -a /backups                    # every repo
   cbbackupmgr info -a /backups -r tarxiv-2026-09  # one month, with per-collection doc counts
   ```
2. **Restore drill (safe, do this first).** Restore a scope into a scratch scope without touching live data. The drill takes the latest backup in the repo. Then compare the counts with `info` and drop the scratch scope:
   ```commandline
   cbbackupmgr restore -a /backups -r tarxiv-2026-09 -c couchbase://couchbase \
     --include-data tarxiv.misc --map-data tarxiv.misc=tarxiv.misc_restore_test
   docker compose exec couchbase /opt/couchbase/bin/cbq -u $CB_USERNAME -p $CB_PASSWORD \
     --script "SELECT COUNT(*) FROM tarxiv.misc_restore_test.idx"
   docker compose exec couchbase /opt/couchbase/bin/couchbase-cli collection-manage \
     -c localhost -u $CB_USERNAME -p $CB_PASSWORD --bucket tarxiv --drop-scope misc_restore_test
   ```
3. **Roll the live bucket back to a point in time.** First stop the writers: `docker compose stop tarxiv-api`, and pause the TNS ingest cron/pipeline. Then restore from that backup:
   ```commandline
   cbbackupmgr restore -a /backups -r tarxiv-2026-09 -c couchbase://couchbase \
     --start 2026-09-20T03_00_01.123456789Z --end 2026-09-20T03_00_01.123456789Z --force-updates
   ```
   Without `--force-updates`, documents that are newer on the cluster are kept. A restore never deletes documents created after the backup. For an exact rollback, flush the bucket (or use a fresh cluster) first.
4. **A single scope or collection.** Add `--include-data tarxiv.xmatch` or `--include-data tarxiv.misc.idx` to any restore.
5. **Fresh or new server.** Bring up `couchbase` (`init_server.sh` creates the bucket, scopes and users). Copy or rsync the whole archive into `$TARXIV_COUCHBASE_ARCHIVE_DIR`, then restore the latest repo with `cbbackupmgr restore -a /backups -r tarxiv-YYYY-MM -c couchbase://couchbase`. GSI index definitions are restored too. Postgres is separate: `pg_restore` (see `scripts/backup_postgres.sh`), then `docker compose run --rm tarxiv-migrate`.
6. **Legacy `tns` scope.** It is restored as-is. Don't try `--map-data tarxiv.tns=tarxiv.objects`: the collection names differ (`tns.objects` vs `objects.meta`), so it isn't equivalent.

### JSONL restores

This is slower than cbbackupmgr and doesn't include indexes, but the files work across Couchbase versions. Target scopes and collections must already exist. From the repo root:

```commandline
uv run --env-file setup/.env scripts/db_utils.py --load-all \
  -f couchbase-tarxiv-YYYYMMDD-HHMMSS.jsonl.gz [--scope misc] [--map misc=misc_restore_test]
```

### Verify after any restore

- Per-collection `SELECT COUNT(*) FROM tarxiv.<scope>.<collection>` matches the doc counts from `cbbackupmgr info` (or the counts `db_utils.py --backup` printed).
- The API responds and a known object loads in the dashboard.
- The `misc.idx` counters (one doc per year) are ≥ the highest existing `TXV-<year>-…` id, or new objects will get duplicate ids.


# Local development setup

If you are looking to run a local development version of the system you should be able to just use the example environment variables in the `.env.sample` file, simply by copying it to the setup directory and renaming it to .env, i.e. 

```commandline
cp .env.sample .env
```

After this, running the above docker compose commands _should_ work. 
We have encountered several instances where more memory is required (up to 12GB should work), usually on Mac where docker runs in a virtualised environment.
You may also need to pre-create the directories in `.data` for each of the microservices so they have appropriate permissions:

```commandline
mkdir -p .data/elastic .data/couchbase .data/redis .data/postgres/db
```

## Populating with test data

There is a db_utils tool in the scripts directory which should allow you to load in the example dataset found in this directory (`example_dataset.json`). You should be able to run the following command:

```commandline
python ../scripts/db_utils.py -l -f example_dataset.json
```

but only if the following caveats are true:
- You have set up your `tarxiv` config file correctly
- You have couchbase running with docker compose
- You have set up a virtual environment, or similar, with the necessary dependencies to run `tarxiv`
