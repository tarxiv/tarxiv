import dash
from dash import html, Input, Output, State, no_update, callback, dcc
import dash_mantine_components as dmc
from dash_extensions import Keyboard
from ..components import (
    title_card,
    expressive_card,
    format_cone_search_results,
    create_message_banner,
)
from ..schemas import ConeSearchResponseModel
import requests
from pydantic import ValidationError
from flask import current_app, request
from werkzeug.exceptions import Unauthorized
import os
from urllib.parse import unquote

dash.register_page(
    __name__,
    path="/cone",
    title="TarXiv - Cone Search",
    name="Cone Search",
    order=2,
    icon="lucide:cone",
)


def layout(**kwargs):
    # logger = current_app.config["TXV_LOGGER"]

    token = unquote(request.cookies.get("tarxiv_user_token", ""))

    return dmc.Stack(
        children=[
            dcc.Store(id="cone-search-store"),
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="Cone Search",
                children=[
                    dmc.Stack(
                        [
                            dmc.Text(
                                "Search for objects within a specified radius of sky coordinates",
                            ),
                            # dmc.Group(
                            dmc.Stack(
                                [
                                    Keyboard(
                                        children=dmc.Group(
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
                                            ]
                                        ),
                                        captureKeys=["Enter"],
                                        n_keydowns=0,
                                        id="cone-search-keyboard",
                                    ),
                                    dmc.Button(
                                        "Search",
                                        id="cone-search-button",
                                        n_clicks=0,
                                        style={"marginTop": "21px"},
                                    ),
                                ]
                            ),
                        ]
                    ),
                ],
            ),
            dmc.Box(
                id="message-banner",
                children=[],
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
                        # children=status,
                    ),
                    dmc.Stack(
                        id="results-container",
                        # children=[res],
                    ),
                ],
            ),
        ],
    )


@callback(
    [
        Output("results-container", "children", allow_duplicate=True),
        Output("search-status", "children", allow_duplicate=True),
        Output("message-banner", "children", allow_duplicate=True),
        Output("cone-search-store", "data"),
        Output("active-settings-store", "data", allow_duplicate=True),
    ],
    [
        Input("cone-search-button", "n_clicks"),
        Input("cone-search-keyboard", "n_keydowns"),
    ],
    [
        State("ra-input", "value"),
        State("dec-input", "value"),
        State("radius-input", "value"),
        State("token", "value"),
        State("active-settings-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_cone_search(n_clicks, n_keydowns, ra, dec, radius, token, settings):
    """Handle cone search button clicks."""
    logger = current_app.config["TXV_LOGGER"]

    if not token:
        warning_banner = create_message_banner(
            "Please provide an API token to perform the search.", "warning"
        )
        return html.Div(), "", warning_banner, no_update, no_update

    settings.update({"tarxiv_user_token": token})  # Save token to active settings

    if not ra or not dec or not radius:
        warning_banner = create_message_banner(
            "Please provide valid RA, Dec and radius coordinates.", "warning"
        )
        return html.Div(), "", warning_banner, no_update, no_update

    status_msg = f"Cone search: RA={ra}, Dec={dec}, radius={radius} arcsec"
    logger.info(
        {
            "search_type": "cone",
            "ra": ra,
            "dec": dec,
            "radius": radius,
        }
    )
    try:
        # Perform cone search
        results = get_cone_search_results(ra, dec, radius, token, logger)

        # Display results
        result = format_cone_search_results(results, ra, dec)
        success_banner = create_message_banner(
            f"Found {len(results)} object(s) in search region", "success"
        )
        logger.info({"info": f"Cone search found {len(results)} objects."})

        store_data = {"results": results, "ra": ra, "dec": dec}

        return result, status_msg, success_banner, store_data, settings
    except Unauthorized as e:
        logger.warning({"warning": f"Unauthorized cone search attempt: {str(e)}"})
        error_banner = create_message_banner(
            "Unauthorized: Invalid API token. Check your token.", "error"
        )
        return html.Div(), "Unauthorized", error_banner, no_update, no_update
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error({"error": error_msg})
        error_banner = create_message_banner(error_msg, "error")
        return html.Div(), "Error occurred", error_banner, no_update, no_update


def get_cone_search_results(ra, dec, radius, token, logger) -> list:
    """Perform a cone search.

    Args:
        txv_db: TarxivDB instance
        ra: Right Ascension
        dec: Declination
        radius: Search radius in arcseconds
        logger: Logger instance

    Returns
    -------
        List of search results
    """
    api_url = os.getenv("TARXIV_DASHBOARD_API_URL")
    response_cone = requests.post(
        url=f"{api_url}/cone_search",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": token,
        },
        json={"ra": ra, "dec": dec, "radius": radius},
    )

    results = []
    logger.info({"info": f"Cone search response status: {response_cone.status_code}"})

    print(response_cone.text)  # Debug: Print raw response text
    print(response_cone.headers)  # Debug: Print response headers
    print(response_cone.status_code)

    if response_cone.status_code == 200:
        try:
            data = ConeSearchResponseModel.validate_json(response_cone.text)
            results = ConeSearchResponseModel.dump_python(data)

            logger.debug(
                {
                    "debug": f"Cone search results for RA={ra}, Dec={dec}, "
                    f"radius={radius} arcsec: {len(results)} objects found"
                }
            )
        except ValidationError as e:
            logger.error({"error": f"Failed to parse cone search results: {str(e)}"})
    if response_cone.status_code == 401:
        logger.warning(
            {"warning": "Unauthorized cone search attempt. Check API token validity."}
        )
        raise Unauthorized("Invalid API token. Check your token.")
    else:
        logger.error(
            {"error": f"Cone search request failed: Status {response_cone.status_code}"}
        )

    return results
