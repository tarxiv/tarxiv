"""Card components for displaying object data."""

import dash_mantine_components as dmc
from dash import dcc
import json
from ..styles import CARD_STYLE, COLORS
from . import theme_manager as tm


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
                    [
                        dmc.Text(f"{label}: "),
                        str(value),
                    ],
                    style={"marginBottom": "6px"},
                )
            )

    return dmc.Stack(
        [
            # Lightcurve card
            dmc.Card(
                [
                    dmc.Title(
                        f"Lightcurve: {object_id}", order=3, style={"marginTop": "0"}
                    ),
                    dcc.Loading(
                        dcc.Graph(
                            id={"type": tm.PLOT_TYPE, "index": "lightcurve-plot"}
                        ),
                    ),
                ],
                style=CARD_STYLE,
            ),
            # Metadata card
            dmc.Card(
                [
                    dmc.Title(
                        f"Object Metadata: {object_id}",
                        order=3,
                        style={"marginTop": "0"},
                    ),
                    dmc.Stack(summary_items),
                ],
                style=CARD_STYLE,
            ),
            # Full JSON card
            dmc.Card(
                [
                    dmc.Title(
                        "Full Metadata (JSON)", order=4, style={"marginTop": "0"}
                    ),
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
                ],
                style=CARD_STYLE,
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
