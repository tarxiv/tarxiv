# ORM, User Accounts, and Object Tags Plan

## Purpose

This branch is intended to introduce a relational data layer for lightweight TarXiv accounts and object tagging.

The current branch state only partially implements that goal. This document records the intended architecture, the gaps in the current implementation, and a concrete rollout plan for finishing the work.

## Current Direction

The agreed direction is:

- Use ORCID only as an identity provider, not as the authoritative source of profile metadata.
- Store TarXiv-specific profile metadata in the relational database and allow it to be edited independently of ORCID.
- Support future authentication providers by separating external identity from internal user records.
- Attach tags to astronomical objects, with ownership scoped to either a user or a team.
- Drop permissions for now; authenticated access is sufficient in the near term.
- Move away from `setup/postgres-init.sql` toward schema creation and evolution managed by SQLAlchemy metadata and Alembic migrations.

## Summary of Current Branch State

Implemented in some form:

- SQLAlchemy and psycopg dependencies
- PostgreSQL service in docker compose
- Initial ORM models for `User`, `Institution`, and partial `Team`
- DTO/ORM separation started via `tarxiv/dto.py` and `tarxiv/orm.py`
- API login callback attempts to persist ORCID-backed users
- A Postgres user data layer exists in `tarxiv/database_user.py`

Not implemented or incomplete:

- Stable auth import path currently broken by a circular import
- ORCID login DTO shape is incompatible with the current `dto.User`
- Postgres environment wiring is incomplete in compose/docs
- ORM coverage does not match the intended schema
- No Alembic setup
- No tag ownership model in application code
- No object-tag API endpoints
- No team membership workflow
- No editable TarXiv profile workflow
- Duplicate Postgres access layer modules (`database_user.py` and `pg_database.py`)

## Recommended Target Data Model

The relational model should distinguish four concerns:

1. Internal TarXiv users
2. External authentication identities
3. Teams and team membership
4. Object-level tags applied by either users or teams

### Core Tables

#### `users`

TarXiv-owned account/profile record.

Suggested fields:

- `id` UUID primary key
- `display_name` nullable
- `username` nullable, unique if kept
- `email` nullable
- `forename` nullable
- `surname` nullable
- `institution_name` nullable
- `picture_url` nullable
- `bio` nullable
- `created_at`
- `updated_at`

Notes:

- This should represent TarXiv's editable profile state.
- ORCID-derived values can be used as defaults when the user first signs in.
- Avoid making most profile fields required.

#### `external_identities`

Maps an internal user to one external login provider.

Suggested fields:

- `id` UUID primary key
- `user_id` FK to `users`
- `provider` string, e.g. `orcid`
- `provider_user_id` string
- `provider_username` nullable
- `provider_email` nullable
- `provider_profile_json` nullable JSON blob
- `created_at`
- `updated_at`

Constraints:

- unique on `provider, provider_user_id`

Notes:

- This is the extensibility point for future authenticators.
- ORCID iD should live here, not as a hard-coded core user field.

#### `teams`

Suggested fields:

- `id` UUID primary key
- `name` unique
- `description` nullable
- `created_by_user_id` FK to `users`, nullable
- `created_at`
- `updated_at`

#### `team_memberships`

Suggested fields:

- `team_id` FK to `teams`
- `user_id` FK to `users`
- `role` string, default `member`
- `created_at`

Constraints:

- composite primary key or unique constraint on `team_id, user_id`

Notes:

- Keep roles minimal for now: `member`, `admin`, `owner`.

#### `tags`

Suggested fields:

- `id` UUID primary key
- `name` string
- `description` nullable
- `color` nullable
- `created_at`
- `updated_at`

Constraint options:

- If tags are global labels: unique on `name`
- If tags are scoped per owner: unique on `(owner scope, name)` through ownership tables

Recommendation:

- Start with global tag definitions plus explicit ownership on assignments. This is simpler and good enough unless private tag vocabularies are required.

#### `object_tag_assignments`

This is the key table for the actual feature.

Suggested fields:

- `id` UUID primary key
- `object_id` string
- `tag_id` FK to `tags`
- `applied_by_user_id` FK to `users`, nullable
- `owner_user_id` FK to `users`, nullable
- `owner_team_id` FK to `teams`, nullable
- `note` nullable
- `created_at`
- `updated_at`

Constraints:

- exactly one of `owner_user_id` or `owner_team_id` must be set
- optional uniqueness depending on intended semantics:
  - one assignment per `(object_id, tag_id, owner_user_id)`
  - one assignment per `(object_id, tag_id, owner_team_id)`

Notes:

- `object_id` should use the stable TarXiv object identifier already used in Couchbase and the API.
- This avoids duplicating object records into Postgres just to support tagging.
- If candidate IDs and promoted object IDs diverge in future, we should add an object alias mapping layer rather than making the tagging schema more complex now.

## DTO Strategy

The current branch uses one `dto.User` model for both pre-insert provider payloads and persisted database rows. That is too rigid.

Recommended DTOs:

- `UserCreateFromIdentity`
- `UserProfile`
- `UserProfileUpdate`
- `ExternalIdentity`
- `Team`
- `TeamMembership`
- `Tag`
- `ObjectTagAssignment`
- `ObjectTagCreate`

Guidelines:

- DTOs for inbound API payloads should not require DB-generated fields.
- DTOs returned by DB-backed service methods may include generated IDs and timestamps.
- Provider-normalized payloads should map to a provider-specific or identity-specific DTO first, not directly to the persisted user row DTO.

## ORM Strategy

The ORM should fully represent the schema the application intends to own.

Recommended changes:

- Replace the current ORCID-specific `User.orcid_id` field with an `ExternalIdentity` model.
- Remove legacy or duplicate schema ideas unless there is a concrete consumer.
- Keep ORM definitions in one module package, for example `tarxiv/orm.py` or `tarxiv/orm/` if it becomes large.
- Make relationships explicit for:
  - `User` -> `ExternalIdentity`
  - `User` <-> `Team` through `TeamMembership`
  - `Tag` -> `ObjectTagAssignment`
  - `User` / `Team` -> `ObjectTagAssignment`

## Migration Strategy

`setup/postgres-init.sql` should be treated as temporary and removed.

Recommended migration approach:

1. Add Alembic configuration.
2. Define the target SQLAlchemy models.
3. Generate an initial migration from those models.
4. Apply migrations in local development and deployment workflows.
5. Remove `postgres-init.sql` once migration-based setup is verified.

Notes:

- For local development, it is acceptable to create the schema from scratch during early iteration.
- For long-term maintainability, all schema evolution should be migration-driven.

## Service Layer Strategy

The API should not work with ORM sessions directly. Add a relational service layer with small, explicit operations.

Suggested services:

- `UserService`
- `IdentityService`
- `TeamService`
- `TagService`

Important operations:

### Identity/User

- `get_or_create_user_from_identity(provider, provider_user_id, defaults)`
- `get_user(user_id)`
- `get_user_by_provider_identity(provider, provider_user_id)`
- `update_user_profile(user_id, profile_update)`

### Teams

- `create_team(...)`
- `add_user_to_team(...)`
- `list_user_teams(user_id)`

### Tags

- `create_tag(...)`
- `list_tags()`
- `assign_tag_to_object_for_user(object_id, tag_id, owner_user_id, ...)`
- `assign_tag_to_object_for_team(object_id, tag_id, owner_team_id, ...)`
- `list_object_tags(object_id, viewer_user_id)`
- `remove_object_tag_assignment(assignment_id, actor_user_id)`

## Authentication Flow

Recommended flow for ORCID and future providers:

1. Provider callback returns `provider`, `provider_user_id`, and optional profile defaults.
2. API looks up `external_identities(provider, provider_user_id)`.
3. If found, load the linked TarXiv user.
4. If not found:
   - create a TarXiv `users` row with provider-derived defaults if available
   - create the `external_identities` row
5. Sign the session JWT using internal TarXiv user information plus provider information as needed.

JWT guidance:

- The JWT should include the internal TarXiv user ID.
- It may also include provider and provider user ID.
- Do not rely on provider profile data in the JWT as the durable source of truth for editable user metadata.

Recommended minimal JWT claims:

- `sub`: internal TarXiv user ID
- `provider`: `orcid`
- `provider_user_id`: ORCID iD
- `profile`: minimal display data for UI convenience

## API Shape

Per project direction, user profile endpoints should use `/user`, not `/me`.

Recommended initial endpoints:

### User profile

- `GET /user`
- `PATCH /user`

### Teams

- `GET /user/teams`
- `POST /teams`
- `POST /teams/<team_id>/members`

### Tags

- `GET /tags`
- `POST /tags`

### Object tags

- `GET /objects/<object_id>/tags`
- `POST /objects/<object_id>/tags`
- `DELETE /objects/<object_id>/tags/<assignment_id>`

Current implementation status:

- `GET /user` implemented
- `PATCH /user` implemented
- `GET /user/teams` implemented
- `POST /teams` implemented
- `POST /teams/<team_id>/members` implemented
- `GET /tags` implemented
- `POST /tags` implemented
- `GET /objects/<object_id>/tags` implemented
- `POST /objects/<object_id>/tags` implemented
- `DELETE /objects/<object_id>/tags/<assignment_id>` implemented

The object tags response should make ownership explicit, for example:

- assignment ID
- object ID
- tag
- owner type: `user` or `team`
- owner ID
- applied by user
- created timestamp

Visibility rules in the current implementation:

- personal object tags are visible only to the owning user
- team-owned object tags are visible only to members of that team
- global tags are currently implemented as global tag definitions in `/tags`
- `GET /objects/<object_id>/tags` returns only the assignments visible to the authenticated user

## Recommended Implementation Order

### Phase 1: Stabilize the current branch

- Fix the auth provider circular import.
- Remove or archive `tarxiv/pg_database.py` and keep a single Postgres service path.
- Fix DTO misuse by separating provider payload DTOs from persisted user DTOs.
- Add missing Postgres environment wiring to compose and docs.
- Fix obvious broken imports introduced elsewhere on the branch.
- Add smoke tests that import API/auth successfully.

### Phase 2: Establish the relational foundation

- Finalize ORM models for users, identities, teams, memberships, tags, and object tag assignments.
- Add Alembic.
- Generate the first migration.
- Remove `setup/postgres-init.sql` from the active setup path.

### Phase 3: Finish login-backed user provisioning

- Implement `get_or_create_user_from_identity(...)`.
- Ensure first login creates both user and external identity records.
- Ensure repeat login reuses the existing user.
- Persist provider-sourced defaults only when TarXiv-owned profile fields are empty or during first creation.

### Phase 4: Add editable TarXiv profile support

- Implement `GET /user` and `PATCH /user`.
- Keep profile editing limited to TarXiv-owned fields.
- Document which fields are ORCID-derived defaults versus TarXiv-managed state.

### Phase 5: Add team support

- Implement team creation and membership listing.
- Add user-team relationships to the user page.
- Keep roles minimal.

### Phase 6: Add object tagging

- Implement tag creation/listing.
- Implement object-tag assignment endpoints.
- Support user-owned and team-owned assignments.
- Render object tags in the relevant object page in the dashboard.

### Phase 7: Cleanup and hardening

- Remove obsolete schema/bootstrap code.
- Add integration tests for login plus tag flows.
- Add developer documentation for migrations and local setup.

## Testing Recommendations

Minimum test coverage for this work should include:

- auth provider import and login flow tests
- `get_or_create_user_from_identity(...)` idempotency
- migration application on an empty Postgres database
- profile update API tests
- object tag assignment tests for:
  - user-owned assignment
  - team-owned assignment
  - duplicate handling
  - visibility/listing

## Immediate Branch Fixes Before Feature Work

These should happen before adding more functionality:

- fix `tarxiv/auth/providers` circular import
- stop using persisted-user DTOs for provider-normalized payloads
- unify the Postgres data layer
- wire `TARXIV_POSTGRES_URL` into runtime config
- remove broken package-relative import changes introduced in unrelated modules

## Open Design Questions

These should be settled early in implementation:

1. Tag definitions are global.
2. Object tag assignments should only reference tags; free-form notes are out of scope for now.
3. Team-owned tags should only be visible to members of that team.
4. Provider-derived profile fields should only be copied into TarXiv-managed fields when the local field is empty.

## Recommended Decision Defaults

Unless later requirements change, the simplest good defaults are:

- global tag catalog
- explicit object tag assignments
- no free-form assignment notes in the first implementation
- user-visible tag scopes: personal, team, and global definitions
- TarXiv-owned editable profile fields
- one internal user record with many external identities
- provider defaults only fill empty local fields
- Alembic for all schema evolution
