# Object page polish — round 2

**Date:** 2026-08-10
**Follows:** [`lightcurve-redesign-plan.md`](./lightcurve-redesign-plan.md) (the balanced-layout redesign; shipped)

Review notes from running the redesigned page under Compose, checked against
`mockups/mockup-2-balanced.html`. Each item below is a discrete change.

> **Doc convention.** This is a new file rather than an edit to the redesign
> plan. That plan records what was decided and shipped in the previous round;
> rewriting it would destroy that history and grow one doc past the point where
> an agent can hold it in context. Keep rounds in separate dated, cross-linked
> files.

## Two bugs found in the path of this work

- **Tag colours never render.** `render_tagging_panel` passed
  `color=(tag["color"] or "gray").lstrip("#")` into `dmc.Badge`'s *named-colour*
  prop, so `#4287f5` arrived as `4287f5`, which is not a Mantine palette key.
  The same markup (and bug) was duplicated in `pages/user.py::tag_section`.
- **Stale status text.** `search-status` was set to
  `"Searching for object: {id}"` and never cleared, so it still read
  "Searching…" after a successful load.

## Todo

- [x] **1. Off-white background.** Tokens were already right
      (`--tarxiv-bg: #f7f7f8`); Mantine's own body rule won the cascade and
      painted `#ffffff`. Set `bg="var(--tarxiv-bg)"` on the `dmc.AppShell` and
      add a `:root[data-mantine-color-scheme] body` rule to `_STATIC_CSS` so it
      outranks a bare `body` selector regardless of stylesheet order. Verify via
      computed style, not by eye.
- [x] **2. Card header icons.** `icon` parameter on `expressive_card`, rendered
      before the title in `.tarxiv-card-head` at `var(--tarxiv-ink-3)` to match
      `.card-head h2 svg` in the mockup. Lightcurve `clarity:curve-chart-line`,
      Sky view `mdi:earth`, Source metadata `mdi:table`, Citations
      `mdi:format-quote-close`, Tags `mdi:tag-outline`, JSON `mdi:code-json`.
- [x] **3. Shared `tag_badge` helper** in `components/cards.py`, passing the raw
      hex through as a CSS colour. Adopt in `render_tagging_panel` and
      `pages/user.py::tag_section` — fixes the colour bug in both and removes
      the duplication.
- [x] **4. Tag card layout.** Assigned tags become a compact wrapping row of
      chips *above* the select + assign row, replacing the stack of full-width
      bordered `Paper` rows. Keep the pattern-matching remove ids. Card gains
      `id="object-tag-card"` (scroll target) and the tag icon.
- [x] **5. Page head.** Drop the duplicated search controls; add a prominent
      `+ Tag` button and a `Cite` clipboard button. Read-only tag chips sit
      after the object-type badge in `html.Div(id="object-tag-chips")`.
      `_search_controls` stays — still used by the empty state.
- [x] **6. Populate head chips.** Server-render via the existing
      `fetch_object_tags` in `perform_search`, threaded through
      `format_object_metadata` → `build_page_head`. Keep live by adding a chips
      Output to `handle_assign_object_tag` / `handle_remove_object_tag` **only**
      — *not* to `load_object_tagging_panel`, which runs on the empty page where
      no head exists (the trap the `object-tagging-container` test guards).
- [x] **7. Drop the success banner** and clear the status text on success.
      Error/warning banners and the `message-banner` Box stay — `cone.py` also
      writes to that id.
- [x] **8. Centred content column** at `max-width: 1380px` inside
      `AppShellMain`, matching the mockup's `.container`. Topbar stays
      full-bleed.
- [x] **9. Scroll-to-tags.** New `assets/object_page.js` under the
      `window.dash_clientside.object_page` namespace (inline callback strings
      are unreliable under Dash 4 — see the comment in `lightcurve.py`).
      Smooth-scroll, focus the select, brief highlight.

### Done along the way

- [x] Tag badges no longer shout — Mantine upper-cases badges by default, which
      reads badly for user-authored tag names (`tt="none"`).
- [x] The JSON accordion icon is inline with its label; `AccordionControl`'s own
      `icon` prop renders at the far end of the row.
- [x] `handle_assign_object_tag` now logs a warning on a failed POST instead of
      silently re-rendering an unchanged panel, which looked like a no-op.

### Deferred / optional

- [ ] Surface that assign failure in the UI. `object-tagging-banner` exists in
      the panel but is still never written to — a user-visible message needs an
      extra Output on the assign callback.
- [ ] `api_base_url()` is duplicated verbatim between `lightcurve.py` and
      `tagged.py`; `fetch_api_data` still carries a "refactor to a shared API
      client" TODO.
- [ ] `dmc.ActionIcon` (2.6.0) rejects `title`; this has now bitten twice. If a
      third instance appears, add a lint rule or a helper wrapper.

## Verification — done

- 210 tests pass (201 at the start of this round, +9). New assertions:
  `tag_badge` keeps the `#` and falls back to gray; `build_tag_chips` renders
  one badge per assignment; `build_page_head` has `jump-to-tags`/`cite-copy`/
  `object-tag-chips` and no `object-id-input`; the tagging panel keeps
  `object-tag-card` and its pattern-matching remove ids.
- `ruff check` and `ruff format` clean.
- Verified in-browser against a harness that renders the **real** shell from
  `create_layout()` with the object page injected into its `page-content` slot,
  rather than rebuilding the shell (the substitution that hid the `visibleFrom`
  bug last round). Confirmed by computed style, not by eye:
  `body` = `rgb(247,247,248)` on `#ffffff` cards; content column capped at
  1380px; dark mode `rgb(18,22,23)`. Also confirmed: icons on all six cards,
  four tag chips on one line above the select, correct tag colours in both
  schemes, +Tag scrolling the card into view with the select focused.

**Not verified:** the live API round trip (assign/remove actually updating the
head chips, and the Cite button copying) needs the Compose stack — the harness
has no API behind it.
