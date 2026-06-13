# ORM, User Accounts, and Object Tags Plan

## Purpose

This branch is intended to introduce a relational data layer for lightweight TarXiv accounts and object tagging.

The current branch state only partially implements that goal. This document records the intended architecture, the gaps in the current implementation, and a concrete rollout plan for finishing the work.

For a current implementation snapshot and remaining work list, see `docs/orm-user-tags-status.md`.

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

Tag definitions should no longer be global.

Updated direction:

- tags should be scoped to either a user or a team
- there should not be a global shared list of tags visible to everyone
- UI should eventually expose three views derived from ownership relative to the current user:
  - personal tags
  - tags from teams the user belongs to
  - not a global tag catalog, but the user's combined visible tag universe

Implemented schema direction:

- add `owner_user_id` nullable FK to `tags`
- add `owner_team_id` nullable FK to `tags`
- require exactly one owner scope on each tag
- enforce uniqueness on `(owner_user_id, name)` and `(owner_team_id, name)`

This keeps tag definition and tag ownership aligned, rather than treating ownership as a property only of assignments.

#### `object_tag_assignments`

This is the key table for the actual feature.

Suggested fields:

- `id` UUID primary key
- `object_id` string
- `tag_id` FK to `tags`
- `applied_by_user_id` FK to `users`, nullable
- `created_at`
- `updated_at`

Constraints:

- uniqueness should be based on the scoped tag definition:
  - one assignment per `(object_id, tag_id)` is likely sufficient if `tag_id` already implies owner scope

Notes:

- `object_id` should use the stable TarXiv object identifier already used in Couchbase and the API.
- This avoids duplicating object records into Postgres just to support tagging.
- If candidate IDs and promoted object IDs diverge in future, we should add an object alias mapping layer rather than making the tagging schema more complex now.
- free-form notes on assignments are not part of the current design.

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
- `list_visible_tags(user_id)`
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

Note:

- `/tags` returns only the tags visible to the authenticated user, not a global catalog

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
- `GET /objects/<object_id>/tags` returns only the assignments visible to the authenticated user

The backend now models tag definitions as user- or team-scoped rows in `tags`.

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

## Current Dashboard Follow-On Plan

The current backend has now moved beyond the original minimal team/tag endpoints.

Implemented since the original plan was written:

- team creation and membership listing in the backend
- tag creation/listing and object tag assignment/removal endpoints
- alerts filtering by selected tags
- user-page tag UI and object tagging UI on the lightcurve page
- OpenAPI/Swagger docs for the current API surface
- backend support for:
  - `GET /users/search`
  - `GET /teams/search`
  - `POST /teams/<team_id>/join`
  - `DELETE /user/teams/<team_id>`
  - `GET /tags/<tag_id>/objects`
  - friendly duplicate-username handling on `PATCH /user`

The next dashboard work should build on those backend capabilities rather than inventing new flows in the UI.

### Current Product Decisions

- Keep the route path as `/user`, but rename the dashboard page label from `User` to `Account`.
- Add a dedicated `Tagged` dashboard page.
- Treat username uniqueness as a real product feature, not just a database implementation detail.
- For now, use direct `Join team` and `Leave team` actions.
- Do not implement join-request approval state yet.
- Defer team member management UI until user search is available and the account page basics are stable.

### Phase 1 Backend Scope

This phase is now implemented in the backend and should be treated as the contract for the next UI pass:

- `GET /users/search?q=...`
  - searches by username, nickname, forename, surname, and email
  - returns minimal user summary data
- `GET /teams/search?q=...`
  - searches teams by name and description
  - returns whether the current user is already a member
- `POST /teams/<team_id>/join`
  - direct join flow for the authenticated user
- `DELETE /user/teams/<team_id>`
  - direct leave flow for the authenticated user
- `GET /tags/<tag_id>/objects?limit=&offset=`
  - lists objects associated with a visible tag
- `PATCH /user`
  - returns a clean conflict error when the username is already taken

### Account Page Plan

The current `/user` page should evolve into the account hub.

Recommended next UI changes:

1. Rename the page label from `User` to `Account` while keeping the path `/user`.
2. Tidy the teams section into clearer subsections:
   - `Your Teams`
   - `Discover Teams`
   - `Create Team`
3. Keep creation forms hidden by default and reveal them only from explicit buttons.
4. Add team discovery/search on the account page using `GET /teams/search`.
5. Show join/leave actions in search results and current memberships.
6. Keep member-management UI out of the dashboard for now.

### Tagged Page Plan

Add a new dashboard page called `Tagged`.

Recommended first implementation:

- load available tags with `GET /tags`
- allow the user to select one tag at a time
- load tagged objects with `GET /tags/<tag_id>/objects`
- render object IDs as links to `/lightcurve/<object_id>`
- keep the first pass simple and paginated rather than trying to expand all tags at once

### Team Member Management Plan

This remains a second-pass feature.

Prerequisites now in place:

- backend user search endpoint exists
- backend add-member endpoint exists

Recommended second-pass implementation:

- expose member-management controls only to owners/admins
- use `GET /users/search` to find users by username/name/email
- add users to teams via `POST /teams/<team_id>/members`
- decide later whether this should live on the account page or a dedicated team detail page

### Current Testing Expectations

The project now has both mocked API tests and real Postgres integration coverage for team/tag behavior.

Current expectations for follow-on work:

- add API tests for any new account-page/team discovery routes if the contract changes
- keep integration coverage for join/leave, tagged object listing, and duplicate username conflicts
- add dashboard-level tests later once the account and tagged pages settle



# Summary of necessary changes before commit:
From Jack:
(Implementation detail and decisions recorded in `docs/orm-dashboard-polish-plan.md`.)
  - [x] Team management
    - [x] List team members on manage team members section
          (new `GET /teams/<team_id>/members` + member list in the manager)
    - [x] Confirmation of people being added to teams (success banner)
    - [x] Search list updates on team member being added
          (added user dropped from results, member list refreshed)
    - [ ] Limit who can create teams? — DEFERRED (kept open creation)
    - [ ] Invite rather than directly add people to teams? — DEFERRED (kept direct add)
  - [x] Polishing UI
    - [x] Colour wheel on tag colour (`dmc.ColorInput` with swatches)
    - [~] Image/file selector on profile image url? — URL input polished with live
          preview + validation; file upload DEFERRED (needs storage backend)
    - [x] username generator (Suggest button on the username field)
    - [x] Hiding of various sections on user page (Profile/Teams/Tags tabs)
    - [~] API Token — relabelled as session token + copy button; real personal
          access tokens DEFERRED (no backend yet)
    - [x] Empty taglist option (friendly empty state)
    - [x] Display banner in correct location (in-context, per active tab)
  - [x] Remove tag filtering from Alerts
  - [x] Split up account info, tags, and teams onto different pages? (tabs on `/user`)
  - [x] Modal hover-over on Account button (`dmc.HoverCard` with profile summary)

Deferred (future work): personal access tokens, team invite/approval workflow,
team-creation limits, profile image upload, remove-member / change-role UI.