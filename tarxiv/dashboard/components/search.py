"""Search UI components."""

from dash import html
import dash_mantine_components as dmc
from ..components import ExpressiveCard


def create_unified_search():
    """Create a unified search interface with tabs.

    Returns
    -------
        html.Div containing tabbed search UI
    """
    # return dmc.Container(
    return ExpressiveCard(
        children=[
            dmc.Title(
                "Search TarXiv Database",
                order=2,
                style={"marginBottom": "20px"},
            ),
            dmc.Tabs(
                id="search-tabs",
                value="id-search",
                style={"marginBottom": "20px"},
                children=[
                    dmc.TabsList(
                        justify="space-around",
                        grow=True,
                        children=[
                            dmc.TabsTab("Search by Object ID", value="id-search"),
                            dmc.TabsTab("Cone Search", value="cone-search"),
                        ],
                    ),
                    dmc.TabsPanel(
                        value="id-search",
                        children=[
                            html.Div(
                                [
                                    dmc.Text(
                                        "Enter a TNS object name to view its metadata and lightcurve",
                                        style={
                                            "fontSize": "14px",
                                            "marginTop": "15px",
                                            "marginBottom": "15px",
                                        },
                                    ),
                                    dmc.Group(
                                        [
                                            dmc.TextInput(
                                                id="object-id-input",
                                                placeholder="Enter object ID (e.g., 2024abc)",
                                                style={
                                                    "width": "400px",
                                                    "marginRight": "10px",
                                                },
                                            ),
                                            dmc.Button(
                                                "Search",
                                                id="search-id-button",
                                                n_clicks=0,
                                                style={},
                                            ),
                                        ]
                                    ),
                                ]
                            )
                        ],
                    ),
                    dmc.TabsPanel(
                        value="cone-search",
                        children=[
                            dmc.Text(
                                "Search for objects within a specified radius of sky coordinates",
                                style={
                                    "fontSize": "14px",
                                    "marginTop": "15px",
                                    "marginBottom": "15px",
                                },
                            ),
                            dmc.Group(
                                [
                                    dmc.NumberInput(
                                        id="ra-input",
                                        placeholder="0-360",
                                        min=0,
                                        max=360,
                                        label="RA (degrees):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                    dmc.NumberInput(
                                        id="dec-input",
                                        placeholder="-90 to 90",
                                        min=-90,
                                        max=90,
                                        label="Dec (degrees):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                    dmc.NumberInput(
                                        id="radius-input",
                                        placeholder=">0",
                                        # value=30,
                                        min=0,
                                        label="Radius (arcsec):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                    dmc.Button(
                                        "Search",
                                        id="cone-search-button",
                                        n_clicks=0,
                                        style={"marginTop": "21px"},
                                    ),
                                ]
                            ),
                        ],
                    ),
                ],
            ),
        ],
        # style=SECTION_STYLE,
    )


# def create_search_by_id():
#     """Create the search by ID component.

#     Returns
#     -------
#         html.Div containing search by ID UI
#     """
#     # return html.Div(
#     return dmc.Container(
#         [
#             dmc.Title(
#                 "Search by Object ID",
#                 order=2,
#                 style={"marginBottom": "20px"},
#             ),
#             dmc.Text(
#                 "Enter a TNS object name to view its metadata and lightcurve",
#                 style={"fontSize": "14px", "marginBottom": "15px"},
#             ),
#             # html.Div(
#             dmc.Group(
#                 [
#                     dcc.Input(
#                         id="object-id-input",
#                         type="text",
#                         placeholder="Enter object ID (e.g., 2024abc)",
#                         style={**INPUT_STYLE, "width": "400px", "marginRight": "10px"},
#                     ),
#                     dmc.Button(
#                         "Search ID",
#                         id="search-id-button",
#                         n_clicks=0,
#                         style={},
#                     ),
#                 ]
#             ),
#         ],
#         style=SECTION_STYLE,
#     )


# def create_cone_search():
#     """Create the cone search component.

#     Returns
#     -------
#         html.Div containing cone search UI
#     """
#     return html.Div(
#         [
#             dmc.Title(
#                 "Cone Search by Coordinates",
#                 order=2,
#                 style={"marginBottom": "20px"},
#             ),
#             dmc.Text(
#                 "Search for objects within a specified radius of sky coordinates",
#                 style={"fontSize": "14px", "marginBottom": "15px"},
#             ),
#             html.Div(
#                 [
#                     html.Div(
#                         [
#                             html.Label(
#                                 "RA (degrees):",
#                                 style={
#                                     "display": "block",
#                                     "marginBottom": "5px",
#                                     "fontWeight": "500",
#                                     "fontSize": "14px",
#                                 },
#                             ),
#                             dcc.Input(
#                                 id="ra-input",
#                                 type="number",
#                                 placeholder="0-360",
#                                 style={**INPUT_STYLE, "width": "150px"},
#                             ),
#                         ],
#                         style={"display": "inline-block", "marginRight": "20px"},
#                     ),
#                     html.Div(
#                         [
#                             html.Label(
#                                 "Dec (degrees):",
#                                 style={
#                                     "display": "block",
#                                     "marginBottom": "5px",
#                                     "fontWeight": "500",
#                                     "fontSize": "14px",
#                                 },
#                             ),
#                             dcc.Input(
#                                 id="dec-input",
#                                 type="number",
#                                 placeholder="-90 to 90",
#                                 style={**INPUT_STYLE, "width": "150px"},
#                             ),
#                         ],
#                         style={"display": "inline-block", "marginRight": "20px"},
#                     ),
#                     html.Div(
#                         [
#                             html.Label(
#                                 "Radius (arcsec):",
#                                 style={
#                                     "display": "block",
#                                     "marginBottom": "5px",
#                                     "fontWeight": "500",
#                                     "fontSize": "14px",
#                                 },
#                             ),
#                             dcc.Input(
#                                 id="radius-input",
#                                 type="number",
#                                 placeholder="Default: 30",
#                                 value=30,
#                                 style={**INPUT_STYLE, "width": "150px"},
#                             ),
#                         ],
#                         style={"display": "inline-block", "marginRight": "20px"},
#                     ),
#                     html.Div(
#                         [
#                             dmc.Button(
#                                 "Cone Search",
#                                 id="cone-search-button",
#                                 n_clicks=0,
#                                 style={"marginTop": "21px"},
#                             ),
#                         ],
#                         style={"display": "inline-block", "verticalAlign": "top"},
#                     ),
#                 ]
#             ),
#         ],
#         style=SECTION_STYLE,
#     )


def create_results_section():
    """Create the results display section.

    Returns
    -------
        dmc.Container containing results display area
    """
    return dmc.Container(
        [
            dmc.Text(
                id="search-status",
                style={
                    "padding": "10px",
                    # "color": COLORS["muted"],
                    "fontStyle": "italic",
                    "fontSize": "14px",
                },
            ),
            dmc.Stack(
                id="results-container",
            ),
        ],
    )
