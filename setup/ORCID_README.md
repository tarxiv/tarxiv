# ORCID Identity Provider for TarXiv

This setup keeps Postgres as the backend while switching identity to ORCID OAuth.

Schema initialization is now handled via Alembic migrations.

## 1. Configure environment variables

Add the following to your `.env` (or export in your shell):

- `ORCID_CLIENT_ID`: ORCID application client ID
- `ORCID_CLIENT_SECRET`: ORCID application client secret
- `ORCID_SCOPE`: Optional, defaults to `/authenticate`
- `ORCID_AUTH_URL`, `ORCID_TOKEN_URL`, `ORCID_API_BASE`: Optional overrides for sandbox

## 2. Start Postgres

From `setup/`:

```bash
docker-compose up -d postgres
```

## 3. Run migrations

From `setup/`, run the one-shot migration service inside the compose network:

```bash
docker compose run --rm tarxiv-migrate
```

If you need to run Alembic directly from the host instead, make sure `TARXIV_POSTGRES_URL` points at the exposed local port rather than the docker service hostname (this is not recommended).

## 4. Run the dashboard

```bash
docker-compose --profile tarxiv up -d tarxiv-dashboard
```

Click "Sign in with ORCID" in the navbar to authenticate.
