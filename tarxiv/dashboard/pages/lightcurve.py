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
        res, status, banner, store = get_meta_data(id, logger)
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
                    dmc.Stack([
                        dmc.Text(
                            "Enter a TNS object name to view its metadata and lightcurve",
                        ),
                        dmc.Group([
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
                        ]),
                    ]),
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
                        children=[res],
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
        return [no_update] * 6

    if not target_id:
        return [no_update] * 6

    # 2. Run your search logic
    try:
        res, status, banner, store = get_meta_data(target_id, logger)

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


def get_meta_data(object_id, logger):
    """The core logic shared by both Button and URL triggers."""
    status_msg = f"Searching for object: {object_id}"
    logger.info({"search_type": "id", "object_id": object_id})

    response_meta = requests.post(
        url=f"http://tarxiv-api:9001/get_object_meta/{object_id}",  # TODO: Fix URL
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": "TOKEN",
        },
    )
    meta = None
    logger.info({"info": f"Metadata response status: {response_meta.status_code}"})
    # logger.info({"info": f"Metadata response text: {response_meta.text}"})
    if response_meta.status_code == 200:
        try:
            data = MetadataResponseModel.model_validate_json(response_meta.text)
        except ValidationError as e:
            logger.error({
                "error": f"Failed to parse metadata for object {object_id}: {str(e)}"
            })
            error_banner = create_message_banner(
                f"Failed to parse metadata for object: {object_id}", "error"
            )
            return no_update, "", error_banner, no_update
    else:
        logger.error({
            "error": f"Metadata request failed for object {object_id}: "
            f"Status {response_meta.status_code}"
        })
        error_banner = create_message_banner(
            f"Metadata request failed for object: {object_id}", "error"
        )
        return no_update, "", error_banner, no_update

    meta = data.model_dump()
    # Get metadata
    if meta is None:
        error_banner = create_message_banner(
            f"No object found with ID: {object_id}", "error"
        )
        logger.warning({"warning": f"Object ID not found: {object_id}"})
        return no_update, status_msg, error_banner, no_update

    # Get lightcurve data
    lc_data = get_lightcurve_data(object_id, logger)

    # Display metadata
    result = format_object_metadata(object_id, meta, logger)
    success_banner = create_message_banner(
        f"Successfully loaded object: {object_id}", "success"
    )
    logger.info({"info": f"Object {object_id} loaded successfully."})

    store_data = {"data": lc_data, "id": object_id}

    return result, status_msg, success_banner, store_data


def get_lightcurve_data(object_id, logger):
    """Fetch lightcurve data for an object.

    Args:
        object_id: Object identifier
        logger: Logger instance

    Returns
    -------
        Lightcurve data or None
    """
    try:
        response_lc = requests.post(
            url=f"http://tarxiv-api:9001/get_object_lc/{object_id}",  # TODO: Fix URL
            timeout=10,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": "TOKEN",
            },
        )
        # response_lc.text will contain a list of LightcurveResponseSingle
        data = None
        logger.info({"info": f"Lightcurve response status: {response_lc.status_code}"})
        if response_lc.status_code == 200:
            try:
                data = LightcurveResponseModel.validate_json(response_lc.text)

                logger.info({
                    "success": f"Parsed lightcurve for object {object_id}: {len(data)} points"
                })

            except ValidationError as e:
                logger.error({
                    "error": f"Failed to parse lightcurve for object {object_id}: {str(e)}"
                })
                return None
        else:
            logger.error({
                "error": f"Lightcurve request failed for object {object_id}: "
                f"Status {response_lc.status_code}"
            })
            return None

        return LightcurveResponseModel.dump_python(data)
    except Exception as e:
        logger.error({"error": f"Failed to fetch lightcurve: {str(e)}"})
        return None
