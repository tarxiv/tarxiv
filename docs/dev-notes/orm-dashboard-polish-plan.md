# Account Page Polish & Dashboard Cleanup Plan

## Context

The `jb/orm` branch added a relational account/team/tag backend and wired it through
the API and the Dash dashboard. The backend contract is stable; the remaining work is
UI polish and cleanup. This plan turns the pre-commit checklist at the end of
`docs/orm-user-tags-plan.md` — plus the loose ends listed in
`docs/orm-user-tags-status.md` — into a concrete change set.

Decisions confirmed:
- **Account page → tabs** (Profile / Teams / Tags) on the same `/user` route. No new routes.
- **API token → defer.** Keep showing the session JWT; just relabel + add a copy button. No PAT backend.
- **Team policy → keep direct add/join.** Defer invite-flow and team-creation limits to future work.
- **Profile image → polish the URL input only.** No file-upload / storage backend.

## Key files

- `tarxiv/dashboard/pages/user.py` — Account page (layout, render helpers, callbacks). Primary file.
- `tarxiv/dashboard/pages/alerts.py` — remove tag filtering.
- `tarxiv/dashboard/layouts/main_layout.py` — nav rail / Account button.
- `tarxiv/dashboard/components/cards.py` — `create_nav_link`, `create_message_banner`.
- `tarxiv/api.py` — add `GET /teams/<team_id>/members`.
- `tarxiv/database_user.py` — add `list_team_members()`.
- `tarxiv/dto.py` — DTO for member listing.
- `tarxiv/openapi.py` — document the new members endpoint.
- `tarxiv/tests/test_api.py`, `test_database_user_integration.py`, `test_dashboard_user.py`.

## Backend changes

### 1. List team members (new endpoint)
The "Manage Members" UI can currently only add members, not show them. Add the read path:
- `database_user.py`: `list_team_members(team_id, requesting_user_id)` — verify the
  requester is a member (reuse `_ensure_team_membership`), then return the team's
  memberships with `user_id`, `role`, `created_at`, and joined user summary fields
  (username/forename/surname/email). Mirror the shape used by `search_users` and
  `list_user_teams`.
- `api.py`: `GET /teams/<team_id>/members` — auth via `_require_authenticated_user_id`,
  403 if not a member.
- `openapi.py`: add the spec entry next to the existing POST members entry.
- Tests: API contract test + integration test (member visible to members, 403 for non-members).

## Dashboard changes — `user.py`

### 2. Restructure into tabs
Wrap the existing Profile / Teams / Tags sections in `dmc.Tabs` (`Profile`, `Teams`,
`Tags`) inside `layout()`. Keep the same component IDs and `dcc.Store`s so existing
callbacks keep working — only the surrounding container changes. Keep the auth/user chip
+ relabeled API-token group in the Profile tab.

### 3. Team management polish
- **List members:** extend `render_team_member_manager` to render a member list (new
  `team_member_list_block`) fed by `GET /teams/<team_id>/members`. Load it when the
  manager opens (`toggle_team_member_manager`).
- **Add confirmation:** in `add_team_member`, on success show a clear success banner.
- **Refresh search list on add:** after a successful add, refresh the member list and drop
  the added user from the search results.

### 4. Tag UI polish
- **Colour picker:** replace the plain hex `TextInput` (`new-tag-color`) with
  `dmc.ColorInput` (keeps a hex string value, compatible with `create_tag` and badge rendering).
- **Empty taglist state:** give `tag_block` / `tag_section` a friendly empty-state message.

### 5. Profile polish
- **Username generator:** add a "Suggest" button next to the username field that fills a
  generated suggestion. Client-side/Dash callback; no backend needed.
- **Image URL polish:** keep the `picture_url` TextInput but add a small live preview
  (reuse `avatar_image`) and basic URL validation feedback.

### 6. Banner location
Place the banner adjacent to the action that triggered it (within the active tab) so
confirmations appear in context. Apply consistently to profile-save, team, and tag callbacks.

### 7. API token relabel
Relabel the `api-token-group` to make clear this is a session token, add a
copy-to-clipboard button (`dcc.Clipboard`). Leave a `# TODO: replace with real personal
access tokens` note.

### 8. Account button hover card (nav)
Add a `dmc.HoverCard` on the Account nav button showing a quick profile summary (avatar,
name, email, logout).

## Dashboard changes — `alerts.py`

### 9. Remove tag filtering from Alerts
Remove the `alerts-tag-filter` `MultiSelect`, its `Input` in `update_alerts_table`, the
`tag_ids` argument passed to the fetch helper, the tag-options init, and `fetch_visible_tags`
if unused elsewhere. Update the callback signature/returns accordingly.

## Cleanup (from status doc remaining work)

### 10. Nickname fallbacks
Remove remaining `nickname` fallback references outside the Account page now that username
is the product field.

### 11. Stale schema reference
Confirm `setup/postgres-init.sql` is no longer on the active setup path (Alembic owns the
schema); remove or clearly mark it deprecated, and fix any docs that still point to it.

## Deferred (out of scope this pass)
- Personal access token (PAT) system.
- Team invite/approval workflow and team-creation permission gating.
- Profile image file upload + storage backend.
- Remove-member / change-role team admin UI (only add + list this pass).

## Verification

- **Unit/dashboard tests:** extend `test_dashboard_user.py` for the member-list render,
  add-member confirmation/refresh, tab layout sanity, colour input, and empty-tag state.
  Add Tagged-page and lightcurve-tagging dashboard tests.
- **API tests:** `test_api.py` — `GET /teams/<team_id>/members` contract; integration test
  in `test_database_user_integration.py` for member-visibility + non-member 403.
- **Manual run:** start the dashboard, sign in, confirm tabs, manage-members listing +
  refresh + confirmation, colour picker, empty tag state, username suggest, image preview,
  Account nav hover card, and that Alerts no longer shows a tag filter and still loads.
- Run the full test suite (`pytest`) before committing.
