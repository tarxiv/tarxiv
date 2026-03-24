"""Card components for displaying object data."""

import json
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
    fields_to_display = [
        ("identifiers", "Identifiers"),
        ("ra_deg", "RA (deg)"),
        ("dec_deg", "Dec (deg)"),
        ("ra_hms", "RA (HMS)"),
        ("dec_dms", "Dec (DMS)"),
        ("object_type", "Object Type"),
        ("discovery_date", "Discovery Date"),
        ("reporting_group", "Reporting Group"),
        ("redshift", "Redshift"),
        ("host_name", "Host Name"),
    ]
    field_labels = dict(fields_to_display)

    sources_data = meta.get("sources", [])
    source_names = []
    for s in sources_data:
        name = s.get("name") if isinstance(s, dict) else s
        if isinstance(name, str) and name and name not in source_names:
            source_names.append(name)

    if "tns" in source_names:
        source_names.remove("tns")
        source_names.insert(0, "tns")

    source_variant_map = {
        "tns": ["tns"],
        "atlas_survey": ["atlas_survey", "atlas"],
        "atlas_twb": ["atlas_twb", "atlas"],
        "ztf_survey": ["ztf_survey", "ztf"],
        "asas-sn_survey": ["asas-sn_survey", "asas-sn"],
        "asas-sn_skypatrol": ["asas-sn_skypatrol", "asas-sn"],
        "sherlock": ["sherlock"],
        "fink": ["fink"],
        "mangrove": ["mangrove"],
    }

    variant_to_tabs = {}
    for tab_name, variants in source_variant_map.items():
        if tab_name not in source_names:
            continue
        for variant in variants:
            variant_to_tabs.setdefault(variant, []).append(tab_name)

    tab_contents = {name: [] for name in source_names}
    default_tab = (
        "tns" if "tns" in tab_contents else (source_names[0] if source_names else None)
    )

    for field, values in meta.items():
        if field in {"schema", "sources"}:
            continue

        label = field_labels.get(field, field.replace("_", " ").title())
        entries = values if isinstance(values, list) else [values]

        for entry in entries:
            if isinstance(entry, dict):
                source_id = entry.get("source")
                matched_tabs = variant_to_tabs.get(source_id, []) if source_id else []
                if not matched_tabs and default_tab:
                    matched_tabs = [default_tab]

                if field == "identifiers" and "name" in entry:
                    value = entry["name"]
                elif "value" in entry:
                    value = entry["value"]
                else:
                    value = json.dumps(entry, separators=(",", ":"), default=str)

                for tab in matched_tabs:
                    tab_contents[tab].append(dmc.Text(f"{label}: {value}"))
            elif default_tab:
                tab_contents[default_tab].append(dmc.Text(f"{label}: {entry}"))

    # Create Tabs component
    tabs_list = []
    tabs_panels = []

    for name in source_names:
        display_label = name.upper()
        tabs_list.append(dmc.TabsTab(display_label, value=name))
        panel_children = (
            dmc.Stack(tab_contents[name], py="md")
            if tab_contents[name]
            else dmc.Text("No source-specific metadata available.")
        )
        tabs_panels.append(
            dmc.TabsPanel(
                panel_children,
                value=name,
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
        value=default_tab,
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
