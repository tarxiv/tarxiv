import dash
from dash import html, callback, no_update, dcc
from dash.dependencies import Input, Output, State
from dash_extensions import Keyboard
from flask import current_app, request
from werkzeug.exceptions import Unauthorized
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
from urllib.parse import unquote

dash.register_page(
    __name__,
    path="/lightcurve",
    path_template="/lightcurve/<id>",
    title="TarXiv - Lightcurve",
    name="Lightcurve",
    order=1,
    icon="clarity:curve-chart-line",
)


def layout(id=None, **kwargs):
    # perform search if id is provided in URL, otherwise show empty search page
    logger = current_app.config["TXV_LOGGER"]

    token = unquote(request.cookies.get("tarxiv_user_token", ""))

    if id and token:
        # User came via deep link and has a saved session
        results, status, banner, lc_store, meta_store = perform_search(
            id, token, logger
        )
    elif id and not token:
        # Deep link but no token: Show the search bar pre-filled with ID
        # but warn the user that a token is missing.
        results = html.Div()
        status = "Authentication required"
        banner = create_message_banner(
            "Please enter your API token to view data.", "warning"
        )
        lc_store = None
        meta_store = None
    else:
        # Default empty search page
        results, status, banner, lc_store, meta_store = (
            html.Div(),
            "",
            html.Div(),
            None,
            None,
        )

    return dmc.Stack(
        children=[
            dcc.Store(id="lightcurve-store", storage_type="session", data=lc_store),
            dcc.Store(
                id="lightcurve-meta-store", storage_type="session", data=meta_store
            ),
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
                                    Keyboard(
                                        children=[
                                            dmc.TextInput(
                                                id="object-id-input",
                                                placeholder="Enter object ID (e.g., 2024abc)",
                                                value=id,  # Pre-populate with URL parameter
                                                style={
                                                    "width": "400px",
                                                    "marginRight": "10px",
                                                },
                                            ),
                                            dmc.VisuallyHidden(
                                                dmc.TextInput(
                                                    # When API auth is implemented, remove this input from the UI
                                                    # and remove the prepopulate_token() callback.
                                                    id="token",
                                                    placeholder="Enter a token",
                                                    value=token,  # Pre-populate with URL parameter
                                                    style={
                                                        "width": "400px",
                                                        "marginRight": "10px",
                                                    },
                                                )
                                            ),
                                        ],
                                        captureKeys=["Enter"],
                                        id="search-id-keyboard",
                                        n_keydowns=0,
                                    ),
                                    dmc.Button(
                                        "Search",
                                        id="search-id-button",
                                        n_clicks=0,
                                    ),
                                ],
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


# Callback to handle search navigation
@callback(
    Output("url", "pathname", allow_duplicate=True),
    [
        Input("search-id-button", "n_clicks"),
        Input("search-id-keyboard", "n_keydowns"),
    ],
    [State("object-id-input", "value")],
    prevent_initial_call=True,
)
def search_navigation(n_clicks, n_keydowns, object_id):
    if not object_id:
        return no_update

    # Redirect to the object-specific URL which will trigger a layout reload
    return f"/lightcurve/{object_id}"


@callback(
    Output("aladin-lite-runjs", "run"),
    # Triggered by the search-store or metadata container being updated
    Input("lightcurve-meta-store", "data"),
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


def fetch_api_data(endpoint, object_id, token, logger):
    """Helper to perform API requests."""
    # TODO: Refactor to use a shared API client module instead of hardcoding requests here
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_DASHBOARD_API_URL", f"http://{host}:{port}")
    # try:
    response = requests.post(
        url=f"{api_url}/{endpoint}/{object_id}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": token,
        },
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response
    # except Exception as e:
    #     logger.error({"error": f"Failed to fetch {endpoint}: {str(e)}"})
    #     return None


def get_metadata_data(object_id, token, logger):
    """Fetch metadata for an object."""
    response = fetch_api_data("get_object_meta", object_id, token, logger)

    if response.status_code == 200:
        try:
            data = MetadataResponseModel.model_validate_json(response.text)
            return data.model_dump()
        except ValidationError as e:
            logger.exception(e)
            logger.error(
                {"error": f"Failed to parse metadata for object {object_id}: {str(e)}"}
            )
    # authentication error
    elif response.status_code == 401:
        logger.warning(
            {
                "warning": f"Unauthorized access when fetching metadata for object {object_id}. "
                f"Check if the token is valid."
            }
        )
        raise Unauthorized("Invalid API token. Check your token.")

    logger.error(
        {
            "error": f"Metadata request failed for object {object_id}: "
            f"Status {response.status_code}"
        }
    )
    return None


def get_lightcurve_data(object_id, token, logger):
    """Fetch lightcurve data for an object."""
    response = fetch_api_data("get_object_lc", object_id, token, logger)
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


def perform_search(object_id, token, logger):
    """The core logic shared by both Button and URL triggers."""
    status_msg = f"Searching for object: {object_id}"
    logger.info({"search_type": "id", "object_id": object_id})

    # Fetch Metadata
    try:
        meta = get_metadata_data(object_id, token, logger)
    except Unauthorized as e:
        return (
            html.Div(),
            "Authentication required",
            create_message_banner(str(e), "error"),
            None,
            None,
        )
    except Exception as e:
        logger.error({"error": f"Unexpected error fetching metadata for {object_id}: {str(e)}"})
        logger.exception(e)
        return (
            html.Div(),
            "Error",
            create_message_banner(f"Failed to fetch metadata: {str(e)}", "error"),
            None,
            None,
        )

    if meta is None:
        error_banner = create_message_banner(
            f"No object found with ID: {object_id}", "error"
        )
        logger.warning({"warning": f"Object ID not found: {object_id}"})
        return html.Div(), status_msg, error_banner, None, None

    # Fetch Lightcurve
    lc_data = get_lightcurve_data(object_id, token, logger)

    # Display metadata
    result = format_object_metadata(object_id, meta, logger)
    success_banner = create_message_banner(
        f"Successfully loaded object: {object_id}", "success"
    )
    logger.info({"info": f"Object {object_id} loaded successfully."})

    lc_store = {"data": lc_data, "id": object_id}
    meta_store = meta

    return result, status_msg, success_banner, lc_store, meta_store
