import os
from typing import cast

import dash
from dash import html, Input, Output, State, no_update, callback, dcc, ctx
import dash_mantine_components as dmc
from dash_extensions import Keyboard
from astropy.coordinates import Angle
import astropy.units as u
import requests
from pydantic import ValidationError
from flask import current_app, request
from werkzeug.exceptions import Unauthorized

from ...auth import get_jwt_from_request, validate_token, TokenStatus
from ..components import (
    title_card,
    expressive_card,
    format_cone_search_results,
    create_message_banner,
)
from ..schemas import ConeSearchResponseModel

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

    # token = get_jwt_from_request(request)

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
                            dmc.Text(
                                "Option 1: Enter RA (degrees), Dec (degrees) and radius (arcsec)"
                            ),
                            dmc.Group(
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
                            dmc.Divider(label="OR", labelPosition="center"),
                            dmc.Text(
                                "Option 2: Enter RA (HMS), Dec (DMS) and radius (arcsec)"
                            ),
                            dmc.Group(
                                [
                                    Keyboard(
                                        children=dmc.Group(
                                            [
                                                dmc.TextInput(
                                                    id="ra-hms-input",
                                                    placeholder="21:01:36.90",
                                                    label="RA (HMS):",
                                                    style={
                                                        "width": "150px",
                                                    },
                                                ),
                                                dmc.TextInput(
                                                    id="dec-dms-input",
                                                    placeholder="+68:09:48.0",
                                                    label="Dec (DMS):",
                                                    style={
                                                        "width": "150px",
                                                    },
                                                ),
                                                dmc.NumberInput(
                                                    id="radius-hmsdms-input",
                                                    placeholder=">0",
                                                    min=0,
                                                    label="Radius (arcsec):",
                                                    style={
                                                        "width": "150px",
                                                    },
                                                ),
                                            ]
                                        ),
                                        captureKeys=["Enter"],
                                        n_keydowns=0,
                                        id="cone-search-hmsdms-keyboard",
                                    ),
                                    dmc.Button(
                                        "Search",
                                        id="cone-search-hmsdms-button",
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


def parse_hms_dms_coordinates(ra_hms: str, dec_dms: str) -> tuple[float, float]:
    """Parse RA (HMS) and Dec (DMS) strings into degrees.

    Supported inputs include RA values like '21 01 36.90' or '21:01:36.90',
    and Dec values like '+68 09 48.0' or '+68:09:48.0'.
    """
    cleaned_ra = " ".join(ra_hms.strip().split())
    cleaned_dec = " ".join(dec_dms.strip().split())
    if not cleaned_ra or not cleaned_dec:
        raise ValueError("Please provide both RA (HMS) and Dec (DMS) coordinates.")

    try:
        ra_angle = Angle(cleaned_ra, unit=u.hourangle)
        dec_angle = Angle(cleaned_dec, unit=u.deg)
    except Exception as exc:
        raise ValueError(
            "Could not parse RA/Dec. Use formats like "
            "RA='21 01 36.90' or '21:01:36.90' and "
            "Dec='+68 09 48.0' or '+68:09:48.0'."
        ) from exc

    # cast to float to satisfy type checker, as Angle.degree is a Quantity
    # return float(cast(Any, ra_angle.degree)), float(cast(Any, dec_angle.degree))
    return cast(float, ra_angle.degree), cast(float, dec_angle.degree)


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
        Input("cone-search-hmsdms-button", "n_clicks"),
        Input("cone-search-hmsdms-keyboard", "n_keydowns"),
    ],
    [
        State("ra-input", "value"),
        State("dec-input", "value"),
        State("radius-input", "value"),
        State("ra-hms-input", "value"),
        State("dec-dms-input", "value"),
        State("radius-hmsdms-input", "value"),
        State("active-settings-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_cone_search(
    n_clicks,
    n_keydowns,
    n_hmsdms_clicks,
    n_hmsdms_keydowns,
    ra,
    dec,
    radius,
    ra_hms,
    dec_dms,
    radius_hmsdms,
    settings,
):
    """Handle cone search button clicks."""
    logger = current_app.config["TXV_LOGGER"]

    token = get_jwt_from_request(request)
    validation = validate_token(token)

    if validation["status"] == TokenStatus.EXPIRED:
        warning_banner = create_message_banner(
            "Your session has expired. Please log in again.", "warning"
        )
        return html.Div(), "", warning_banner, no_update, no_update
    elif validation["status"] == TokenStatus.INVALID and token:
        warning_banner = create_message_banner(
            "Invalid authentication token. Please log in again.", "error"
        )
        return html.Div(), "", warning_banner, no_update, no_update
    elif not token or validation["status"] != TokenStatus.VALID:
        warning_banner = create_message_banner(
            "Please log in to perform the search.", "warning"
        )
        return html.Div(), "", warning_banner, no_update, no_update

    if not isinstance(settings, dict):
        settings = {}

    settings.update({"tarxiv_user_token": token})  # Save token to active settings

    trigger_id = ctx.triggered_id
    use_hmsdms_input = trigger_id in {
        "cone-search-hmsdms-button",
        "cone-search-hmsdms-keyboard",
    }

    if use_hmsdms_input:
        if (
            not ra_hms
            or not str(ra_hms).strip()
            or not dec_dms
            or not str(dec_dms).strip()
        ):
            warning_banner = create_message_banner(
                "Please provide both RA (HMS) and Dec (DMS) coordinates.", "warning"
            )
            return html.Div(), "", warning_banner, no_update, no_update
        if radius_hmsdms is None or radius_hmsdms <= 0:
            warning_banner = create_message_banner(
                "Please provide a radius greater than zero.", "warning"
            )
            return html.Div(), "", warning_banner, no_update, no_update

        try:
            ra, dec = parse_hms_dms_coordinates(ra_hms, dec_dms)
        except ValueError as exc:
            warning_banner = create_message_banner(str(exc), "warning")
            return html.Div(), "", warning_banner, no_update, no_update

        radius = float(radius_hmsdms)
    else:
        if ra is None or dec is None or radius is None:
            warning_banner = create_message_banner(
                "Please provide valid RA, Dec and radius coordinates.", "warning"
            )
            return html.Div(), "", warning_banner, no_update, no_update
        if radius <= 0:
            warning_banner = create_message_banner(
                "Please provide a radius greater than zero.", "warning"
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
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response_cone = requests.post(
        url=f"{api_url}/cone_search",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
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
    elif response_cone.status_code == 401:
        logger.warning(
            {"warning": "Unauthorized cone search attempt. Check API token validity."}
        )
        raise Unauthorized("Invalid API token. Check your token.")
    else:
        logger.error(
            {"error": f"Cone search request failed: Status {response_cone.status_code}"}
        )

    return results
