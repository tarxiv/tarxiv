"""Card components for displaying object data."""

import json
import math
from typing import Literal

import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

from ..styles import CARD_STYLE


def title_card(title_text: str, subtitle_text: str | None = None, **kwargs):
    """Create a styled title card.

    Args:
        title_text: Main title text
        subtitle_text: Optional subtitle text
        **kwargs: Additional keyword arguments for dmc.Paper

    Returns
    -------
        dmc.Paper component styled as a title card
    """
    children = []
    children.append(
        dmc.Title(
            title_text,
            order=1,
            style={"marginBottom": "0px", "fontSize": "90px"},
        )
    )
    if subtitle_text:
        children.append(
            dmc.Text(
                subtitle_text,
            )
        )

    return dmc.Paper(
        children=dmc.Stack(
            children=children,
            align="center",
        ),
        p="xl",
        radius=28,
        style={
            "backgroundColor": "var(--tarxiv-color-primary)",
            "color": "white",
            "textAlign": "center",
        },
        **kwargs,
    )


def footer_card():
    """Create a styled footer card with 3 logos.

    Returns
    -------
        dmc.Paper component styled as a footer card
    """
    return dmc.Paper(
        children=dmc.Flex(
            children=[  # get images from assets folder
                html.Img(src="/assets/oxford.png", width="200px"),
                # html.Img(ingest="/assets/hawaii.png", width="150px"),
                html.Img(src="/assets/LOGO_CNRS_BLEU.png", width="150px"),
                html.Img(src="/assets/hawaii.png", width="150px"),
            ],
            gap=100,
            justify="center",
            align="center",
            direction="row",
        ),
        p="xl",
        style={
            "backgroundColor": "var(--tarxiv-footer-bg)",
            "color": "var(--tarxiv-color-primary)",
            "textAlign": "center",
        },
        mt="md",
    )


def expressive_card(
    children, title=None, title_order: Literal[1, 2, 3, 4, 5, 6] = 2, **kwargs
):
    """Create a styled card with expressive design.

    Args:
        children: List of child components
        title: Optional title for the card
        title_order: Heading order (1-6)
        **kwargs: Additional keyword arguments for dmc.Paper

    Returns
    -------
        dmc.Paper component styled as a card
    """
    if not isinstance(children, list):
        children = [children]

    return dmc.Paper(
        children=[
            dmc.Title(
                title,
                order=title_order,
                # fw=700,
                # fz="lg",
                mb="md",
            )
            if title
            else None,
            dmc.Stack(
                children=children,
                gap="md",
            ),
        ],
        p="xl",
        radius=28,  # Specific M3 Expressive radius
        style={
            "backgroundColor": "var(--tarxiv-card-1)",
        },
        **kwargs,
    )


def create_nav_item(
    icon,
    label: str,
    is_active: bool,
    id: str = "",
):
    icon_container = (
        DashIconify(icon=icon, width=35, id=id)
        if isinstance(icon, str)
        else html.Div(
            icon,
            style={
                "width": "35px",
                "height": "35px",
                "display": "flex",
                "alignItems": "center",
                "justifyContent": "center",
            },
        )
    )

    return dmc.UnstyledButton(
        className="nav-item-hover",
        px=2,
        py="md",
        my="xs",
        style={
            "width": "100%",
            "borderRadius": "16px",
            "display": "flex",
            "flexDirection": "column",
            "alignItems": "center",
            "gap": "4px",
            "color": "var(--tarxiv-color-primary)" if is_active else "inherit",
            "transition": "background-color 200ms ease",
        },
        children=[
            icon_container,
            dmc.Text(
                label,
                size="xs",
                ta="center",
                className="nav-text-wrap",
            ),
        ],
    )


def create_nav_link(
    icon: str,
    label: str,
    href: str,
    is_active: bool,
    id: str = "",
):
    """Creates a vertically stacked navigation button.

    Args:
        icon: Icon name for DashIconify
        label: Text label for the nav item
        href: Link URL
        is_active: Whether this nav item is active

    Returns
    -------
        dcc.Link containing a styled dmc.UnstyledButton
    """
    return dcc.Link(
        href=href,
        style={"textDecoration": "none", "color": "inherit"},
        children=create_nav_item(icon, label, is_active, id=id),
    )


def create_message_banner(
    message,
    message_type="info",
    id="",
    hide=False,
    duration=None,
):
    """Create a styled message banner.

    Args:
        message: Message text
        message_type: "success", "error", "warning", or "info"
        id: Optional component ID
        hide: Whether to hide the banner (default: False)
        duration: Duration in milliseconds to auto-hide the banner (optional)

    Returns
    -------
        html.Div with styled message
    """
    color_map = {
        "success": {"bg": "#d4edda", "border": "#c3e6cb", "text": "#155724"},
        "error": {"bg": "#f8d7da", "border": "#f5c6cb", "text": "#721c24"},
        "warning": {"bg": "#fff3cd", "border": "#ffeaa7", "text": "#856404"},
        "info": {"bg": "#d1ecf1", "border": "#bee5eb", "text": "#0c5460"},
    }

    colors = color_map.get(message_type, color_map["info"])

    return dmc.Alert(
        # message,
        title=message.capitalize(),
        style={
            "padding": "12px 20px",
            "border": f"1px solid {colors['border']}",
            "borderRadius": "4px",
            "backgroundColor": colors["bg"],
            "color": colors["text"],
            "fontSize": "14px",
            "fontWeight": "500",
        },
        id=id,
        hide=hide,
        duration=duration,
    )


# Shared height (px) for the Aladin sky-plot pane and the scrollable metadata
# pane beside it, so the two columns line up.
ALADIN_HEIGHT_PX = 500

# Source key -> display label for the per-source metadata tabs.
SOURCE_LABELS = {
    "tns": "TNS",
    "ztf": "ZTF",
    "atlas": "ATLAS",
    "atlas_twb": "ATLAS TWB",
    "asas_sn": "ASAS-SN",
    "asas-sn": "ASAS-SN",
    "asas-sn_skypatrol": "ASAS-SN Skypatrol",
    "sherlock": "Sherlock",
    "fink": "Fink",
    "mangrove": "Mangrove",
    "lasair": "Lasair",
    "lsst": "LSST",
}

# Preferred ordering of source tabs; any source not listed is appended after.
SOURCE_ORDER = ["tns", "ztf", "atlas", "asas_sn", "sherlock"]

# Placeholder shown in metadata tables wherever a value is missing (None).
EM_DASH = "—"


def _display_or_dash(value):
    """Render a metadata value, substituting an em-dash for missing values."""
    return EM_DASH if value is None else str(value)

# Nice display labels for scalar metadata fields. Anything not listed falls
# back to a title-cased version of the raw key, so unmapped sources still render.
FIELD_LABELS = {
    "identifier": "Identifier",
    "ra_deg": "RA (deg)",
    "dec_deg": "Dec (deg)",
    "object_type": "Object Type",
    "discovery_date": "Discovery Date",
    "reporting_group": "Reporting Group",
    "discovery_data_source": "Discovery Data Source",
    "redshift": "Redshift",
    "host_name": "Host Name",
    "mag": "Magnitude",
    "mag_err": "Magnitude Error",
    "mag_filter": "Magnitude Filter",
    "association_type": "Association Type",
    "best_distance": "Best Distance",
    "best_distance_flag": "Best Distance Flag",
    "best_distance_source": "Best Distance Source",
    "catalogue_object_id": "Catalogue Object ID",
    "catalogue_object_type": "Catalogue Object Type",
    "catalogue_table_name": "Catalogue Table",
    "classificationReliability": "Classification Reliability",
    "separation_arcsec": "Separation (arcsec)",
    "north_separation_arcsec": "North Separation (arcsec)",
    "east_separation_arcsec": "East Separation (arcsec)",
    "physical_separation_kpc": "Physical Separation (kpc)",
    # List-valued photometry fields and their per-entry columns.
    "peak_mag": "Peak Magnitude",
    "latest_detection": "Latest Detection",
    "latest_nondetection": "Latest Non-detection",
    "filter": "Filter",
    "date": "Date",
    "value": "Magnitude",
    "mag_rate": "Mag Rate",
}


def _field_label(field_name: str) -> str:
    """Return a display label for a metadata field, with a sensible fallback."""
    return FIELD_LABELS.get(field_name, field_name.replace("_", " ").title())


def _source_label(source_key: str) -> str:
    """Return a display label for a data source, with a sensible fallback."""
    return SOURCE_LABELS.get(source_key, source_key.replace("_", " ").upper())


def _ordered_sources(data_sources: dict) -> list:
    """Order present sources by SOURCE_ORDER, appending any extras after."""
    ordered = [key for key in SOURCE_ORDER if key in data_sources]
    ordered += [key for key in data_sources if key not in ordered]
    return ordered


def _build_scalar_table(source_payload: dict):
    """Build a Field/Value table for the scalar entries of a source payload.

    List-valued fields are rendered as their own tables by
    ``_build_list_table`` and skipped here; dict values are rendered compactly
    rather than dropped so nothing is silently lost.
    """
    rows = []
    for field_name, value in source_payload.items():
        if isinstance(value, list):
            continue
        if isinstance(value, dict):
            value = json.dumps(value, separators=(",", ":"), default=str)
        rows.append((field_name, value))

    if not rows:
        return None

    return dmc.Box(
        dmc.Table(
            [
                dmc.TableThead(
                    dmc.TableTr([
                        dmc.TableTh("Field"),
                        dmc.TableTh("Value"),
                    ])
                ),
                dmc.TableTbody([
                    dmc.TableTr([
                        dmc.TableTd(_field_label(field_name)),
                        dmc.TableTd(_display_or_dash(value)),
                    ])
                    for field_name, value in rows
                ]),
            ],
            withTableBorder=True,
            withColumnBorders=True,
            striped=True,
            highlightOnHover=True,
            horizontalSpacing="xs",
            verticalSpacing="xs",
            style={"width": "fit-content"},
        ),
    )


def _build_list_table(field_name: str, entries: list):
    """Build a labelled table for a single list-valued metadata field.

    Each list item becomes a row. The nesting is assumed to be at most one deep:
    when items are dicts (e.g. ``peak_mag``/``latest_detection`` arrays) the
    columns are the union of their keys, preserving first-seen order; when items
    are scalars a single ``Value`` column is used. Missing values render as an
    em-dash. Returns ``None`` for an empty list.
    """
    if not entries:
        return None

    dict_entries = [entry for entry in entries if isinstance(entry, dict)]
    if dict_entries:
        columns: list[str] = []
        for entry in dict_entries:
            for key in entry:
                if key not in columns:
                    columns.append(key)
        header = dmc.TableThead(
            dmc.TableTr([dmc.TableTh(_field_label(col)) for col in columns])
        )
        body_rows = []
        for entry in entries:
            if isinstance(entry, dict):
                cells = [_display_or_dash(entry.get(col)) for col in columns]
            else:
                # A bare scalar in an otherwise-dict list: show it in the first
                # column and pad the rest so the row stays rectangular.
                cells = [_display_or_dash(entry)] + [EM_DASH] * (len(columns) - 1)
            body_rows.append(dmc.TableTr([dmc.TableTd(cell) for cell in cells]))
    else:
        header = dmc.TableThead(dmc.TableTr([dmc.TableTh("Value")]))
        body_rows = [
            dmc.TableTr([dmc.TableTd(_display_or_dash(entry))]) for entry in entries
        ]

    return dmc.Stack(
        [
            dmc.Text(_field_label(field_name), fw=600),
            dmc.Box(
                dmc.Table(
                    [header, dmc.TableTbody(body_rows)],
                    withTableBorder=True,
                    withColumnBorders=True,
                    striped=True,
                    highlightOnHover=True,
                    horizontalSpacing="xs",
                    verticalSpacing="xs",
                    style={"width": "fit-content"},
                )
            ),
        ],
        gap="xs",
    )


def _build_metadata_tabs(data_sources: dict):
    """Build the per-source metadata tabs component from the data_sources dict."""
    ordered = _ordered_sources(data_sources)
    if not ordered:
        return dmc.Text("No metadata available for this object.")

    tabs_list = []
    tabs_panels = []
    for source_key in ordered:
        payload = data_sources.get(source_key) or {}
        tabs_list.append(dmc.TabsTab(_source_label(source_key), value=source_key))

        panel_blocks = []
        scalar_table = _build_scalar_table(payload)
        if scalar_table is not None:
            panel_blocks.append(scalar_table)

        # Each list-valued field gets its own table below the scalar table.
        for field_name, value in payload.items():
            if isinstance(value, list) and value:
                list_table = _build_list_table(field_name, value)
                if list_table is not None:
                    panel_blocks.append(list_table)

        panel_children = (
            dmc.Stack(panel_blocks, py="md", gap="sm")
            if panel_blocks
            else dmc.Text("No source-specific metadata available.")
        )
        tabs_panels.append(dmc.TabsPanel(panel_children, value=source_key))

    default_tab = "tns" if "tns" in data_sources else ordered[0]
    return dmc.Tabs(
        [
            dmc.ScrollArea(
                dmc.TabsList(tabs_list, justify="flex-start"),
                offsetScrollbars=True,
                type="hover",
            )
        ]
        + tabs_panels,
        value=default_tab,
    )


def _build_citation_component(citation_str: str | None):
    """Build a copyable BibTeX citation card with a copy button.

    The card is rendered even when ``citation_str`` is empty/None so the failure
    mode is visible: an empty citations card with a fallback message means the
    /citations call returned nothing.
    """
    if citation_str:
        body = html.Div(
            [
                dcc.Clipboard(
                    target_id="citation-bibtex",
                    title="Copy citations",
                    style={
                        "position": "absolute",
                        "top": "8px",
                        "right": "8px",
                        "fontSize": "20px",
                        "cursor": "pointer",
                    },
                ),
                dmc.Code(
                    citation_str,
                    id="citation-bibtex",
                    block=True,
                    style={
                        "padding": "10px",
                        "maxHeight": "300px",
                        "overflow": "auto",
                        "borderRadius": "4px",
                    },
                ),
            ],
            style={"position": "relative"},
        )
    else:
        body = dmc.Text(
            "Could not load citations for this object — check the /citations API logs.",
            c="dimmed",
        )
    return body


def format_object_metadata(object_id, meta, citation_str=None, logger=None):
    """Format object metadata for display.

    Args:
        object_id: Object identifier
        meta: Metadata dictionary (source-keyed schema, see MetadataResponseModel)
        citation_str: Optional concatenated BibTeX citation string
        logger: Optional logger instance

    Returns
    -------
        A ``(results_top, citations_card, full_metadata)`` tuple. The caller
        composes these into the page: ``results_top`` (lightcurve + sky-plot /
        metadata) goes in the results container, ``citations_card`` sits in a
        grid beside the (always-present) ``object-tagging-container``, and
        ``full_metadata`` is the collapsible JSON dump pinned to the page bottom.
        Splitting the output this way lets the tagging container live in the base
        layout so its callbacks never target a missing component.
    """
    data_sources = meta.get("data_sources") or {}

    metadata_component = _build_metadata_tabs(data_sources)
    citations_component = _build_citation_component(citation_str)

    # Prominent, copyable RA/Dec (sexagesimal HMS + DMS) sits above the lightcurve.
    lightcurve_card = expressive_card(
        children=[
            _build_coordinates_header(meta),
            dcc.Loading(
                dcc.Graph(id={"type": "themeable-plot", "index": "lightcurve-plot"}),
            ),
        ],
        title=f"Lightcurve: {object_id}",
    )
    aladin_card = expressive_card(
        children=[
            # A hidden div to receive the "success" message from our JS
            html.Div(id="aladin-status-dummy", style={"display": "none"}),
            html.Div(
                id="aladin-lite-div",
                style={"width": "100%", "height": f"{ALADIN_HEIGHT_PX}px"},
            ),
        ],
        title="Sky Plot (Aladin Lite)",
    )

    # Constrain the metadata pane to the Aladin height and scroll any overflow,
    # so a source with many fields doesn't stretch the page.
    metadata_card = expressive_card(
        children=dmc.ScrollArea(
            metadata_component,
            h=ALADIN_HEIGHT_PX,
            type="auto",
            offsetScrollbars=True,
        ),
        title=f"Object Metadata: {object_id}",
    )

    results_top = dmc.Stack([
        # Lightcurve spans the full width; the metadata pairs with the sky plot.
        lightcurve_card,
        # Per-source metadata on the left, Aladin sky-plot on the right.
        dmc.Grid(
            [
                dmc.GridCol(metadata_card, span=6),
                dmc.GridCol(aladin_card, span=6),
            ],
            gutter="md",
        ),
    ])

    # Citations card (copyable BibTeX); the caller pairs it with the tagging panel.
    citations_card = expressive_card(
        children=citations_component,
        title=f"Citations: {object_id}",
    )

    # Full metadata JSON — collapsible, collapsed by default, at the very bottom.
    full_metadata = dmc.Accordion(
        chevronPosition="left",
        variant="separated",
        children=[
            dmc.AccordionItem(
                value="full-metadata",
                children=[
                    dmc.AccordionControl("Full Metadata (JSON)"),
                    dmc.AccordionPanel(
                        dmc.Code(
                            json.dumps(meta, indent=2),
                            style={
                                "padding": "10px",
                                "maxHeight": "400px",
                                "overflow": "auto",
                                "borderRadius": "4px",
                            },
                            block=True,
                        ),
                    ),
                ],
            )
        ],
    )

    return results_top, citations_card, full_metadata


def _build_coordinates_header(meta):
    """Build a prominent, copyable RA/Dec display above the lightcurve.

    The top-level ``ra_hms``/``dec_dms`` are sexagesimal strings (h:m:s /
    d:m:s). They are shown together, space-separated, with a clipboard button
    that copies the combined string. The older ``ra``/``dec`` keys are accepted
    as a fallback. Returns a dimmed placeholder when coordinates are missing.
    """
    ra = meta.get("ra_hms") or meta.get("ra")
    dec = meta.get("dec_dms") or meta.get("dec")
    if not ra or not dec:
        return dmc.Text("Coordinates unavailable", c="dimmed", size="sm")

    coordinate_str = f"{ra} {dec}"
    return dmc.Group(
        [
            dmc.Text("RA, Dec (J2000):", size="sm", c="dimmed"),
            dmc.Text(
                coordinate_str,
                id="object-coordinates",
                fw=700,
                size="xl",
                style={"fontFamily": "monospace"},
            ),
            dcc.Clipboard(
                target_id="object-coordinates",
                title="Copy coordinates",
                style={"cursor": "pointer", "fontSize": "1.1rem"},
            ),
        ],
        gap="sm",
        align="center",
    )


# Page size for the cone-search results list. The Aladin overlay still shows
# markers for every result; only the textual card list is paginated.
CONE_RESULTS_PAGE_SIZE = 20


def build_cone_result_card(idx: int, obj: dict):
    """Build one cone-search result card.

    The card's pattern-matching id carries the absolute result index so the
    Aladin clientside callback can match a hover event back to the correct
    marker even when the list is paginated.
    """
    distance_arcsec = obj.get("distance_deg", 0) * 3600  # Convert to arcsec
    summary_style = {
        **CARD_STYLE,
        "cursor": "pointer",
        "marginBottom": "10px",
        "padding": "15px",
    }
    obj_name = obj["obj_name"]
    return dmc.Card(
        [
            dmc.Group(
                [
                    dmc.Anchor(
                        f"{obj_name}",
                        href=f"/lightcurve/{obj_name}",
                        id={"type": "object-link", "index": idx},
                        underline="always",
                        style={
                            "fontWeight": "bold",
                            "fontSize": "16px",
                            "marginRight": "20px",
                            "cursor": "pointer",
                        },
                    ),
                    dcc.Store(
                        id={"type": "object-id-store", "index": idx},
                        data=obj_name,
                    ),
                    dmc.Text(f"RA: {obj['ra']:.6f}°", style={"marginRight": "15px"}),
                    dmc.Text(f"Dec: {obj['dec']:.6f}°", style={"marginRight": "15px"}),
                    dmc.Text(
                        f"Distance: {distance_arcsec:.2f}″",
                        style={"fontStyle": "italic"},
                    ),
                ],
                style={"padding": "15px"},
            ),
        ],
        style=summary_style,
        id={"type": "object-card", "index": idx},
    )


def build_cone_result_cards_page(results: list, page: int) -> list:
    """Slice results to a 1-indexed page and build card components."""
    start = max(page - 1, 0) * CONE_RESULTS_PAGE_SIZE
    end = start + CONE_RESULTS_PAGE_SIZE
    return [
        build_cone_result_card(start + offset, obj)
        for offset, obj in enumerate(results[start:end])
    ]


def format_cone_search_results(
    results, search_ra, search_dec, txv_db=None, logger=None
):
    """Format cone search results with paginated object cards.

    Args:
        results: List of objects with ra, dec, obj_name
        search_ra: Search position RA
        search_dec: Search position Dec
        txv_db: Database instance for fetching object details (optional)
        logger: Logger instance (optional)

    Returns
    -------
        dmc.Stack containing the Aladin widget, paginated object cards and
        their pagination control.
    """
    total = len(results)
    page_count = max(1, math.ceil(total / CONE_RESULTS_PAGE_SIZE))
    first_page_cards = build_cone_result_cards_page(results, 1)

    pagination = (
        dmc.Pagination(
            id="cone-results-pagination",
            total=page_count,
            value=1,
            siblings=1,
            withEdges=True,
            mt="md",
        )
        if page_count > 1
        else html.Div(id="cone-results-pagination", style={"display": "none"})
    )

    plural = "s" if total != 1 else ""
    return dmc.Stack([
        expressive_card(
            title=f"Found {total} object{plural}",
            children=[
                dmc.Text(
                    f"Search coordinates: RA={search_ra:.6f}°, Dec={search_dec:.6f}°",
                ),
                # Hidden div receives the Aladin init status from clientside JS.
                html.Div(id="cone-aladin-status", style={"display": "none"}),
                html.Div(
                    id="cone-aladin-div",
                    style={"width": "100%", "height": "500px"},
                ),
            ],
        ),
        expressive_card(
            title="Objects Found",
            title_order=3,
            children=[
                dmc.Stack(first_page_cards, id="cone-results-list"),
                pagination,
            ],
        ),
    ])
