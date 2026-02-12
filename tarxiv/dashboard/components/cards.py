"""Card components for displaying object data."""

import dash_mantine_components as dmc
from dash import dcc, html
from dash_iconify import DashIconify

import visdcc
import json
from ..styles import CARD_STYLE
from . import theme_manager as tm


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


def expressive_card(children, title=None, title_order: int = 2, **kwargs):
    """Create a styled card with expressive design.

    Args:
        children: List of child components
        title: Optional title for the card
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
    icon: str,
    label: str,
    is_active: bool,
    id: str = "",
):
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
            # DashIconify(icon=icon, width=28, id=id),
            DashIconify(icon=icon, width=35, id=id),
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


def create_message_banner(message, message_type="info"):
    """Create a styled message banner.

    Args:
        message: Message text
        message_type: "success", "error", "warning", or "info"

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
            "marginBottom": "15px",
            "border": f"1px solid {colors['border']}",
            "borderRadius": "4px",
            "backgroundColor": colors["bg"],
            "color": colors["text"],
            "fontSize": "14px",
            "fontWeight": "500",
        },
    )


def format_object_metadata(object_id, meta, logger=None):
    """Format object metadata for display.

    Args:
        object_id: Object identifier
        meta: Metdata dictionary
        logger: Optional logger instance

    Returns
    -------
        html.Div containing formatted cards
    """
    # Create a summary card
    summary_items = []

    # Extract key fields
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

    for field, label in fields_to_display:
        if field in meta and meta[field]:
            value = meta[field]
            # Format list values
            if isinstance(value, list) and len(value) > 0:
                if isinstance(value[0], dict) and "value" in value[0]:
                    value = value[0]["value"]
                else:
                    value = str(value[0])
            summary_items.append(
                dmc.Text(
                    dmc.Text(f"{label}: {value}"),
                    style={"marginBottom": "6px"},
                )
            )

    return dmc.Stack(
        [
            # Lightcurve card
            expressive_card(
                children=dcc.Loading(
                    dcc.Graph(id={"type": tm.PLOT_TYPE, "index": "lightcurve-plot"}),
                ),
                title=f"Lightcurve: {object_id}",
            ),
            # Metadata card
            expressive_card(
                children=dmc.Stack(summary_items),
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
                    dcc.Loading(
                        visdcc.Run_js(
                            id="aladin-lite-runjs",
                        )
                    ),
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
                                href="#",
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

    return dmc.Stack(
        [
            # Summary card
            dmc.Card(
                [
                    dmc.Title(
                        f"Found {len(results)} object(s)",
                        order=3,
                        style={"marginTop": "0"},
                    ),
                    dmc.Text(
                        f"Search coordinates: RA={search_ra:.6f}°, Dec={search_dec:.6f}°",
                        style={"fontSize": "14px"},
                    ),
                ],
                style=CARD_STYLE,
            ),
            # Sky plot card
            dmc.Card(
                [
                    dmc.Title("Sky Position", order=4, style={"marginTop": "0"}),
                    dcc.Loading(
                        dcc.Graph(
                            id={"type": tm.PLOT_TYPE, "index": "sky-plot"},
                        ),
                    ),
                ],
                style=CARD_STYLE,
            ),
            # Expandable object cards
            dmc.Card(
                [
                    dmc.Title("Objects Found", order=4, style={"marginTop": "0"}),
                    dmc.Stack(object_cards),
                ],
                style=CARD_STYLE,
            ),
        ]
    )
