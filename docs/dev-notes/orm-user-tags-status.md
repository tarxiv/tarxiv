# ORM, User, Team, and Tagging Status

## Purpose

This note is a snapshot of what has been completed on the ORM/account/tagging work, what is currently in place on the branch, and what still needs to be finished.

This is a status companion to `docs/orm-user-tags-plan.md`, which remains the broader design and rollout document.

## Completed So Far

- Added a relational SQLAlchemy model layer in `tarxiv/orm.py` for:
  - `users`
  - `external_identities`
  - `teams`
  - `team_memberships`
  - `tags`
  - `object_tag_assignments`
- Added Alembic setup and an initial migration for the current relational schema.
- Consolidated Postgres access into `tarxiv/database_user.py` and removed the duplicate `pg_database.py` path.
- Switched auth/user identity handling so JWT `sub` is the internal TarXiv user UUID.
- Kept ORCID as an external identity provider rather than the core user record.
- Added user/profile API routes:
  - `GET /user`
  - `PATCH /user`
  - `GET /users/search`
- Added team API routes:
  - `GET /user/teams`
  - `DELETE /user/teams/<team_id>`
  - `POST /teams`
  - `GET /teams/search`
  - `POST /teams/<team_id>/join`
  - `POST /teams/<team_id>/members`
- Added tag and tagged-object API routes:
  - `GET /tags`
  - `POST /tags`
  - `GET /tags/<tag_id>/objects`
  - `GET /objects/<object_id>/tags`
  - `POST /objects/<object_id>/tags`
  - `DELETE /objects/<object_id>/tags/<assignment_id>`
- Added lightweight OpenAPI/Swagger docs at:
  - `GET /openapi.json`
  - `GET /docs`
- Updated compose/CI migration flow to run a dedicated `tarxiv-migrate` step.
- Added integration tests for the relational user/team/tag flows using `testcontainers.postgres`.

## Dashboard Progress

- Rebuilt the `/user` dashboard page as the Account page.
- Added read-only-by-default profile display with explicit edit/save/cancel flow.
- Removed nickname from the Account page UI.
- Added team creation UI and team discovery/search UI.
- Added direct join/leave team actions.
- Added hidden-by-default tag creation UI.
- Added tag display split into personal and team tags.
- Added object tagging UI on the lightcurve page.
- Added the Tagged page for browsing objects by tag.
- Added owner/admin-only member-management controls inside team cards.
- Added per-team user search and `Add to team` actions in the Account page.

## Recently Added Test Coverage

- `tarxiv/tests/test_api.py` covers the user/team/tag/tagged-object API contract and Swagger endpoints.
- `tarxiv/tests/test_database_user_integration.py` covers real Postgres-backed relational behavior.
- `tarxiv/tests/test_dashboard_user.py` now covers the new Account-page member-management logic:
  - owner/admin-only `Manage Members` rendering
  - hidden controls for non-admin memberships
  - manager open/close state handling
  - user-search callback behavior
  - add-member callback success/error handling

## Current State

The main relational account/team/tagging backend is in place and wired through the API and dashboard.

The Account page now supports:

- viewing and editing TarXiv-owned profile fields
- listing current team memberships
- creating teams
- searching for teams and joining/leaving them
- creating personal or team-owned tags
- owner/admin member-management with user search and add-member actions

The object-tagging flow is also in place:

- users can list visible tags
- users can assign tags to objects
- users can remove tag assignments they are allowed to manage
- users can browse tagged objects from the Tagged page

## Remaining Work

### Dashboard

- Add broader dashboard coverage for the Tagged page and object-tagging flows.
- Add more complete Account-page coverage around profile edit, create-team, create-tag, and join/leave interactions.
- Decide whether team member management should also show current team members and member roles.
- Decide whether add-member search results should immediately reflect newly-added members in a richer way than the current banner-only confirmation.

### Product/UX Decisions Still Deferred

- No moderated join-request workflow yet.
- No broader permissions model beyond authenticated access plus owner/admin add-member checks.
- No remove-member or change-role UI yet.
- No final cleanup yet for remaining nickname fallback references outside the Account page.

### Docs / Cleanup

- Keep `docs/orm-user-tags-plan.md` aligned with the implemented state as the branch evolves.
- Continue updating setup/deploy docs when the migration workflow changes.
- Eventually remove any stale references to `setup/postgres-init.sql` as the active schema path.

## Known Gaps / Risks

- Dashboard coverage is still unit-style and does not exercise a full browser-driven Dash flow.
- Team member management currently supports add-member only; it is not a full team administration UI.
- Some dashboard/auth display code outside the Account page still has `nickname` fallback logic.

## Suggested Next Steps

1. Add focused tests for the Tagged page and lightcurve object-tagging interactions.
2. Add Account-page tests for profile editing, team creation, tag creation, and join/leave flows.
3. Decide whether the next team-management pass should include member listing, removal, or role updates.
4. Clean up remaining `nickname` fallback references if they are no longer wanted.
