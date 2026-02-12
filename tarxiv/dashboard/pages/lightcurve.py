import dash
from dash import html, callback, ctx, no_update, dcc
from dash.dependencies import Input, Output, State
from flask import current_app
import dash_mantine_components as dmc
from ..components import (
    title_card,
    expressive_card,
    format_object_metadata,
    create_message_banner,
)
from ..schemas import (
    MetadataResponseModel,
    LightcurveResponseModel,
)
import requests
from pydantic import ValidationError
import os

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
    logger = current_app.config["TXV_LOGGER"]
    if id:
        results, status, banner, lc_store, meta_store = perform_search(id, logger)
    else:
        results, status, banner, lc_store, meta_store = (
            html.Div(),
            "",
            html.Div(),
            no_update,
            no_update,
        )

    return dmc.Stack(
        children=[
            dcc.Store(id="lightcurve-store", data=lc_store),
            dcc.Store(id="lightcurve-meta-store", data=meta_store),
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
                        children=[results],
                    ),
                ],
            ),
        ],
    )


# Remove the url input listener and rely solely on the button.
# Implement the URL-based search in the layout function by pre-populating the input.
# This simplifies the callback and avoids potential issues with multiple triggers.
@callback(
    [
        Output("results-container", "children", allow_duplicate=True),
        Output("search-status", "children", allow_duplicate=True),
        Output("message-banner", "children", allow_duplicate=True),
        Output("lightcurve-store", "data"),
        Output("lightcurve-meta-store", "data"),
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
    logger = current_app.config["TXV_LOGGER"]

    triggered_id = ctx.triggered_id

    # 1. Determine the ID
    if triggered_id == "search-id-button":
        target_id = state_id
    # elif pathname and pathname.startswith("/lightcurve/"):
    #     target_id = pathname.split("/")[-1]
    else:
        return [no_update] * 7

    if not target_id:
        return [no_update] * 7

    # 2. Run your search logic
    try:
        results, status, banner, lc_store, meta_store = perform_search(
            target_id, logger
        )

        # 3. Define the new URL path
        new_path = f"/lightcurve/{target_id}"

        # Return all values, including the new URL path
        return results, status, banner, lc_store, meta_store, target_id, new_path

    except Exception as e:
        return (
            html.Div(),
            "Error",
            create_message_banner(str(e), "error"),
            no_update,
            no_update,
            target_id,
            no_update,
        )


@callback(
    Output("aladin-lite-runjs", "run"),
    # Triggered by the search-store or metadata container being updated
    Input("lightcurve-meta-store", "data"),
    prevent_initial_call=True,
)
def update_aladin_viewer(store_data):
    """Triggers the Aladin JS ONLY when new data arrives."""
    if not store_data:
        return no_update

    # Extract RA/Dec from your stored metadata
    # (Assuming your store_data has these keys)
    print(f"Received store data for Aladin: {store_data}")
    ra = store_data.get("ra_deg", 0)[0].get("value", 0)
    dec = store_data.get("dec_deg", 0)[0].get("value", 0)
    print(f"Extracted RA: {ra}, Dec: {dec} for Aladin viewer.")

    return generate_aladin_js(ra, dec)


def generate_aladin_js(ra, dec):
    """v3 compliant Aladin initialization."""
    print(f"Generating Aladin JS for RA: {ra}, Dec: {dec}")
    return f"""
// Clear the div first to prevent the 'Multiple Instance' loop
document.getElementById('aladin-lite-div').innerHTML = '';

// v3 requires the .then() wrapper
A.init.then(() => {{
    var aladin = A.aladin('#aladin-lite-div', {{
        survey: 'P/PanSTARRS/DR1/color-z-zg-g', // v3 uses different survey ID format
        fov: 0.025,
        target: '{ra} {dec}',
        reticleColor: '#ff89ff',
        reticleSize: 32,
    }});
    
    // Add your catalogs here...
}});
"""


def fetch_api_data(endpoint, object_id, logger):
    """Helper to perform API requests."""
    domain = os.getenv("TARXIV_HOST")
    port = os.getenv("TARXIV_PORT")
    try:
        response = requests.post(
            url=f"http://{domain}:{port}/{endpoint}/{object_id}",
            timeout=10,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "TOKEN",
            },
        )
        logger.info({"info": f"{endpoint} response status: {response.status_code}"})
        return response
    except Exception as e:
        logger.error({"error": f"Failed to fetch {endpoint}: {str(e)}"})
        return None


def get_metadata_data(object_id, logger):
    """Fetch metadata for an object."""
    response = fetch_api_data("get_object_meta", object_id, logger)
    if response and response.status_code == 200:
        try:
            data = MetadataResponseModel.model_validate_json(response.text)
            return data.model_dump()
        except ValidationError as e:
            logger.error(
                {"error": f"Failed to parse metadata for object {object_id}: {str(e)}"}
            )
    else:
        if response:
            logger.error(
                {
                    "error": f"Metadata request failed for object {object_id}: "
                    f"Status {response.status_code}"
                }
            )
    return None


def get_lightcurve_data(object_id, logger):
    """Fetch lightcurve data for an object."""
    response = fetch_api_data("get_object_lc", object_id, logger)
    if response and response.status_code == 200:
        try:
            data = LightcurveResponseModel.validate_json(response.text)
            logger.info(
                {
                    "success": f"Parsed lightcurve for object {object_id}: {len(data)} points"
                }
            )
            return LightcurveResponseModel.dump_python(data)
        except ValidationError as e:
            logger.error(
                {
                    "error": f"Failed to parse lightcurve for object {object_id}: {str(e)}"
                }
            )
    else:
        if response:
            logger.error(
                {
                    "error": f"Lightcurve request failed for object {object_id}: "
                    f"Status {response.status_code}"
                }
            )
    return None


def perform_search(object_id, logger):
    """The core logic shared by both Button and URL triggers."""
    status_msg = f"Searching for object: {object_id}"
    logger.info({"search_type": "id", "object_id": object_id})

    # Fetch Metadata
    meta = get_metadata_data(object_id, logger)

    if meta is None:
        error_banner = create_message_banner(
            f"No object found with ID: {object_id}", "error"
        )
        logger.warning({"warning": f"Object ID not found: {object_id}"})
        return no_update, status_msg, error_banner, no_update, no_update

    # Fetch Lightcurve
    lc_data = get_lightcurve_data(object_id, logger)

    # Display metadata
    result = format_object_metadata(object_id, meta, logger)
    success_banner = create_message_banner(
        f"Successfully loaded object: {object_id}", "success"
    )
    logger.info({"info": f"Object {object_id} loaded successfully."})

    lc_store = {"data": lc_data, "id": object_id}
    meta_store = meta

    return result, status_msg, success_banner, lc_store, meta_store
