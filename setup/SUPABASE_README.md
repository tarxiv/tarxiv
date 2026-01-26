# Supabase Integration for Tarxiv

This setup adds Supabase (PostgreSQL + Auth + REST API) to your Tarxiv Docker Compose stack for managing user accounts and user-specific data.

## Services Added

- **supabase-db**: PostgreSQL database (port 5432)
- **supabase-auth**: GoTrue authentication service (port 9999)
- **supabase-rest**: PostgREST API (port 3000)
- **supabase-kong**: Kong API Gateway (port 8000) - unified entry point

## Quick Start

### 1. Configure Environment Variables

Copy the example environment variables to your `.env` file:

```bash
cat .env.supabase.example >> ../.env
```

Edit the `.env` file and update:
- `SUPABASE_DB_PASSWORD`: Choose a strong password
- `SUPABASE_JWT_SECRET`: Generate with `openssl rand -base64 32`

### 2. Start Supabase Services

```bash
docker-compose up -d supabase-db supabase-auth supabase-rest supabase-kong
```

Wait for the database to be ready (check with `docker-compose logs supabase-db`).

### 3. Initialize the Database

Run the initialization script to create schemas, roles, and example tables:

```bash
docker-compose exec supabase-db psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/supabase-init.sql
```

Or copy it into the container first:

```bash
docker cp supabase-init.sql $(docker-compose ps -q supabase-db):/tmp/init.sql
docker-compose exec supabase-db psql -U postgres -d postgres -f /tmp/init.sql
```

### 4. Install Python Client

```bash
pip install supabase
```

### 5. Try the Example

```bash
cd ../examples
python supabase_example.py
```

## API Endpoints

All requests go through Kong at `http://localhost:8000`:

- **Auth**: `http://localhost:8000/auth/v1/`
  - POST `/auth/v1/signup` - Create new user
  - POST `/auth/v1/token?grant_type=password` - Login
  - GET `/auth/v1/user` - Get current user
  - POST `/auth/v1/logout` - Logout

- **REST API**: `http://localhost:8000/rest/v1/`
  - GET/POST/PATCH/DELETE `/rest/v1/user_profiles`
  - GET/POST/PATCH/DELETE `/rest/v1/tarxiv_user_data`

## Example Tables

The initialization script creates two example tables:

### `user_profiles`
Stores user profile information:
- `id` (UUID) - Links to auth.users
- `username` (TEXT)
- `full_name` (TEXT)
- `avatar_url` (TEXT)

### `tarxiv_user_data`
Stores user-specific astronomical object data:
- `id` (UUID)
- `user_id` (UUID) - Links to auth.users
- `object_name` (TEXT) - Name of the astronomical object
- `notes` (TEXT) - User notes about the object
- `tags` (TEXT[]) - Array of tags
- `is_favorite` (BOOLEAN)

Both tables have Row Level Security (RLS) enabled, so users can only access their own data.

### New tables for users, tags, and teams
The dashboard now expects richer profile and collaboration tables:
- `users` (UUID PK → `auth.users.id`, provider id, username/nickname/email, names, bio, picture_url, institution)
- `tags` (id, name, description)
- `teams` (id, name, description, admin_user_id → `users.id`)
- `user_tags` (user_id, tag_id)
- `team_tags` (team_id, tag_id)
- `user_teams` (user_id, team_id, role, joined_at)

RLS highlights:
- Users can read/write only their own row in `users`.
- Tags are world-readable; service role manages writes.
- Teams are readable to authenticated users; updates/deletes require admin_user_id.
- Team membership (`user_teams`) is visible to the member or team admin; members can join themselves; admins manage membership.
- Team tags are visible to members/admins; admins manage tags.

Re-run the init script after pulling these changes:
```bash
docker-compose exec supabase-db psql -U postgres -d postgres -f /docker-entrypoint-initdb.d/supabase-init.sql
```

## Using with Python

```python
from supabase import create_client

# Initialize
supabase = create_client(
    "http://localhost:8000",
    "your-anon-key-here"
)

# Sign up
response = supabase.auth.sign_up({
    "email": "user@example.com",
    "password": "password123"
})

# Login
response = supabase.auth.sign_in_with_password({
    "email": "user@example.com",
    "password": "password123"
})

# Insert data (automatically filtered by user_id due to RLS)
supabase.table("tarxiv_user_data").insert({
    "object_name": "SN2024abc",
    "notes": "Interesting supernova",
    "is_favorite": True
}).execute()

# Query data (automatically filtered by user_id due to RLS)
data = supabase.table("tarxiv_user_data").select("*").execute()
```

## API Keys

The demo keys in the Kong configuration are:

- **anon** (public): `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (see .env.supabase.example)
- **service_role** (admin): `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...` (see .env.supabase.example)

**Important**: For production, generate your own JWT keys based on your `SUPABASE_JWT_SECRET`.

## Generating Production Keys

1. Use the `SUPABASE_JWT_SECRET` from your `.env`
2. Create JWT tokens with the appropriate role claims (`anon` or `service_role`)
3. Update the `supabase-kong.yml` consumer credentials

## Stopping Services

```bash
docker-compose stop supabase-db supabase-auth supabase-rest supabase-kong
```

## Database Admin UI

An Adminer container is included for quick inspection of Supabase tables.

1. Start it with the rest of the stack:
   ```bash
   docker-compose up -d supabase-db supabase-auth supabase-rest supabase-kong supabase-adminer
   ```
2. Open http://localhost:8080 in your browser.
3. Use the same credentials as `SUPABASE_DB_USER` / `SUPABASE_DB_PASSWORD`.

Adminer connects directly to the `supabase-db` Postgres instance, so any schema changes there are reflected immediately.

## Troubleshooting login errors

- Make sure the Supabase services are running (`docker-compose ps` should show `supabase-db`, `supabase-auth`, `supabase-rest`, `supabase-kong` healthy).
- Confirm the URL/key the dashboard uses (`SUPABASE_API_EXTERNAL_URL`, `SUPABASE_ANON_KEY`) match the ones exposed through Kong at `http://localhost:8000`.
- If you recreate the database, rerun `supabase-init.sql` so that the `users`, `tags`, and `teams` tables exist before logging in.

## CLI helper for admins

There is now a small helper in `scripts/supabase_admin.py` for creating users or seeding metadata with the service role key.

```bash
# Make sure SUPABASE_SERVICE_ROLE_KEY is set in your environment
python scripts/supabase_admin.py create-user \
  --email user@example.com \
  --password "secretpass" \
  --username astro_hacker \
  --institution "Tarxiv Lab"
```

The script uses Supabase's admin API and will auto-create a matching row in the `users` table so the dashboard can display the profile immediately.

## Viewing Logs

```bash
docker-compose logs -f supabase-auth
docker-compose logs -f supabase-db
```

## Next Steps

1. Customize the example tables to match your needs
2. Add more tables with RLS policies for different types of user data
3. Integrate Supabase Auth into your Tarxiv dashboard
4. Set up email verification (configure SMTP settings)
5. Add OAuth providers (Google, GitHub, etc.)

## Resources

- [Supabase Documentation](https://supabase.com/docs)
- [Supabase Python Client](https://github.com/supabase-community/supabase-py)
- [Row Level Security Guide](https://supabase.com/docs/guides/auth/row-level-security)
- [GoTrue API Reference](https://supabase.com/docs/reference/auth)
