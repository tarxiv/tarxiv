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
| `proxy` | nginx-proxy, nginx-letsencrypt (deployment only) | `docker compose --profile proxy up -d` |
| `setup_elasticsearch` | one-shot Elasticsearch bootstrap | `docker compose run setup_elasticsearch` |

Naming a service on the command line auto-enables its profile, so `docker compose up -d tarxiv-api` works without `--profile tarxiv`. Profiles can be combined (`--profile kafka --profile logging`), and if you always want the same set you can pin it once in `.env` with `COMPOSE_PROFILES=tarxiv,tools`.


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
