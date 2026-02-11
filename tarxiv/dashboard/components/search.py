"""Search UI components."""

from dash import html
import dash_mantine_components as dmc
from ..components import expressive_card


# def create_unified_search():
#     """Create a unified search interface with tabs.

#     Returns
#     -------
#         html.Div containing tabbed search UI
#     """
#     # return dmc.Container(
#     return expressive_card(
#         title="Search Tarxiv Database",
#         title_order=2,
#         children=[
#             # dmc.Title(
#             #     "Search TarXiv Database",
#             #     order=2,
#             #     style={"marginBottom": "20px"},
#             # ),
#             dmc.Tabs(
#                 id="search-tabs",
#                 value="id-search",
#                 style={"marginBottom": "20px"},
#                 children=[
#                     dmc.TabsList(
#                         justify="space-around",
#                         grow=True,
#                         children=[
#                             dmc.TabsTab("Search by Object ID", value="id-search"),
#                             dmc.TabsTab("Cone Search", value="cone-search"),
#                         ],
#                     ),
#                     dmc.TabsPanel(
#                         value="id-search",
#                         children=[
#                             html.Div(
#                                 [
#                                     dmc.Text(
#                                         "Enter a TNS object name to view its metadata and lightcurve",
#                                         style={
#                                             "fontSize": "14px",
#                                             "marginTop": "15px",
#                                             "marginBottom": "15px",
#                                         },
#                                     ),
#                                     dmc.Group(
#                                         [
#                                             dmc.TextInput(
#                                                 id="object-id-input",
#                                                 placeholder="Enter object ID (e.g., 2024abc)",
#                                                 style={
#                                                     "width": "400px",
#                                                     "marginRight": "10px",
#                                                 },
#                                             ),
#                                             dmc.Button(
#                                                 "Search",
#                                                 id="search-id-button",
#                                                 n_clicks=0,
#                                                 style={},
#                                             ),
#                                         ]
#                                     ),
#                                 ]
#                             )
#                         ],
#                     ),
#                     dmc.TabsPanel(
#                         value="cone-search",
#                         children=[
#                             dmc.Text(
#                                 "Search for objects within a specified radius of sky coordinates",
#                                 style={
#                                     "fontSize": "14px",
#                                     "marginTop": "15px",
#                                     "marginBottom": "15px",
#                                 },
#                             ),
#                             dmc.Group(
#                                 [
#                                     dmc.NumberInput(
#                                         id="ra-input",
#                                         placeholder="0-360",
#                                         min=0,
#                                         max=360,
#                                         label="RA (degrees):",
#                                         style={
#                                             "width": "150px",
#                                         },
#                                     ),
#                                     dmc.NumberInput(
#                                         id="dec-input",
#                                         placeholder="-90 to 90",
#                                         min=-90,
#                                         max=90,
#                                         label="Dec (degrees):",
#                                         style={
#                                             "width": "150px",
#                                         },
#                                     ),
#                                     dmc.NumberInput(
#                                         id="radius-input",
#                                         placeholder=">0",
#                                         # value=30,
#                                         min=0,
#                                         label="Radius (arcsec):",
#                                         style={
#                                             "width": "150px",
#                                         },
#                                     ),
#                                     dmc.Button(
#                                         "Search",
#                                         id="cone-search-button",
#                                         n_clicks=0,
#                                         style={"marginTop": "21px"},
#                                     ),
#                                 ]
#                             ),
#                         ],
#                     ),
#                 ],
#             ),
#         ],
#     )


def create_results_section():
    """Create the results display section.

    Returns
    -------
        dmc.Container containing results display area
    """
    # return dmc.Container(
    return dmc.Stack(
        [
            dmc.Text(
                id="search-status",
                style={
                    "padding": "10px",
                    "fontStyle": "italic",
                    "fontSize": "14px",
                },
            ),
            dmc.Stack(
                id="results-container",
            ),
        ],
    )
