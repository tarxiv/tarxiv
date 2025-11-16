"""Card components for displaying object data."""
from dash import html, dash_table
import json
from ..styles import CARD_STYLE, COLORS
from .plots import create_lightcurve_plot, create_sky_plot


def format_object_metadata(object_id, meta, lc_data, logger=None):
    """Format object metadata for display.

    Args:
        object_id: Object identifier
        meta: Metadata dictionary
        lc_data: Lightcurve data
        logger: Optional logger instance

    Returns:
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
            summary_items.append(html.P([html.B(f"{label}: "), str(value)]))

    # Create lightcurve plot
    lc_plot = create_lightcurve_plot(lc_data, object_id, logger) if lc_data else None

    if logger:
        logger.debug({"debug": f"{lc_plot}"})

    return html.Div(
        [
            # Lightcurve card
            html.Div(
                [
                    html.H3(f"Lightcurve: {object_id}", style={"marginTop": "0"}),
                    lc_plot if lc_plot is not None else html.P(
                        "No lightcurve data available",
                        style={"color": "gray", "fontStyle": "italic"}
                    ),
                ],
                style=CARD_STYLE
            ) if lc_plot or lc_data else html.Div(),

            # Metadata card
            html.Div(
                [
                    html.H3(f"Object Metadata: {object_id}", style={"marginTop": "0"}),
                    html.Div(summary_items, style={"padding": "10px"}),
                ],
                style=CARD_STYLE
            ),

            # Full JSON card
            html.Div(
                [
                    html.H4("Full Metadata (JSON)", style={"marginTop": "0"}),
                    html.Pre(
                        json.dumps(meta, indent=2),
                        style={
                            "backgroundColor": "#f5f5f5",
                            "padding": "10px",
                            "maxHeight": "400px",
                            "overflow": "auto",
                            "borderRadius": "4px"
                        },
                    ),
                ],
                style=CARD_STYLE
            ),
        ]
    )


def format_cone_search_results(results, search_ra, search_dec, txv_db=None, logger=None):
    """Format cone search results with expandable object cards.

    Args:
        results: List of objects with ra, dec, obj_name
        search_ra: Search position RA
        search_dec: Search position Dec
        txv_db: Database instance for fetching object details (optional)
        logger: Logger instance (optional)

    Returns:
        html.Div containing formatted results
    """
    # Create sky plot
    sky_plot = create_sky_plot(results, search_ra, search_dec)

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

        from dash import dcc
        object_cards.append(
            html.Div(
                [
                    html.Div(
                        [
                            html.A(
                                f"{obj_name}",
                                id={"type": "object-link", "index": idx},
                                n_clicks=0,
                                style={
                                    "fontWeight": "bold",
                                    "fontSize": "16px",
                                    "marginRight": "20px",
                                    "color": COLORS["primary"],
                                    "textDecoration": "underline",
                                    "cursor": "pointer"
                                }
                            ),
                            dcc.Store(id={"type": "object-id-store", "index": idx}, data=obj_name),
                            html.Span(
                                f"RA: {obj['ra']:.6f}°",
                                style={"marginRight": "15px", "color": COLORS["muted"]}
                            ),
                            html.Span(
                                f"Dec: {obj['dec']:.6f}°",
                                style={"marginRight": "15px", "color": COLORS["muted"]}
                            ),
                            html.Span(
                                f"Distance: {distance_arcsec:.2f}″",
                                style={"color": COLORS["primary"], "fontStyle": "italic"}
                            ),
                        ],
                        style={"padding": "15px"}
                    ),
                ],
                style=summary_style,
                id={"type": "object-card", "index": idx}
            )
        )

    return html.Div(
        [
            # Summary card
            html.Div(
                [
                    html.H3(f"Found {len(results)} object(s)", style={"marginTop": "0", "color": COLORS["secondary"]}),
                    html.P(
                        f"Search coordinates: RA={search_ra:.6f}°, Dec={search_dec:.6f}°",
                        style={"color": COLORS["muted"], "fontSize": "14px"}
                    ),
                ],
                style=CARD_STYLE
            ),

            # Sky plot card
            html.Div(
                [
                    html.H4("Sky Position", style={"marginTop": "0"}),
                    sky_plot,
                ],
                style=CARD_STYLE
            ),

            # Expandable object cards
            html.Div(
                [
                    html.H4("Objects Found", style={"marginTop": "0"}),
                    html.Div(object_cards),
                ],
                style=CARD_STYLE
            ),
        ]
    )
