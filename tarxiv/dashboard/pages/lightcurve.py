import dash
from dash import html, callback, ctx, no_update, dcc
from dash.dependencies import Input, Output, State
from flask import current_app
import dash_mantine_components as dmc
from ..components import (
    title_card,
    expressive_card,
    create_results_section,
    format_object_metadata,
)

dash.register_page(
    __name__,
    path="/lightcurve",
    path_template="/lightcurve/<id>",
    title="Lightcurve",
    order=1,
    icon="clarity:curve-chart-line",
)


def layout(id=None, **kwargs):
    # perform search if id is provided in URL, otherwise show empty search page
    if id:
        txv_db = current_app.config["TXV_DB"]
        logger = current_app.config["TXV_LOGGER"]
        try:
            res, status, banner, store = perform_search(id, txv_db, logger)
        except Exception as e:
            res, status, banner, store = (
                html.Div(),
                "Error",
                create_message_banner(str(e), "error"),
                no_update,
            )
    else:
        res, status, banner, store = html.Div(), "", html.Div(), no_update
    return dmc.Stack(
        children=[
            dcc.Store(id="lightcurve-store", data=store),
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="Lightcurve Search",
                children=[
                    dmc.Stack(
                        [
                            dmc.Text(
                                "Enter a TNS object name to view its metadata and lightcurve",
                            ),
                            dmc.Group(
                                [
                                    dmc.TextInput(
                                        id="object-id-input",
                                        placeholder="Enter object ID (e.g., 2024abc)",
                                        value=id,  # Pre-populate with URL parameter
                                        style={
                                            "width": "400px",
                                            "marginRight": "10px",
                                        },
                                    ),
                                    dmc.Button(
                                        "Search",
                                        id="search-id-button",
                                        n_clicks=0,
                                    ),
                                ]
                            ),
                        ]
                    ),
                ],
            ),
            dmc.Box(
                id="message-banner",
                children=[banner],
                style={"marginBottom": "20px"},
            ),
            # create_results_section(),
            dmc.Stack(
                [
                    dmc.Text(
                        id="search-status",
                        style={
                            "padding": "10px",
                            "fontStyle": "italic",
                            "fontSize": "14px",
                        },
                        children=status,
                    ),
                    dmc.Stack(
                        id="results-container",
                        children=[res],
                    ),
                ],
            ),
        ],
    )


# @callback(
#     [
#         Output("results-container", "children", allow_duplicate=True),
#         Output("search-status", "children", allow_duplicate=True),
#         Output("message-banner", "children", allow_duplicate=True),
#         Output("lightcurve-store", "data"),
#         Output("object-id-input", "value"),
#         Output("url", "pathname"),  # refresh URL
#     ],
#     [
#         Input("search-id-button", "n_clicks", allow_optional=True),
#         Input("url", "pathname"),  # Listen to the URL for deep linking
#     ],
#     [State("object-id-input", "value")],
#     prevent_initial_call=True,
# )
# def handle_combined_search(n_clicks, pathname, state_id):
#     # if pathname is not None and not pathname.startswith("/lightcurve"):
#     #     return [no_update] * 6

#     txv_db = current_app.config["TXV_DB"]
#     logger = current_app.config["TXV_LOGGER"]

#     triggered_id = ctx.triggered_id

#     # 1. Determine the ID
#     if triggered_id == "search-id-button":
#         target_id = state_id
#     elif pathname and pathname.startswith("/lightcurve/"):
#         target_id = pathname.split("/")[-1]
#     else:
#         return [no_update] * 6

#     if not target_id:
#         return [no_update] * 6

#     # 2. Run your search logic
#     try:
#         res, status, banner, store = perform_search(target_id, txv_db, logger)

#         # 3. Define the new URL path
#         new_path = f"/lightcurve/{target_id}"

#         # Return all values, including the new URL path
#         return res, status, banner, store, target_id, new_path

#     except Exception as e:
#         return (
#             html.Div(),
#             "Error",
#             create_message_banner(str(e), "error"),
#             no_update,
#             target_id,
#             no_update,
#         )


# Remove the url input listener and rely solely on the button.
# Implement the URL-based search in the layout function by pre-populating the input.
# This simplifies the callback and avoids potential issues with multiple triggers.
@callback(
    [
        Output("results-container", "children", allow_duplicate=True),
        Output("search-status", "children", allow_duplicate=True),
        Output("message-banner", "children", allow_duplicate=True),
        Output("lightcurve-store", "data"),
        Output("object-id-input", "value"),
        Output("url", "pathname"),  # refresh URL
    ],
    [
        # Input("search-id-button", "n_clicks", allow_optional=True),
        Input("search-id-button", "n_clicks"),
        # Input("url", "pathname"),  # Listen to the URL for deep linking
    ],
    [State("object-id-input", "value")],
    prevent_initial_call=True,
)
def handle_combined_search(n_clicks, state_id):
    txv_db = current_app.config["TXV_DB"]
    logger = current_app.config["TXV_LOGGER"]

    triggered_id = ctx.triggered_id

    # 1. Determine the ID
    if triggered_id == "search-id-button":
        target_id = state_id
    # elif pathname and pathname.startswith("/lightcurve/"):
    #     target_id = pathname.split("/")[-1]
    else:
        return [no_update] * 6

    if not target_id:
        return [no_update] * 6

    # 2. Run your search logic
    try:
        res, status, banner, store = perform_search(target_id, txv_db, logger)

        # 3. Define the new URL path
        new_path = f"/lightcurve/{target_id}"

        # Return all values, including the new URL path
        return res, status, banner, store, target_id, new_path

    except Exception as e:
        return (
            html.Div(),
            "Error",
            create_message_banner(str(e), "error"),
            no_update,
            target_id,
            no_update,
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
        message,
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


def perform_search(object_id, txv_db, logger):
    """The core logic shared by both Button and URL triggers."""
    if not object_id:
        return (
            no_update,
            "",
            create_message_banner("No ID provided.", "warning"),
            no_update,
        )

    meta = txv_db.get(object_id, "objects")
    if meta is None:
        return (
            no_update,
            f"Searching: {object_id}",
            create_message_banner(f"Not found: {object_id}", "error"),
            no_update,
        )

    lc_data = get_lightcurve_data(txv_db, object_id, logger)
    result = format_object_metadata(object_id, meta, logger)
    store_data = {"data": lc_data, "id": object_id}
    banner = create_message_banner(f"Loaded: {object_id}", "success")

    return result, f"Object: {object_id}", banner, store_data


def get_lightcurve_data(txv_db, object_id, logger):
    """Fetch lightcurve data for an object.

    Args:
        txv_db: TarxivDB instance
        object_id: Object identifier
        logger: Logger instance

    Returns
    -------
        Lightcurve data or None
    """
    try:
        lc_data = txv_db.get(object_id, "lightcurves")
        logger.debug(
            {
                "debug": f"Fetched lightcurve data for object: {object_id}: "
                f"{len(lc_data) if lc_data else lc_data}"
            }
        )
        return lc_data
    except Exception as e:
        logger.error({"error": f"Failed to fetch lightcurve: {str(e)}"})
        return None
