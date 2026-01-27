# ORCID Identity Provider for TarXiv

This setup keeps Postgres as the backend while switching identity to ORCID OAuth.

## 1. Configure environment variables

Add the following to your `.env` (or export in your shell):

- `ORCID_CLIENT_ID`: ORCID application client ID
- `ORCID_CLIENT_SECRET`: ORCID application client secret
- `ORCID_REDIRECT_URI`: Redirect URI registered with ORCID (example: `http://localhost:8050/`)
- `ORCID_SCOPE`: Optional, defaults to `/authenticate`
- `ORCID_AUTH_URL`, `ORCID_TOKEN_URL`, `ORCID_API_BASE`: Optional overrides for sandbox

## 2. Start Postgres

From `setup/`:

```bash
docker-compose up -d postgres
```

The database schema is initialized from `postgres-init.sql` on first boot.

## 3. Run the dashboard

```bash
docker-compose --profile tarxiv up -d tarxiv-dashboard
```

Click "Sign in with ORCID" in the navbar to authenticate.
