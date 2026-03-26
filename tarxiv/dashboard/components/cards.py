"""Card components for displaying object data."""

import json
from typing import Literal, List, Dict, Set

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


def format_object_metadata(object_id, meta, logger=None):
    """Format object metadata for display.

    Args:
        object_id: Object identifier
        meta: Metadata dictionary
        logger: Optional logger instance

    Returns
    -------
        html.Div containing formatted cards
    """
    field_labels = {
        "identifiers": "Identifiers",
        "ra_deg": "RA (deg)",
        "dec_deg": "Dec (deg)",
        "object_type": "Object Type",
        "discovery_date": "Discovery Date",
        "reporting_group": "Reporting Group",
        "discovery_data_source": "Discovery Data Source",
        "redshift": "Redshift",
        "host_name": "Host Name",
        "peak_mag": "Peak Magnitude",
        "latest_detection": "Latest Detection",
    }

    # Associated-source groupings mirrored from aux/config.yml.
    associated_sources: Dict[str, Set[str]] = {
        "tns": {"tns"},
        "ztf": {"ztf", "fink", "mangrove"},
        "atlas": {"atlas", "atlas_twb", "sherlock"},
        "asas-sn": {"asas-sn", "asas-sn_skypatrol"},
    }

    tab_order = [
        # ("all", "ALL SOURCES"),
        ("tns", "TNS"),
        ("ztf", "ZTF"),
        ("atlas", "ATLAS"),
        ("asas-sn", "ASAS-SN"),
    ]
    tab_data = {
        tab_key: {
            "kv_rows": [],
            "photometry": {
                "peak_mag": [],
                "latest_detection": [],
            },
        }
        for tab_key, _ in tab_order
    }

    def value_from_entry(field_name: str, entry_value) -> str:
        """Extract a display-friendly value from a metadata entry."""
        if isinstance(entry_value, dict):
            if field_name == "identifiers" and "name" in entry_value:
                return entry_value["name"]
            if "value" in entry_value:
                return entry_value["value"]
            if "name" in entry_value:
                return entry_value["name"]
            return json.dumps(entry_value, separators=(",", ":"), default=str)
        return entry_value

    def add_text(
        tab_key: str,
        label: str,
        field_name: str,
        entry_value,
    ) -> None:
        source = entry_value.get("source") if isinstance(entry_value, dict) else None
        value = value_from_entry(field_name, entry_value)
        tab_data[tab_key]["kv_rows"].append(
            {
                "field": label,
                "source": source or "-",
                "value": value,
            }
        )

    def add_field_for_sources(
        tab_key: str,
        field_name: str,
        allowed_sources: Set[str],
    ) -> None:
        """Add entries for a specific field if their source is in the allowed set.

        Args:
            tab_key: The key of the current tab (e.g., "tns", "ztf")
            field_name: The metadata field to add (e.g., "ra_deg")
            allowed_sources: Set of sources to include for this field
        """
        if field_name not in meta:
            return
        entries = (
            meta[field_name]
            if isinstance(meta[field_name], list)
            else [meta[field_name]]
        )
        label = field_labels[field_name]
        for entry in entries:
            source = entry.get("source") if isinstance(entry, dict) else None
            if source in allowed_sources:
                add_text(tab_key, label, field_name, entry)

    def add_grouped_by_filter(
        tab_key: str,
        field_name: str,
        allowed_sources: Set[str],
    ) -> None:
        """Add photometry entries for a specific field grouped by filter.

        Args:
            tab_key: The key of the current tab (e.g., "ztf", "atlas")
            field_name: The photometry field to add (e.g., "peak_mag")
            allowed_sources: Set of sources to include for this field
        """
        if field_name not in meta:
            return
        entries = (
            meta[field_name]
            if isinstance(meta[field_name], list)
            else [meta[field_name]]
        )
        matched = [
            entry
            for entry in entries
            if isinstance(entry, dict) and entry.get("source") in allowed_sources
        ]
        if not matched:
            return
        tab_data[tab_key]["photometry"][field_name].extend(matched)

    def build_kv_table(rows: List[dict]) -> dmc.Box:
        """Build a compact table for field/source/value metadata rows."""
        return dmc.Box(
            dmc.Table(
                [
                    dmc.TableThead(
                        dmc.TableTr(
                            [
                                dmc.TableTh("Field"),
                                dmc.TableTh("Source"),
                                dmc.TableTh("Value"),
                            ]
                        )
                    ),
                    dmc.TableTbody(
                        [
                            dmc.TableTr(
                                [
                                    dmc.TableTd(str(row["field"])),
                                    dmc.TableTd(str(row["source"])),
                                    dmc.TableTd(str(row["value"])),
                                ]
                            )
                            for row in rows
                        ]
                    ),
                ],
                withTableBorder=True,
                withColumnBorders=True,
                striped=True,
                highlightOnHover=True,
                horizontalSpacing="xs",
                verticalSpacing="xs",
                style={
                    "width": "fit-content",
                    # "maxWidth": "100%",
                    # "fontSize": "0.95rem",
                },
            ),
            # style={"overflowX": "auto", "maxWidth": "100%"},
        )

    def build_detection_info_table(tab_key: str) -> List:
        """Build a condensed detection summary table grouped by filter.

        Columns are:
        Filter | latest_date | latest_mag | peak_mag | mag_rate
        """
        peak_entries = tab_data[tab_key]["photometry"]["peak_mag"]
        latest_entries = tab_data[tab_key]["photometry"]["latest_detection"]

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

        rows = []

        def display_or_dash(value):
            return "-" if value is None else str(value)

        for filter_name in sorted(filters):
            latest_entry = latest_for_filter(filter_name)
            peak_entry = peak_for_filter(filter_name)
            rows.append(
                dmc.TableTr(
                    [
                        dmc.TableTd(f"{filter_name} Band"),
                        dmc.TableTd(
                            display_or_dash(
                                latest_entry.get("date") if latest_entry else None
                            )
                        ),
                        dmc.TableTd(
                            display_or_dash(
                                latest_entry.get("value") if latest_entry else None
                            )
                        ),
                        dmc.TableTd(
                            display_or_dash(
                                latest_entry.get("mag_rate") if latest_entry else None
                            )
                        ),
                        dmc.TableTd(
                            display_or_dash(
                                peak_entry.get("date") if peak_entry else None
                            )
                        ),
                        dmc.TableTd(
                            display_or_dash(
                                peak_entry.get("value") if peak_entry else None
                            )
                        ),
                        dmc.TableTd(
                            display_or_dash(
                                peak_entry.get("mag_rate") if peak_entry else None
                            )
                        ),
                    ]
                )
            )

        return [
            dmc.Text("Detection Info by Filter", fw=600),
            dmc.Box(
                dmc.Table(
                    [
                        dmc.TableThead(
                            dmc.TableTr(
                                [
                                    dmc.TableTh("Filter"),
                                    dmc.TableTh("Latest Date"),
                                    dmc.TableTh("Latest Mag"),
                                    dmc.TableTh("Latest Mag Rate"),
                                    dmc.TableTh("Peak Date"),
                                    dmc.TableTh("Peak Mag"),
                                    dmc.TableTh("Peak Mag Rate"),
                                ]
                            )
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

    # # ALL SOURCES tab: RA, Dec, identifiers.
    # for field in ["ra_deg", "dec_deg", "identifiers"]:
    #     if field not in meta:
    #         continue
    #     entries = meta[field] if isinstance(meta[field], list) else [meta[field]]
    #     for entry in entries:
    #         add_text("all", field_labels[field], field, entry)

    # Every source tab includes its own RA, Dec, identifiers.
    add_field_for_sources("tns", "ra_deg", associated_sources["tns"])
    add_field_for_sources("tns", "dec_deg", associated_sources["tns"])
    add_field_for_sources("tns", "identifiers", associated_sources["tns"])

    add_field_for_sources("ztf", "ra_deg", associated_sources["ztf"])
    add_field_for_sources("ztf", "dec_deg", associated_sources["ztf"])
    add_field_for_sources("ztf", "identifiers", associated_sources["ztf"])

    add_field_for_sources("atlas", "ra_deg", associated_sources["atlas"])
    add_field_for_sources("atlas", "dec_deg", associated_sources["atlas"])
    add_field_for_sources("atlas", "identifiers", associated_sources["atlas"])

    add_field_for_sources("asas-sn", "ra_deg", associated_sources["asas-sn"])
    add_field_for_sources("asas-sn", "dec_deg", associated_sources["asas-sn"])
    add_field_for_sources("asas-sn", "identifiers", associated_sources["asas-sn"])

    # TNS tab: object_type, discovery_date, reporting_group, discovery_data_source, redshift.
    for field in [
        "object_type",
        "discovery_date",
        "reporting_group",
        "discovery_data_source",
        "redshift",
    ]:
        add_field_for_sources("tns", field, associated_sources["tns"])

    # ZTF tab: redshift, host_name.
    for field in ["redshift", "host_name"]:
        add_field_for_sources("ztf", field, associated_sources["ztf"])

    # ATLAS tab: redshift.
    add_field_for_sources("atlas", "redshift", associated_sources["atlas"])

    # Survey tabs include grouped peak_mag and latest_detection by filter.
    add_grouped_by_filter("ztf", "peak_mag", associated_sources["ztf"])
    add_grouped_by_filter("ztf", "latest_detection", associated_sources["ztf"])
    add_grouped_by_filter("atlas", "peak_mag", associated_sources["atlas"])
    add_grouped_by_filter("atlas", "latest_detection", associated_sources["atlas"])
    add_grouped_by_filter("asas-sn", "peak_mag", associated_sources["asas-sn"])
    add_grouped_by_filter("asas-sn", "latest_detection", associated_sources["asas-sn"])

    tabs_list = []  # For building the dmc.TabsList with dmc.TabsTab components
    tabs_panels = []  # For building the dmc.TabsPanel components corresponding to each tab
    # iterate over the tabs in the specified order to build the tab list and panels
    for tab_key, tab_label in tab_order:
        tabs_list.append(dmc.TabsTab(tab_label, value=tab_key))
        kv_rows = tab_data[tab_key]["kv_rows"]
        phot_sections = []
        if tab_key in {"ztf", "atlas", "asas-sn"}:
            phot_sections.extend(build_detection_info_table(tab_key))

        # Only add the key-value table if there are entries to show
        panel_blocks = []
        if kv_rows:
            panel_blocks.append(build_kv_table(kv_rows))
        panel_blocks.extend(phot_sections)

        panel_children = (
            dmc.Stack(panel_blocks, py="md", gap="sm")
            if panel_blocks
            else dmc.Text("No source-specific metadata available.")
        )
        tabs_panels.append(
            dmc.TabsPanel(
                panel_children,
                value=tab_key,
            )
        )

    metadata_component = dmc.Tabs(
        [
            dmc.ScrollArea(
                dmc.TabsList(tabs_list, justify="flex-start"),
                offsetScrollbars=True,
                type="hover",
            )
        ]
        + tabs_panels,
        # value="all", # default to the "ALL SCOURCES" tab
        value="tns",  # default to the "TNS" tab since "ALL SOURCES" is currently disabled
    )

    return dmc.Stack(
        [
            # Lightcurve card
            expressive_card(
                children=dcc.Loading(
                    dcc.Graph(
                        id={"type": "themeable-plot", "index": "lightcurve-plot"}
                    ),
                ),
                title=f"Lightcurve: {object_id}",
            ),
            # Metadata card
            expressive_card(
                children=metadata_component,
                title=f"Object Metadata: {object_id}",
            ),
            # Full JSON card
            expressive_card(
                children=dmc.Code(
                    json.dumps(meta, indent=2),
                    style={
                        "padding": "10px",
                        "maxHeight": "400px",
                        "overflow": "auto",
                        "borderRadius": "4px",
                    },
                    block=True,
                ),
                title="Full Metadata (JSON)",
            ),
            # Sky plot Aladin card
            expressive_card(
                children=[
                    # A hidden div to receive the "success" message from our JS
                    html.Div(id="aladin-status-dummy", style={"display": "none"}),
                    html.Div(
                        id="aladin-lite-div",
                        style={"width": "100%", "height": "500px"},
                    ),
                ],
                title="Sky Plot (Aladin Lite)",
            ),
        ]
    )


def format_cone_search_results(
    results, search_ra, search_dec, txv_db=None, logger=None
):
    """Format cone search results with expandable object cards.

    Args:
        results: List of objects with ra, dec, obj_name
        search_ra: Search position RA
        search_dec: Search position Dec
        txv_db: Database instance for fetching object details (optional)
        logger: Logger instance (optional)

    Returns
    -------
        html.Div containing formatted results
    """
    # Create expandable object cards
    object_cards = []
    for idx, obj in enumerate(results):
        obj_name = obj["obj_name"]
        distance_arcsec = obj.get("distance_deg", 0) * 3600  # Convert to arcsec

        # Create a summary row for each object
        summary_style = {
            **CARD_STYLE,
            "cursor": "pointer",
            "marginBottom": "10px",
            "padding": "15px",
        }

        object_cards.append(
            dmc.Card(
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
                            dmc.Text(
                                f"RA: {obj['ra']:.6f}°", style={"marginRight": "15px"}
                            ),
                            dmc.Text(
                                f"Dec: {obj['dec']:.6f}°", style={"marginRight": "15px"}
                            ),
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
        )

    plural = "s" if len(results) != 1 else ""
    return dmc.Stack(
        [
            expressive_card(
                title=f"Found {len(results)} object{plural}",
                children=[
                    dmc.Text(
                        f"Search coordinates: RA={search_ra:.6f}°, Dec={search_dec:.6f}°",
                    ),
                    dcc.Loading(
                        dcc.Graph(
                            id={"type": "themeable-plot", "index": "sky-plot"},
                        ),
                    ),
                ],
            ),
            expressive_card(
                title="Objects Found",
                title_order=3,
                children=dmc.Stack(
                    object_cards,
                ),
            ),
        ]
    )
