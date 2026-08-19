# Implement "Balanced" Lightcurve Page Redesign in Dash

## Context

The mockup phase produced four standalone HTML prototypes in `mockups/`; Jack approved **mockup 2 — balanced** (`mockups/mockup-2-balanced.html`, tokens in `mockups/shared.css`, widget logic in `mockups/shared.js`). This plan implements it in the real app (`tarxiv/dashboard/`, Dash 4.0.0 + dash-mantine-components 2.6.0).

Decisions confirmed with Jack:
- **Topbar app-wide**: replace the 100px left icon rail with a slim 52px top navbar on every page.
- **App-wide design system**: new tokens (Inter/JetBrains Mono, 14px bordered cards, real red ramp) via shared components; other pages keep their layouts.
- **Plot ⇄ Table toggle** on the lightcurve card (also the a11y relief channel for the amber filter colour).
- **Compact search row** in the page head; centred search card as the empty state.

The mockups stay untracked reference material; `mockups/shared.css`/`shared.js` are the source of truth for token values, the validated filter palette, and the Plotly layout spec.

## Status: implemented

All six phases are done; 194 tests pass and `ruff check` is clean. Two things changed from the plan below during implementation — both deliberate:

1. **`format_object_metadata` returns a 4-tuple**, `(results_top, metadata_card, citations_card, full_metadata)`, and takes a new `lc_data` argument. The balanced lower grid pairs the metadata card with the tagging container, and the tagging container must stay in the base layout (its callbacks fire on initial load), so the metadata card has to be handed back separately. The two test unpack sites were updated; every id assertion is unchanged.
2. **Marker symbol encodes the band, not the survey.** The plan had symbol carrying the survey, which left ZTF g and ZTF r both circles — and the green/red pair measures ΔE 6.9 under deuteranopia, inside the 6–8 band that is only legal *with* a secondary encoding. Shape therefore moves with hue instead. The consequence is that the same bandpass from two surveys renders identically; that is scientifically honest (it is the same measurement) and the legend groups plus the table view disambiguate.

Palette validation (dataviz `validate_palette.js`, all-pairs/scatter pairlist, against `#ffffff` and `#1c2224`): the four bands that actually co-occur in TarXiv data — g, r, c, o — pass every gate in both schemes. Rarer bands (u, V, i, z, w) sit past the documented four-series all-pairs cap; all are inside the lightness band with chroma above the floor, and lean on symbol + legend + table for identity. Amber `o` and magenta `z` are sub-3:1 on the light surface, for which the Plot⇄Table toggle is the required relief channel.

Not verified end-to-end: the dashboard needs Couchbase + the API, so the real `/lightcurve/<id>` round trip is untested. Verification used a standalone harness rendering the actual components with sample SN 2023ixf data — topbar, key facts, plot (both schemes), Plot⇄Table, Aladin, metadata tabs, citations, JSON accordion and footer all confirmed in light and dark at 1512×801 and 1280×800. Run the docker-compose dev stack for a live pass.

## Phasing (6 commits, each runnable + tests green)

### Phase 1 — Design tokens + theme foundation
**`tarxiv/dashboard/styles.py`**
- New `COLORS` = `{"primary": "#b31b1b", "light": {...}, "dark": {...}}` with the full token set from `mockups/shared.css` (bg, card, card_2, border, border_strong, ink/ink_2/ink_3, primary_hover, primary_ink — `#e06058` on dark, primary_soft/_2, grid, axis, shadow, shadow_lg).
- `ARXIV_RED_RAMP` — real 10-step scale, index 6 = `#b31b1b`.
- Replace `FILTER_COLORS` with `FILTER_STYLE` keyed by `(survey, filter)` — validated values from `mockups/shared.js`: `("ztf","g") #199e70 circle`, `("ztf","r") #e34948 square`, `("atlas","c") #2a78d6/#3987e5 diamond`, `("atlas","o") #eda100/#c98500 triangle-up` — plus `FILTER_FALLBACK` by filter only (u/g/c/V/r/o/i/z/w/Unknown, wavelength-ordered hues, light+dark, distinct symbols) and `resolve_filter_style(survey, filter)` (normalises survey lowercase, `"R"`→`"r"`; exact → filter fallback → Unknown). **Re-run the dataviz palette validator** on the fallback hexes vs `#ffffff`/`#1c2224`; symbols cover warn-band pairs, fix any fail-band pair.
- Delete ~11 dead style dicts (NAVBAR/NAV_TITLE/NAV_RIGHT/USER_CHIP/LOGIN/SIGNUP/PROFILE_BUTTON/AUTH_MODAL_*/PROFILE_DRAWER_*). Keep + tokenise `CARD_STYLE` (cone); keep `AVATAR_STYLE(S)` (auth.py), `BUTTON_STYLE`+`ORCID_BUTTON_STYLE` (user.py).

**`tarxiv/dashboard/components/theme_manager.py`**
- `THEME`: `colors.arxiv_red = ARXIV_RED_RAMP`, `primaryShade {"light": 6, "dark": 5}`, `fontFamily` Inter stack, `fontFamilyMonospace` JetBrains Mono stack, `headings` (Inter, 700), `defaultRadius "md"`, component defaults (inputs/buttons `size="sm"`, `Paper {"radius": 14}`).
- `generate_css()`: write path derived from `__file__` (fixes the cwd TODO at line ~126). Emit new `--tarxiv-*` vars per `:root[data-mantine-color-scheme=…]` by looping `COLORS["light"]/["dark"]`, **keep legacy aliases** (`--tarxiv-color-primary`, `--tarxiv-card-1`→card, `--tarxiv-surface-1/-2`→card_2, `--tarxiv-footer-bg`→`#1c2224` in both modes). Delete the `nav_hover` block; add static `.tarxiv-topnav-link` (+ `.active`), `.tarxiv-card-head`, `.tarxiv-wordmark` classes mirroring `mockups/shared.css`.
- `register_tarxiv_templates()`: rebuild `tarxiv_light`/`tarxiv_dark` **from `COLORS`** mirroring `lightcurveLayout()` in `mockups/shared.js`: paper/plot bg = card colour (fixes the `#1A1B1E` dark mismatch), Inter font, tokenised grid/axis/tick styling, horizontal legend (x 0, y 1.02, grouptitlefont), inverted hoverlabel, margins l52/r12/t12/b42. **Do not rename the templates** — the strings double as `active-settings-store.theme` values.
- Delete `get_filter_style` (only consumer was plots.py) + its `components/__init__.py` export.

**`tarxiv/dashboard/app.py`**: add `external_stylesheets=[Google Fonts css2 Inter 400–700 + JetBrains Mono 400/600]`. (Accepted CDN dependency — Aladin already is one; self-host woff2 later if offline matters.)

### Phase 2 — App shell: top navbar
**`tarxiv/dashboard/layouts/main_layout.py`** (stores, cookie popup, auth, footer, `url`/`page-content` unchanged)
- `dmc.AppShell(id="app-shell", header={"height": 52}, navbar={"width": 260, "breakpoint": "sm", "collapsed": {"mobile": True, "desktop": True}}, padding="md")` — drop `layout="alt"`.
- `dmc.AppShellHeader` (all breakpoints): Burger (`hiddenFrom="sm"`) · wordmark `dcc.Link` ("tar" + red "X" + "iv") · `html.Div(id="topbar-nav", visibleFrom="sm")` · spacer · global search (`dash_extensions.Keyboard` wrapping `dmc.TextInput(id="global-search-input", w=220, size="xs")`, `id="global-search-keyboard"`, `visibleFrom="md"`) · theme toggle `dmc.ActionIcon(id="color-scheme-toggle", children=DashIconify(id="theme-icon", ...))` — **both ids preserved** so `style_callbacks.py` theme callbacks keep working · account avatar chip (adapt `account_nav_hovercard`, `position="bottom-end"`, keep `nav-logout-button`).
- `dmc.AppShellNavbar` → mobile-only drawer with `html.Div(id="mobile-nav-content")`; nav clicks full-reload (`url` has `refresh=True`) so no close-callback needed.
- Cleanup: `cookie_callbacks.py` imports `SETTING_DEFAULTS` from main_layout instead of duplicating; delete `create_nav_item`/`create_nav_link` from cards.py after re-grep for users.

**`tarxiv/dashboard/callbacks/style_callbacks.py`**
- Retarget `refresh_navigation` → `[Output("topbar-nav","children"), Output("mobile-nav-content","children")]`; topbar = `dcc.Link(className="tarxiv-topnav-link"...)`, mobile = `dmc.NavLink` with icons.
- New `global_search` callback: `Output("url","pathname", allow_duplicate=True)`, `Input("global-search-keyboard","n_keydowns")`, `State("global-search-input","value")` → `/lightcurve/{value}`. Coexists with lightcurve's `search_navigation` (both allow_duplicate).
- New burger callback: `Patch()` on `app-shell.navbar` → `["collapsed"]["mobile"] = not opened` (fixes currently-dead mobile burger).

### Phase 3 — Shared component restyle
**`tarxiv/dashboard/components/cards.py`**
- `title_card` — same signature; compact left-aligned `dmc.Title(fz=26)` + dimmed subtitle (kills the 90px red banner on all 6 pages).
- `expressive_card(children, title=None, title_order=2, header_extra=None, **kwargs)` — `dmc.Paper(radius=14, p=0, bg var(--tarxiv-card), border var(--tarxiv-border), boxShadow var(--tarxiv-shadow), overflow hidden)`; titled cards get a `.tarxiv-card-head` divider row (title fz13 fw600 + optional `header_extra`), body `dmc.Box(p="md")`. Merge caller `style`, don't clobber.
- `footer_card` — keep dark strip via alias, `p="md"`, top border.
- `create_message_banner` — replace hardcoded `color_map` with Mantine `dmc.Alert` colors (success→green, error→red, warning→yellow, info→blue), `variant="light"`; signature unchanged (~50 call sites untouched, dark mode fixed).
- Spot-fix: `pages/user.py` ColorInput `swatches` from the new categorical hexes.

### Phase 4 — Plot rebuild
**`tarxiv/dashboard/components/plots.py`** — `create_lightcurve_plot` signature unchanged:
- `scheme` from template name; `surface = COLORS[scheme]["card"]`; per group `style = resolve_filter_style(survey, filter)`, trace `name = f"{survey.upper()} {filter}"`.
- Detections: symbol per style, `marker.line {width 1, color surface}`, `error_y {width 0, thickness 1.2, color}`, `customdata=errs`, hovertemplate `"<b>{label}</b>  MJD %{x:.2f}<br>%{y:.2f} ± %{customdata:.2f} mag<extra></extra>"` (no-± variant when no errors), `legendgroup=survey` + grouptitle.
- Limits: `triangle-down-open`, size 9, opacity 0.55, `showlegend=False` (behaviour change from today — grouped legend + hover covers it), own hovertemplate.
- Layout: no title (card head owns it), `height=430`, `xaxis tickformat "d"`, y reversed "Apparent magnitude"; legend/fonts/margins come from the new templates — don't repeat per-figure.
- `empty_lightcurve_plot`: restyle only (height 430, no title); **keep the test contract**: 0 traces, hidden axes, exactly 1 translucent rect shape, centred annotation, default text `"No lightcurve data available"`, custom `message` honoured.

### Phase 5 — Balanced lightcurve page
**New `tarxiv/dashboard/components/object_view.py`** (all pure/unit-testable where possible):
- `build_key_facts(meta, lc_data) -> list[dict]` — 6 facts `{label, value, unit}` with em-dash fallbacks. **Data gotchas (verified in pipeline code)**: host is under `tns["hostname"]` (not `host_name`), else `sherlock.catalogue_object_id`; redshift prefers `tns.redshift` over `sherlock.redshift`; peak mag = min across every source's `peak_mags` (plural) list where the magnitude value sits under the key **`"limit"`** (writer quirk in `data_sources.py::summarize_lc_mags`); distance from `sherlock.best_distance` (+" Mpc" when numeric); detections counted from `lc_data` (`detection==1`) with survey list as unit.
- `build_page_head(object_id, meta)` — title + `dmc.Badge` type chip + `_build_coordinates_header` (keeps id `object-coordinates`) + spacer + compact search (`object-id-input`/`search-id-keyboard`/`search-id-button` ids kept → existing `search_navigation` callback untouched).
- `build_summary_strip(facts)` — card-styled `dmc.SimpleGrid(cols={"base":2,"sm":3,"lg":6})`.
- `build_hero_grid(object_id)` — Grid `span {base:12, lg:7}`: lightcurve card with `header_extra=dmc.SegmentedControl(id="lc-view-toggle", data=["Plot","Table"], size="xs")`, body `html.Div(id="lc-plot-wrap")` (Loading + `dcc.Graph(id={"type":"themeable-plot","index":"lightcurve-plot"}, style height 430, config responsive)`) + `html.Div(id="lc-table-wrap", style display none)`; `span {base:12, lg:5}`: Sky-view card with `aladin-status-dummy` + `aladin-lite-div` (430px).
- `build_photometry_table(lc_data, scheme)` — `dmc.ScrollArea(h=430)` + `dmc.Table` sorted by MJD: MJD (mono) | Filter (colour swatch via `resolve_filter_style` + "SURVEY filter") | Mag (`"> {limit:.2f}"` for limits) | σ (dash for limits) | Type; `detection==-1` excluded.
- `build_empty_search_state(prefill=None)` — centred search card (same search ids).

**`cards.py::format_object_metadata`** — rewrite; **returns a 4-tuple** `(results_top, metadata_card, citations_card, full_metadata)` and gains `lc_data=None` param (the 3-tuple can't express the balanced lower grid, since `object-tagging-container` lives in the base layout — tests forbid it inside these pieces). `results_top` = page head + summary strip + hero grid; `metadata_card` = titled card + `ScrollArea(_build_metadata_tabs, h=420)`; citations keeps `citation-bibtex` + Clipboard; JSON accordion restyled, ids unchanged. Add `FIELD_LABELS` entries for the keys the pipeline actually writes: `hostname`, `peak_mags`, `latest_detections`, `latest_non_detections`. Delete `ALADIN_HEIGHT_PX`.

**`pages/lightcurve.py`**
- `perform_search` passes `lc_data` into `format_object_metadata`, returns the extra piece; `layout()` composes: stores · `message-banner` · `search-status` · `results-container`(results_top | empty state) · lower Grid (`metadata_card` span 7 / Stack(`object-tagging-container` div, citations) span 5) · `full_metadata`. Ids `lightcurve-store`, `results-container`, `object-tagging-container` preserved (test contract); `title_card` + big search card deleted.
- New toggle callback: `Output lc-plot-wrap.style / lc-table-wrap.style / lc-table-wrap.children`, `Input lc-view-toggle.value + active-settings-store.data` (theme-synced swatches), `State lightcurve-store.data`. Optional clientside `Plotly.Plots.resize` on switch-back.
- **Aladin**: delete the inline JS string (lines ~205–253); new `assets/lightcurve_aladin.js` with `window.dash_clientside.lightcurve_aladin.initialize` following the `cone_aladin.js` namespace pattern (drop the body-wide MutationObserver; poll for `#aladin-lite-div` + `window.A` like cone does). Options: survey `P/PanSTARRS/DR1/color-z-zg-g`, **fov 0.1**, `reticleColor #e34948`, marker at target. Wire via `ClientsideFunction`.

### Phase 6 — Tests
- Must pass unchanged: `test_dashboard_plots.py` empty-state contract; lightcurve empty-layout id tests; coordinates-header + `_extract_object_coordinates` tests; cone/tagged/user suites.
- Mechanical update: `test_format_object_metadata_pieces` + `test_coordinates_header_omitted_without_coordinates` (`tarxiv/tests/test_dashboard_lightcurve.py:119,138`) unpack 4 pieces; id assertions unchanged.
- New: `test_object_view.py` (`build_key_facts` — hostname quirk, peak-mag-under-"limit" quirk, redshift preference, detection counts, all-missing; `build_photometry_table` — sort/limits/σ/-1 exclusion); `resolve_filter_style` tests (exact hits both schemes, R→r, filter fallback, Unknown); extend plots tests (trace name "ZTF g", symbol, error_y 1.2/0, hovertemplate, limit showlegend False, tickformat "d").

## Risks
- Cone page shares ids `results-container`/`search-status`/`message-banner` and owns callbacks to them — lightcurve keeps its instances, gains no callbacks on those ids.
- `"tarxiv_light"/"tarxiv_dark"` strings are both store values and template names — never renamed.
- `color-scheme-toggle` + `theme-icon` ids must exist in the new header or theme callbacks break.
- Cold-load theme flash is pre-existing behaviour, out of scope (optional later: index_string inline script).
- Hidden-graph resize on Plot⇄Table toggle — responsive config + optional clientside resize.

## Verification
1. `uv run pytest tarxiv/tests/test_dashboard_lightcurve.py tarxiv/tests/test_dashboard_plots.py tarxiv/tests/test_dashboard_cone.py tarxiv/tests/test_dashboard_tagged.py tarxiv/tests/test_dashboard_user.py` after each phase.
2. Run app: `uv run python bin/run_dashboard.py --debug --host 127.0.0.1` (needs the API reachable — dev docker-compose stack for a full pass).
3. Manual: topbar on all 6 pages + active state; theme toggle (cards, banner, plot template, table swatches); mobile burger; `/lightcurve` empty state; `/lightcurve/<real id>` — page head/type chip/coord copy, 6-fact strip, plot (symbols, grouped horizontal legend, hover ±err, MJD ticks), Plot⇄Table, Aladin fov 0.1, metadata tabs, tag assign/remove, BibTeX copy, JSON accordion; cone page unaffected; global topbar search navigates from any page.
