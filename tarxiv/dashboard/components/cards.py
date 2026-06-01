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
                # html.Img(src="/assets/hawaii.png", width="150px"),
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

# Per-source fields that hold photometry arrays (lists of detection dicts).
PHOTOMETRY_FIELDS = ("peak_mag", "latest_detection", "latest_nondetection")

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

    Photometry arrays are handled separately; nested values are rendered
    compactly rather than dropped so nothing is silently lost.
    """
    rows = []
    for field_name, value in source_payload.items():
        if field_name in PHOTOMETRY_FIELDS:
            continue
        if isinstance(value, (list, dict)):
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
                        dmc.TableTd(str(value)),
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


def _build_detection_info_table(peak_entries: list, latest_entries: list) -> list:
    """Build a condensed detection summary table grouped by filter.

    Columns are:
    Filter | latest_date | latest_mag | latest_mag_rate | peak_date | peak_mag
    """
    if not peak_entries and not latest_entries:
        return []

    filters = set()
    for entry in peak_entries:
        filters.add(str(entry.get("filter", "unknown")))
    for entry in latest_entries:
        filters.add(str(entry.get("filter", "unknown")))

    def latest_for_filter(filter_name: str):
        candidates = [
            entry
            for entry in latest_entries
            if str(entry.get("filter", "unknown")) == filter_name
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda item: str(item.get("date", "")))

    def peak_for_filter(filter_name: str):
        candidates = [
            entry
            for entry in peak_entries
            if str(entry.get("filter", "unknown")) == filter_name
        ]
        if not candidates:
            return None

        numeric_candidates = [
            entry
            for entry in candidates
            if isinstance(entry.get("value"), (int, float))
        ]
        if numeric_candidates:
            # Magnitude peak is the brightest point (minimum magnitude value).
            return min(numeric_candidates, key=lambda item: item.get("value"))

        return candidates[0]

    def display_or_dash(value):
        return "-" if value is None else str(value)

    rows = []
    for filter_name in sorted(filters):
        latest_entry = latest_for_filter(filter_name)
        peak_entry = peak_for_filter(filter_name)
        rows.append(
            dmc.TableTr([
                dmc.TableTd(f"{filter_name} Band"),
                dmc.TableTd(
                    display_or_dash(latest_entry.get("date") if latest_entry else None)
                ),
                dmc.TableTd(
                    display_or_dash(latest_entry.get("value") if latest_entry else None)
                ),
                dmc.TableTd(
                    display_or_dash(
                        latest_entry.get("mag_rate") if latest_entry else None
                    )
                ),
                dmc.TableTd(
                    display_or_dash(peak_entry.get("date") if peak_entry else None)
                ),
                dmc.TableTd(
                    display_or_dash(peak_entry.get("value") if peak_entry else None)
                ),
            ])
        )

    return [
        dmc.Text("Detection Info by Filter", fw=600),
        dmc.Box(
            dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr([
                            dmc.TableTh("Filter"),
                            dmc.TableTh("Latest Date"),
                            dmc.TableTh("Latest Mag"),
                            dmc.TableTh("Latest Mag Rate"),
                            dmc.TableTh("Peak Date"),
                            dmc.TableTh("Peak Mag"),
                        ])
                    ),
                    dmc.TableTbody(rows),
                ],
                withTableBorder=True,
                withColumnBorders=True,
                striped=True,
                highlightOnHover=True,
                horizontalSpacing="xs",
                verticalSpacing="xs",
                style={"width": "fit-content"},
            )
        ),
    ]


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

        peak_entries = payload.get("peak_mag") or []
        latest_entries = payload.get("latest_detection") or []
        panel_blocks.extend(_build_detection_info_table(peak_entries, latest_entries))

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
        dmc.Stack containing formatted cards
    """
    data_sources = meta.get("data_sources") or {}

    metadata_component = _build_metadata_tabs(data_sources)
    citations_component = _build_citation_component(citation_str)

    # Lightcurve and Aladin sky-plot sit side-by-side in a 3:1 grid.
    lightcurve_card = expressive_card(
        children=dcc.Loading(
            dcc.Graph(id={"type": "themeable-plot", "index": "lightcurve-plot"}),
        ),
        title=f"Lightcurve: {object_id}",
    )
    aladin_card = expressive_card(
        children=[
            # A hidden div to receive the "success" message from our JS
            html.Div(id="aladin-status-dummy", style={"display": "none"}),
            html.Div(
                id="aladin-lite-div",
                style={"width": "100%", "height": "500px"},
            ),
        ],
        title="Sky Plot (Aladin Lite)",
    )

    sections = [
        dmc.Grid(
            [
                dmc.GridCol(lightcurve_card, span=6),
                dmc.GridCol(aladin_card, span=6),
            ],
            gutter="md",
        ),
    ]

    # Per-source metadata tabs.
    sections.append(
        expressive_card(
            children=metadata_component,
            title=f"Object Metadata: {object_id}",
        )
    )

    # Citations card (copyable BibTeX).
    sections.append(
        expressive_card(
            children=citations_component,
            title=f"Citations: {object_id}",
        )
    )

    # Full metadata JSON — collapsible, collapsed by default.
    sections.append(
        dmc.Accordion(
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
    )

    return dmc.Stack(sections)


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
