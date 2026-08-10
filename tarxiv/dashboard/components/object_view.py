"""Builders for the object (lightcurve) page.

The page follows the "balanced" layout: a compact head row, a strip of key
facts, then the lightcurve and sky view side by side above the fold, with the
full per-source metadata, tags and citations below.

Everything here is a pure function of the metadata/photometry documents so the
layout can be unit tested without a running Dash app.
"""

import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from ..styles import band_color
from .plots import PLOT_HEIGHT_PX, series_label

# Placeholder for any missing value; matches cards.EM_DASH.
EM_DASH = "—"


# --------------------------------------------------------------------------
# Key facts
# --------------------------------------------------------------------------


def _sources(meta: dict) -> dict:
    sources = meta.get("data_sources") or {}
    return sources if isinstance(sources, dict) else {}


def _first_present(meta: dict, source_keys: list[str], field: str):
    """First non-None ``field`` across the named sources, in preference order."""
    sources = _sources(meta)
    for key in source_keys:
        payload = sources.get(key)
        if isinstance(payload, dict) and payload.get(field) is not None:
            return payload[field]
    return None


def _fact(label: str, value, unit: str | None = None) -> dict:
    return {
        "label": label,
        "value": EM_DASH if value is None or value == "" else str(value),
        "unit": unit,
    }


def _format_number(value, spec: str):
    """Format a value with ``spec`` when it is numeric, else pass it through."""
    try:
        return format(float(value), spec)
    except (TypeError, ValueError):
        return value


def _peak_magnitude(meta: dict) -> tuple[float | None, str | None]:
    """Brightest (numerically smallest) peak magnitude across all sources.

    ``summarize_lc_mags`` (tarxiv/data_sources.py) writes a ``peak_mags`` list
    per survey payload, and stores the magnitude value under the key ``limit``
    rather than ``mag``. Handle both so this keeps working if that is fixed.
    """
    best_mag: float | None = None
    best_filter: str | None = None

    for payload in _sources(meta).values():
        if not isinstance(payload, dict):
            continue
        entries = payload.get("peak_mags") or payload.get("peak_mag") or []
        if isinstance(entries, dict):
            entries = [entries]
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            raw = entry.get("limit", entry.get("mag", entry.get("value")))
            try:
                mag = float(raw)
            except (TypeError, ValueError):
                continue
            if best_mag is None or mag < best_mag:
                best_mag = mag
                best_filter = entry.get("filter")

    return best_mag, best_filter


def _detection_summary(lc_data) -> tuple[int | None, str | None]:
    """Count detections and list the surveys contributing them."""
    if not lc_data:
        return None, None

    count = 0
    surveys: set[str] = set()
    for point in lc_data:
        if not isinstance(point, dict):
            continue
        if point.get("detection") == 1:
            count += 1
            survey = point.get("survey")
            if survey:
                surveys.add(str(survey).upper())

    unit = " + ".join(sorted(surveys)) if surveys else None
    return count, unit


def build_key_facts(meta: dict, lc_data=None) -> list[dict]:
    """Build the six summary facts shown in the strip under the page head.

    Returns a list of ``{"label", "value", "unit"}`` dicts, using an em-dash
    for anything the record does not carry.
    """
    meta = meta or {}

    # TNS is the authoritative classification source; Sherlock is the fallback.
    redshift = _first_present(meta, ["tns", "sherlock"], "redshift")

    # TNS writes the host under "hostname" (not "host_name").
    host = _first_present(meta, ["tns"], "hostname") or _first_present(
        meta, ["tns"], "host_name"
    )
    if host is None:
        host = _first_present(meta, ["sherlock"], "catalogue_object_id")

    discovery = meta.get("discovery_date") or _first_present(
        meta, ["tns"], "discovery_date"
    )
    if isinstance(discovery, str) and discovery:
        # Trim "2023-05-19 17:27:15" / ISO "T" forms down to the date.
        discovery = discovery.replace("T", " ").split(" ")[0]
    reporting_group = _first_present(meta, ["tns"], "reporting_group")

    peak_mag, peak_filter = _peak_magnitude(meta)
    distance = _first_present(meta, ["sherlock"], "best_distance")
    detections, detection_surveys = _detection_summary(lc_data)

    return [
        _fact("Redshift", _format_number(redshift, ".4g") if redshift else None),
        _fact("Host", host),
        _fact("Discovered", discovery, reporting_group),
        _fact(
            "Peak mag",
            f"{peak_mag:.1f}" if peak_mag is not None else None,
            peak_filter,
        ),
        _fact(
            "Distance",
            _format_number(distance, ".2f") if distance is not None else None,
            "Mpc" if isinstance(distance, (int, float)) else None,
        ),
        _fact("Detections", detections, detection_surveys),
    ]


# --------------------------------------------------------------------------
# Layout pieces
# --------------------------------------------------------------------------


def _search_controls(prefill: str | None = None, width: int = 220, size: str = "xs"):
    """Object-ID search input + button.

    Keeps the ``object-id-input`` / ``search-id-keyboard`` / ``search-id-button``
    ids so the existing ``search_navigation`` callback drives navigation.
    """
    from dash_extensions import Keyboard

    return [
        Keyboard(
            id="search-id-keyboard",
            captureKeys=["Enter"],
            n_keydowns=0,
            children=[
                dmc.TextInput(
                    id="object-id-input",
                    placeholder="Object ID, e.g. 2023ixf",
                    value=prefill or "",
                    size=size,
                    w=width,
                    leftSection=DashIconify(icon="mdi:magnify", width=16),
                )
            ],
        ),
        dmc.Button("Search", id="search-id-button", size=size, variant="default"),
    ]


def build_page_head(object_id: str, meta: dict, coordinates_header=None):
    """Compact identity row: name, type chip, coordinates and search."""
    object_type = _first_present(meta or {}, ["tns"], "object_type")

    left = [
        dmc.Title(object_id, order=1, fz=24, fw=700, style={"letterSpacing": "-0.02em"})
    ]
    if object_type:
        left.append(
            dmc.Badge(object_type, variant="light", color="arxiv_red", size="lg")
        )
    if coordinates_header is not None:
        left.append(coordinates_header)

    return dmc.Group(
        [
            dmc.Group(left, gap="sm", align="center", wrap="wrap"),
            dmc.Group(
                _search_controls(prefill=object_id),
                gap="xs",
                wrap="nowrap",
                visibleFrom="sm",
            ),
        ],
        justify="space-between",
        align="center",
        wrap="wrap",
        gap="sm",
    )


def build_summary_strip(facts: list[dict]):
    """Card-styled strip of key facts; the "no scrolling" payload."""
    tiles = []
    for index, fact in enumerate(facts):
        value_children = [fact["value"]]
        if fact.get("unit"):
            value_children.append(
                dmc.Text(fact["unit"], span=True, size="xs", c="dimmed", fw=500, ml=4)
            )
        tiles.append(
            dmc.Box(
                [
                    dmc.Text(
                        fact["label"],
                        size="10.5px",
                        fw=600,
                        c="dimmed",
                        tt="uppercase",
                        style={"letterSpacing": "0.07em"},
                    ),
                    dmc.Text(value_children, size="15px", fw=600),
                ],
                # Hairline separators between tiles, not before the first.
                pl="md" if index else 0,
                style={
                    "borderLeft": "1px solid var(--tarxiv-border)" if index else "none",
                    "minWidth": 0,
                },
            )
        )

    return dmc.Paper(
        dmc.SimpleGrid(tiles, cols={"base": 2, "sm": 3, "lg": 6}, spacing="md"),
        p="md",
        radius=14,
        style={
            "backgroundColor": "var(--tarxiv-card)",
            "border": "1px solid var(--tarxiv-border)",
            "boxShadow": "var(--tarxiv-shadow)",
        },
    )


def build_hero_grid(object_id: str, lightcurve_card, sky_card):
    """Lightcurve (7 cols) beside the sky view (5 cols), equal heights."""
    return dmc.Grid(
        [
            dmc.GridCol(lightcurve_card, span={"base": 12, "lg": 7}),
            dmc.GridCol(sky_card, span={"base": 12, "lg": 5}),
        ],
        gutter="md",
        align="stretch",
    )


def build_lightcurve_body():
    """Graph and (initially hidden) photometry table, toggled by the segment."""
    return [
        html.Div(
            dcc.Loading(
                dcc.Graph(
                    id={"type": "themeable-plot", "index": "lightcurve-plot"},
                    style={"height": f"{PLOT_HEIGHT_PX}px", "width": "100%"},
                    config={"responsive": True, "displaylogo": False},
                ),
                type="default",
            ),
            id="lc-plot-wrap",
        ),
        html.Div(id="lc-table-wrap", style={"display": "none"}),
    ]


def build_view_toggle():
    """Plot/Table switch for the lightcurve card header.

    The table is also the accessible fallback for the two band colours that
    sit below 3:1 contrast on the light surface (see styles.BAND_COLORS).
    """
    return dmc.SegmentedControl(
        id="lc-view-toggle",
        value="Plot",
        data=["Plot", "Table"],
        size="xs",
        radius="md",
    )


def build_photometry_table(lc_data, scheme: str = "light"):
    """Sortable-by-epoch photometry table used by the Table view."""
    rows = []
    for point in lc_data or []:
        if not isinstance(point, dict):
            continue
        detection = point.get("detection")
        mjd = point.get("mjd")
        if mjd is None or detection not in (0, 1):
            # -1 marks bad-quality points, which the plot also drops.
            continue

        band = point.get("filter")
        survey = point.get("survey")
        if detection == 1:
            mag = point.get("mag")
            mag_text = f"{mag:.2f}" if isinstance(mag, (int, float)) else EM_DASH
            err = point.get("mag_err")
            err_text = f"{err:.2f}" if isinstance(err, (int, float)) else EM_DASH
            kind = "detection"
        else:
            limit = point.get("limit")
            mag_text = f"> {limit:.2f}" if isinstance(limit, (int, float)) else EM_DASH
            err_text = EM_DASH
            kind = "limit"

        rows.append((
            mjd,
            dmc.TableTr([
                dmc.TableTd(f"{mjd:.2f}", ff="monospace"),
                dmc.TableTd(
                    dmc.Group(
                        [
                            dmc.Box(
                                w=9,
                                h=9,
                                style={
                                    "backgroundColor": band_color(band, scheme),
                                    "borderRadius": "3px",
                                    "flexShrink": 0,
                                },
                            ),
                            dmc.Text(series_label(survey, band), size="xs"),
                        ],
                        gap=7,
                        wrap="nowrap",
                    )
                ),
                dmc.TableTd(mag_text, ff="monospace"),
                dmc.TableTd(err_text, ff="monospace"),
                dmc.TableTd(dmc.Text(kind, size="xs", c="dimmed")),
            ]),
        ))

    if not rows:
        return dmc.Box(
            dmc.Text("No photometry available", size="sm", c="dimmed", ta="center"),
            py="xl",
        )

    rows.sort(key=lambda item: item[0])

    return dmc.ScrollArea(
        dmc.Table(
            [
                dmc.TableThead(
                    dmc.TableTr([
                        dmc.TableTh("MJD"),
                        dmc.TableTh("Filter"),
                        dmc.TableTh("Mag"),
                        dmc.TableTh("σ"),
                        dmc.TableTh("Type"),
                    ])
                ),
                dmc.TableTbody([row for _, row in rows]),
            ],
            highlightOnHover=True,
            stickyHeader=True,
            fz="xs",
            verticalSpacing=6,
        ),
        h=PLOT_HEIGHT_PX,
        type="auto",
        offsetScrollbars=True,
    )


def build_empty_search_state(prefill: str | None = None):
    """Centred search card shown when no object is selected."""
    return dmc.Center(
        dmc.Paper(
            dmc.Stack(
                [
                    dmc.Title("Explore a transient", order=2, fz=22, ta="center"),
                    dmc.Text(
                        "Enter a TarXiv or survey object ID to see its lightcurve, "
                        "sky position and cross-matched metadata.",
                        size="sm",
                        c="dimmed",
                        ta="center",
                        maw=420,
                    ),
                    dmc.Group(
                        _search_controls(prefill=prefill, width=280, size="sm"),
                        gap="xs",
                        justify="center",
                    ),
                ],
                gap="md",
                align="center",
            ),
            p="xl",
            radius=14,
            maw=560,
            w="100%",
            style={
                "backgroundColor": "var(--tarxiv-card)",
                "border": "1px solid var(--tarxiv-border)",
                "boxShadow": "var(--tarxiv-shadow)",
            },
        ),
        py=40,
    )
