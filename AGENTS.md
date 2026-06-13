# TarXiv Agent Notes

## Workflow
- Use `uv`, not `pip`/`poetry`. CI installs with `uv sync --frozen --extra dev`; the Docker/compose job uses `uv sync --locked --all-extras --dev`.
- Match CI checks before finishing Python changes:
  - `uv run ruff format --check tarxiv/`
  - `uv run ruff check --statistics tarxiv/`
  - `uv run pytest --log-cli-level=INFO`
- CI lint only checks `tarxiv/` and `bin/`. If you edit `bin/*`, run the same Ruff commands on `bin/` too.

## Entrypoints
- API entrypoint: `bin/start-api` -> `tarxiv.api.API`.
- Dashboard entrypoint: `bin/run_dashboard.py` -> `tarxiv.dashboard.TarxivDashboard`.
- TNS ingestion entrypoint: `bin/tns-ingest` -> `tarxiv.pipeline.TNSPipeline`.
- API and dashboard are separate runtimes. The API talks to Couchbase and Postgres; the dashboard talks to Couchbase and redirects auth to the API.

## Config And Env
- Runtime code reads `config.yml` from `TARXIV_CONFIG_DIR` via `tarxiv.utils.TarxivModule`. Do not assume `.env` alone is enough for local runs.
- Default config path is `../aux/config.yml` relative to the package; compose overrides this with `TARXIV_CONFIG_DIR=/app/aux` and bind-mounts `aux/config.yml`.
- Auth/user flows also require `TARXIV_POSTGRES_URL`; `UserDB` raises immediately if it is missing.
- Alembic also requires `TARXIV_POSTGRES_URL`; metadata comes from `tarxiv.orm`.

## Local Services
- Full local stack lives under `setup/`. Start from `setup/.env.sample` copied to `setup/.env`.
- Compose startup order matters for local integration: run `docker compose run setup_elasticsearch` before bringing up the main services.
- Couchbase bootstrap is slow enough that CI explicitly waits for the pipeline user to exist before loading data or starting the app.
- Local Docker on macOS may need significantly more memory; `setup/README.md` calls out up to 12 GB.
- Useful integration sequence from CI:
  - `docker compose run setup_elasticsearch`
  - `docker compose up -d elasticsearch logstash kibana couchbase`
  - `uv run --env-file setup/.env scripts/db_utils.py -l -f setup/example_dataset.json`
  - `docker compose up -d tarxiv-api tarxiv-dashboard`

## Tests
- Tests live in `tarxiv/tests/`.
- Fast focused run: `uv run pytest tarxiv/tests/test_auth.py`.
- Single test example: `uv run pytest tarxiv/tests/test_auth.py -k test_auth_callback`.
- Pytest markers defined in `pyproject.toml`: `slow`, `imap`, `gmail`, `auth`.
- Many unit tests monkeypatch `TarxivModule`, DB constructors, or file I/O; for API/auth changes, update tests with the mocks instead of trying to boot real services.
- `tarxiv/tests/test_pipeline.py` is effectively disabled (`test_pipeline` is just `pass`) because the real external flow is unreliable in CI. Do not treat it as coverage for ingestion changes.

## Structure
- `tarxiv/api.py` owns Flask routes, OAuth redirects/callbacks, and protected API endpoints.
- `tarxiv/dashboard/` is the Dash UI package; `TarxivDashboard.app.layout` is intentionally a function (`create_layout`), not a prebuilt layout, so auth state is re-evaluated on page load.
- Couchbase access is still in `tarxiv.database.TarxivDB`; relational auth/user/tag data is in Postgres via `tarxiv.database_user` + `tarxiv.orm`.
