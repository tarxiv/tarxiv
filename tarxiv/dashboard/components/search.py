"""Search UI components."""
from dash import dcc, html
from ..styles import SECTION_STYLE, BUTTON_STYLE, INPUT_STYLE, COLORS


def create_unified_search():
    """Create a unified search interface with tabs.

    Returns:
        html.Div containing tabbed search UI
    """
    return html.Div(
        [
            html.H2("Search TarXiv Database", style={"marginTop": "0", "color": COLORS["secondary"]}),
            dcc.Tabs(
                id="search-tabs",
                value="id-search",
                children=[
                    dcc.Tab(label="Search by Object ID", value="id-search", children=[
                        html.Div(
                            [
                                html.P(
                                    "Enter a TNS object name to view its metadata and lightcurve",
                                    style={"color": COLORS["muted"], "fontSize": "14px", "marginTop": "15px", "marginBottom": "15px"}
                                ),
                                html.Div(
                                    [
                                        dcc.Input(
                                            id="object-id-input",
                                            type="text",
                                            placeholder="Enter object ID (e.g., 2024abc)",
                                            style={**INPUT_STYLE, "width": "400px", "marginRight": "10px"},
                                        ),
                                        html.Button(
                                            "Search",
                                            id="search-id-button",
                                            n_clicks=0,
                                            style=BUTTON_STYLE,
                                        ),
                                    ]
                                ),
                            ]
                        )
                    ]),
                    dcc.Tab(label="Cone Search", value="cone-search", children=[
                        html.Div(
                            [
                                html.P(
                                    "Search for objects within a specified radius of sky coordinates",
                                    style={"color": COLORS["muted"], "fontSize": "14px", "marginTop": "15px", "marginBottom": "15px"}
                                ),
                                html.Div(
                                    [
                                        html.Div(
                                            [
                                                html.Label(
                                                    "RA (degrees):",
                                                    style={
                                                        "display": "block",
                                                        "marginBottom": "5px",
                                                        "fontWeight": "500",
                                                        "fontSize": "14px"
                                                    }
                                                ),
                                                dcc.Input(
                                                    id="ra-input",
                                                    type="number",
                                                    placeholder="0-360",
                                                    style={**INPUT_STYLE, "width": "150px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "marginRight": "20px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Dec (degrees):",
                                                    style={
                                                        "display": "block",
                                                        "marginBottom": "5px",
                                                        "fontWeight": "500",
                                                        "fontSize": "14px"
                                                    }
                                                ),
                                                dcc.Input(
                                                    id="dec-input",
                                                    type="number",
                                                    placeholder="-90 to 90",
                                                    style={**INPUT_STYLE, "width": "150px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "marginRight": "20px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Label(
                                                    "Radius (arcsec):",
                                                    style={
                                                        "display": "block",
                                                        "marginBottom": "5px",
                                                        "fontWeight": "500",
                                                        "fontSize": "14px"
                                                    }
                                                ),
                                                dcc.Input(
                                                    id="radius-input",
                                                    type="number",
                                                    placeholder="Default: 30",
                                                    value=30,
                                                    style={**INPUT_STYLE, "width": "150px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "marginRight": "20px"},
                                        ),
                                        html.Div(
                                            [
                                                html.Button(
                                                    "Search",
                                                    id="cone-search-button",
                                                    n_clicks=0,
                                                    style={**BUTTON_STYLE, "marginTop": "21px"},
                                                ),
                                            ],
                                            style={"display": "inline-block", "verticalAlign": "top"},
                                        ),
                                    ]
                                ),
                            ]
                        )
                    ]),
                ],
                style={"marginBottom": "20px"}
            ),
        ],
        style=SECTION_STYLE,
    )


def create_search_by_id():
    """Create the search by ID component.

    Returns:
        html.Div containing search by ID UI
    """
    return html.Div(
        [
            html.H2("Search by Object ID", style={"marginTop": "0", "color": COLORS["secondary"]}),
            html.P(
                "Enter a TNS object name to view its metadata and lightcurve",
                style={"color": COLORS["muted"], "fontSize": "14px", "marginBottom": "15px"}
            ),
            html.Div(
                [
                    dcc.Input(
                        id="object-id-input",
                        type="text",
                        placeholder="Enter object ID (e.g., 2024abc)",
                        style={**INPUT_STYLE, "width": "400px", "marginRight": "10px"},
                    ),
                    html.Button(
                        "Search ID",
                        id="search-id-button",
                        n_clicks=0,
                        style=BUTTON_STYLE,
                    ),
                ]
            ),
        ],
        style=SECTION_STYLE,
    )


def create_cone_search():
    """Create the cone search component.

    Returns:
        html.Div containing cone search UI
    """
    return html.Div(
        [
            html.H2("Cone Search by Coordinates", style={"marginTop": "0", "color": COLORS["secondary"]}),
            html.P(
                "Search for objects within a specified radius of sky coordinates",
                style={"color": COLORS["muted"], "fontSize": "14px", "marginBottom": "15px"}
            ),
            html.Div(
                [
                    html.Div(
                        [
                            html.Label(
                                "RA (degrees):",
                                style={
                                    "display": "block",
                                    "marginBottom": "5px",
                                    "fontWeight": "500",
                                    "fontSize": "14px"
                                }
                            ),
                            dcc.Input(
                                id="ra-input",
                                type="number",
                                placeholder="0-360",
                                style={**INPUT_STYLE, "width": "150px"},
                            ),
                        ],
                        style={"display": "inline-block", "marginRight": "20px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Dec (degrees):",
                                style={
                                    "display": "block",
                                    "marginBottom": "5px",
                                    "fontWeight": "500",
                                    "fontSize": "14px"
                                }
                            ),
                            dcc.Input(
                                id="dec-input",
                                type="number",
                                placeholder="-90 to 90",
                                style={**INPUT_STYLE, "width": "150px"},
                            ),
                        ],
                        style={"display": "inline-block", "marginRight": "20px"},
                    ),
                    html.Div(
                        [
                            html.Label(
                                "Radius (arcsec):",
                                style={
                                    "display": "block",
                                    "marginBottom": "5px",
                                    "fontWeight": "500",
                                    "fontSize": "14px"
                                }
                            ),
                            dcc.Input(
                                id="radius-input",
                                type="number",
                                placeholder="Default: 30",
                                value=30,
                                style={**INPUT_STYLE, "width": "150px"},
                            ),
                        ],
                        style={"display": "inline-block", "marginRight": "20px"},
                    ),
                    html.Div(
                        [
                            html.Button(
                                "Cone Search",
                                id="cone-search-button",
                                n_clicks=0,
                                style={**BUTTON_STYLE, "marginTop": "21px"},
                            ),
                        ],
                        style={"display": "inline-block", "verticalAlign": "top"},
                    ),
                ]
            ),
        ],
        style=SECTION_STYLE,
    )


def create_results_section():
    """Create the results display section.

    Returns:
        html.Div for displaying search results
    """
    return html.Div(
        [
            html.Div(
                id="search-status",
                style={
                    "padding": "10px",
                    "color": COLORS["muted"],
                    "fontStyle": "italic",
                    "fontSize": "14px"
                }
            ),
            html.Div(id="results-container"),
        ],
    )
