import os
from typing import cast
from urllib.parse import parse_qs, urlencode

import dash
from dash import (
    html,
    Input,
    Output,
    State,
    no_update,
    callback,
    clientside_callback,
    ClientsideFunction,
    dcc,
    ctx,
)
import dash_mantine_components as dmc
from dash_extensions import Keyboard
from astropy.coordinates import Angle
import astropy.units as u
import requests
from pydantic import ValidationError
from flask import current_app, request
from werkzeug.exceptions import Unauthorized

from ...auth import get_jwt_from_request
from ..components import (
    title_card,
    expressive_card,
    format_cone_search_results,
    build_cone_result_cards_page,
    create_message_banner,
)
from ...dto import ConeSearchResponseModel

dash.register_page(
    __name__,
    path="/cone",
    title="TarXiv - Cone Search",
    name="Cone Search",
    order=2,
    icon="lucide:cone",
)


# A cone search is fully described by three numbers, so the query string is the
# page's source of truth: pressing Search writes ?ra=&dec=&radius= to the
# page-local Location, and that write is what actually runs the search. All
# three input options normalise to decimal degrees first, so every search — no
# matter which box it was typed into — produces the same shareable URL.
CONE_QUERY_KEYS = ("ra", "dec", "radius")


def build_cone_query_string(ra: float, dec: float, radius: float) -> str:
    """Build the '?ra=...&dec=...&radius=...' search string for a cone search."""
    return "?" + urlencode({
        "ra": f"{float(ra):.6f}",
        "dec": f"{float(dec):.6f}",
        "radius": f"{float(radius):g}",
    })


def parse_cone_query_params(params: dict) -> tuple[float, float, float] | None:
    """Parse cone-search query parameters into (ra, dec, radius).

    Args:
        params: Flattened query parameters, i.e. ``{key: str}``. Dash pages
            hands ``layout()`` exactly this shape; callbacks reading a raw
            search string should use :func:`parse_cone_search_string`.

    Returns
    -------
        ``(ra_deg, dec_deg, radius_arcsec)``, or ``None`` when none of the
        three parameters are present.

    Raises
    ------
        ValueError: with a user-facing message when the parameters are present
        but incomplete, non-numeric, or outside the bounds accepted by the
        search form.
    """
    present = {key: params.get(key) for key in CONE_QUERY_KEYS}
    if all(value is None or str(value).strip() == "" for value in present.values()):
        return None

    missing = [
        key
        for key, value in present.items()
        if value is None or str(value).strip() == ""
    ]
    if missing:
        raise ValueError(
            f"Incomplete cone search link: missing {', '.join(missing)}. "
            "A link needs ra, dec and radius."
        )

    try:
        ra = float(cast(str, present["ra"]))
        dec = float(cast(str, present["dec"]))
        radius = float(cast(str, present["radius"]))
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Could not read the coordinates from the link. ra, dec and radius "
            "must all be numbers, e.g. /cone?ra=315.403750&dec=68.163333&radius=30."
        ) from exc

    if not 0 <= ra <= 360:
        raise ValueError(f"RA must be between 0 and 360 degrees (got {ra}).")
    if not -90 <= dec <= 90:
        raise ValueError(f"Dec must be between -90 and 90 degrees (got {dec}).")
    if radius <= 0:
        raise ValueError(f"Radius must be greater than zero (got {radius}).")

    return ra, dec, radius


def parse_cone_search_string(search: str) -> tuple[float, float, float] | None:
    """Parse a raw '?ra=...&dec=...' Location search string into coordinates."""
    if not search:
        return None
    parsed = parse_qs(search.lstrip("?"))
    return parse_cone_query_params({key: values[0] for key, values in parsed.items()})


# Initialise the Aladin Lite widget for the cone-search results: centre on the
# search position, draw the search radius as a subtle ring, drop a marker per
# result, and hook up hover-linking from result cards to marker highlights.
#
# The JS body lives in assets/cone_aladin.js as window.dash_clientside.cone_aladin
# rather than an inline-string callback — inline strings under Dash 4 can fail
# to register with `dc[namespace][function_name] is undefined`, and the asset
# file is easier to debug in the browser too.
clientside_callback(
    ClientsideFunction(namespace="cone_aladin", function_name="initialize"),
    Output("cone-aladin-status", "children"),
    Input("cone-search-store", "data"),
)


# Re-render the cone-search results list when the user changes the pagination
# page. The Aladin widget is unaffected — it always shows every marker.
@callback(
    Output("cone-results-list", "children"),
    Input("cone-results-pagination", "value"),
    State("cone-search-store", "data"),
    prevent_initial_call=True,
)
def update_cone_results_page(page, store_data):
    if not page or not store_data or not store_data.get("results"):
        return no_update
    return build_cone_result_cards_page(store_data["results"], page)


def layout(ra=None, dec=None, radius=None, **kwargs):
    """Build the cone-search page, running the search when the URL carries one.

    A pasted or bookmarked ``/cone?ra=&dec=&radius=`` link is a cold page load,
    so the search has to happen here rather than in the URL callback — Dash
    forbids ``allow_duplicate`` outputs on a callback that fires on initial
    call, and the banner/settings stores are shared with other callbacks. This
    mirrors ``pages/lightcurve.py``, which runs its search in ``layout()`` for
    the same reason. In-session searches go through ``run_cone_search`` below;
    both paths call :func:`render_cone_search`, so the logic lives in one place.
    """
    logger = current_app.config["TXV_LOGGER"]

    results, status, banner, store_data = html.Div(), "", [], None

    try:
        coordinates = parse_cone_query_params({
            "ra": ra,
            "dec": dec,
            "radius": radius,
        })
    except ValueError as exc:
        coordinates = None
        banner = create_message_banner(str(exc), "warning")

    if coordinates:
        ra, dec, radius = coordinates
        token = get_jwt_from_request(request)
        results, status, banner, store_data = render_cone_search(
            ra, dec, radius, token, logger
        )
    else:
        # Nothing usable in the URL: leave the inputs empty as before.
        ra, dec, radius = None, None, None

    return dmc.Stack(
        children=[
            dcc.Store(id="cone-search-store", data=store_data),
            # Page-local, refresh=False: writing to this pushes history without
            # reloading the page. The app-wide "url" and "auth-location"
            # Locations are both refresh=True and would force a full reload.
            dcc.Location(id="cone-url", refresh=False),
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="Cone Search",
                children=[
                    dmc.Stack([
                        dmc.Text(
                            "Search for objects within a specified radius of sky coordinates",
                        ),
                        dmc.Text(
                            "Option 1: Enter RA (degrees), Dec (degrees) and radius (arcsec)"
                        ),
                        dmc.Group([
                            Keyboard(
                                children=dmc.Group([
                                    dmc.NumberInput(
                                        id="ra-input",
                                        placeholder="0-360",
                                        value=ra,
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
                                        value=dec,
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
                                        value=radius,
                                        min=0,
                                        label="Radius (arcsec):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                ]),
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
                        ]),
                        dmc.Divider(label="OR", labelPosition="center"),
                        dmc.Text(
                            "Option 2: Enter RA (HMS), Dec (DMS) and radius (arcsec)"
                        ),
                        dmc.Group([
                            Keyboard(
                                children=dmc.Group([
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
                                ]),
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
                        ]),
                        dmc.Divider(label="OR", labelPosition="center"),
                        dmc.Text(
                            "Option 3: Enter a single RA/Dec string "
                            "(space-separated h:m:s and d:m:s) and radius (arcsec)"
                        ),
                        dmc.Group([
                            Keyboard(
                                children=dmc.Group([
                                    dmc.TextInput(
                                        id="radec-combined-input",
                                        placeholder="21:01:36.90 +68:09:48.0",
                                        label="RA/Dec (HMS DMS):",
                                        style={
                                            "width": "310px",
                                        },
                                    ),
                                    dmc.NumberInput(
                                        id="radius-combined-input",
                                        placeholder=">0",
                                        min=0,
                                        label="Radius (arcsec):",
                                        style={
                                            "width": "150px",
                                        },
                                    ),
                                ]),
                                captureKeys=["Enter"],
                                n_keydowns=0,
                                id="cone-search-combined-keyboard",
                            ),
                            dmc.Button(
                                "Search",
                                id="cone-search-combined-button",
                                n_clicks=0,
                                style={"marginTop": "21px"},
                            ),
                        ]),
                    ]),
                ],
            ),
            dmc.Box(
                id="message-banner",
                children=banner,
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
                        children=results,
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


def parse_combined_coordinates(combined: str) -> tuple[float, float]:
    """Parse a single combined 'RA Dec' string into degrees.

    Accepts space-separated sexagesimal coordinates where RA is in h:m:s and
    Dec in d:m:s, e.g. '21:01:36.90 +68:09:48.0'. A comma between the two parts
    is also tolerated ('21:01:36.90, +68:09:48.0'). The RA and Dec components
    must use colon separators internally so the pair splits cleanly on the space.
    """
    if not combined or not combined.strip():
        raise ValueError("Please provide a combined RA/Dec coordinate string.")

    tokens = combined.replace(",", " ").split()
    if len(tokens) != 2:
        raise ValueError(
            "Could not parse the combined coordinates. Use colon-separated "
            "sexagesimal values separated by a space, e.g. "
            "'21:01:36.90 +68:09:48.0'."
        )

    ra_hms, dec_dms = tokens
    return parse_hms_dms_coordinates(ra_hms, dec_dms)


def render_cone_search(ra, dec, radius, token, logger):
    """Run a cone search and build everything the page needs to show it.

    Returns
    -------
        ``(results_children, status_text, banner, store_data)``. ``store_data``
        is None when the search failed, so the caller can leave the existing
        store untouched.
    """
    status_msg = f"Cone search: RA={ra}, Dec={dec}, radius={radius} arcsec"
    logger.info({
        "search_type": "cone",
        "ra": ra,
        "dec": dec,
        "radius": radius,
    })

    try:
        results = get_cone_search_results(ra, dec, radius, token, logger)

        result = format_cone_search_results(results, ra, dec)
        success_banner = create_message_banner(
            f"Found {len(results)} object(s) in search region", "success"
        )
        logger.info({"info": f"Cone search found {len(results)} objects."})

        store_data = {
            "results": results,
            "ra": ra,
            "dec": dec,
            "radius": radius,
        }

        return result, status_msg, success_banner, store_data
    except Unauthorized as e:
        logger.warning({"warning": f"Unauthorized cone search attempt: {str(e)}"})
        error_banner = create_message_banner(
            "Unauthorized: Invalid API token. Check your token.", "error"
        )
        return html.Div(), "Unauthorized", error_banner, None
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        logger.error({"error": error_msg})
        error_banner = create_message_banner(error_msg, "error")
        return html.Div(), "Error occurred", error_banner, None


@callback(
    [
        Output("cone-url", "search", allow_duplicate=True),
        Output("message-banner", "children", allow_duplicate=True),
    ],
    [
        Input("cone-search-button", "n_clicks"),
        Input("cone-search-keyboard", "n_keydowns"),
        Input("cone-search-hmsdms-button", "n_clicks"),
        Input("cone-search-hmsdms-keyboard", "n_keydowns"),
        Input("cone-search-combined-button", "n_clicks"),
        Input("cone-search-combined-keyboard", "n_keydowns"),
    ],
    [
        State("ra-input", "value"),
        State("dec-input", "value"),
        State("radius-input", "value"),
        State("ra-hms-input", "value"),
        State("dec-dms-input", "value"),
        State("radius-hmsdms-input", "value"),
        State("radec-combined-input", "value"),
        State("radius-combined-input", "value"),
    ],
    prevent_initial_call=True,
)
def submit_cone_search(
    n_clicks,
    n_keydowns,
    n_hmsdms_clicks,
    n_hmsdms_keydowns,
    n_combined_clicks,
    n_combined_keydowns,
    ra,
    dec,
    radius,
    ra_hms,
    dec_dms,
    radius_hmsdms,
    radec_combined,
    radius_combined,
):
    """Validate the search form and push the coordinates into the URL.

    This does not run the search itself: it normalises whichever input option
    was used down to decimal degrees and writes the resulting query string to
    the page-local Location, which is what triggers `run_cone_search`. Doing it
    this way means a search performed in the browser and a search arriving via
    a pasted link travel exactly the same path.
    """
    trigger_id = ctx.triggered_id
    use_hmsdms_input = trigger_id in {
        "cone-search-hmsdms-button",
        "cone-search-hmsdms-keyboard",
    }
    use_combined_input = trigger_id in {
        "cone-search-combined-button",
        "cone-search-combined-keyboard",
    }

    if use_combined_input:
        if not radec_combined or not str(radec_combined).strip():
            warning_banner = create_message_banner(
                "Please provide a combined RA/Dec coordinate string.", "warning"
            )
            return no_update, warning_banner
        if radius_combined is None or radius_combined <= 0:
            warning_banner = create_message_banner(
                "Please provide a radius greater than zero.", "warning"
            )
            return no_update, warning_banner

        try:
            ra, dec = parse_combined_coordinates(radec_combined)
        except ValueError as exc:
            warning_banner = create_message_banner(str(exc), "warning")
            return no_update, warning_banner

        radius = float(radius_combined)
    elif use_hmsdms_input:
        if (
            not ra_hms
            or not str(ra_hms).strip()
            or not dec_dms
            or not str(dec_dms).strip()
        ):
            warning_banner = create_message_banner(
                "Please provide both RA (HMS) and Dec (DMS) coordinates.", "warning"
            )
            return no_update, warning_banner
        if radius_hmsdms is None or radius_hmsdms <= 0:
            warning_banner = create_message_banner(
                "Please provide a radius greater than zero.", "warning"
            )
            return no_update, warning_banner

        try:
            ra, dec = parse_hms_dms_coordinates(ra_hms, dec_dms)
        except ValueError as exc:
            warning_banner = create_message_banner(str(exc), "warning")
            return no_update, warning_banner

        radius = float(radius_hmsdms)
    else:
        if ra is None or dec is None or radius is None:
            warning_banner = create_message_banner(
                "Please provide valid RA, Dec and radius coordinates.", "warning"
            )
            return no_update, warning_banner
        if radius <= 0:
            warning_banner = create_message_banner(
                "Please provide a radius greater than zero.", "warning"
            )
            return no_update, warning_banner

    return build_cone_query_string(ra, dec, radius), []


@callback(
    [
        Output("results-container", "children", allow_duplicate=True),
        Output("search-status", "children", allow_duplicate=True),
        Output("message-banner", "children", allow_duplicate=True),
        Output("cone-search-store", "data", allow_duplicate=True),
        Output("active-settings-store", "data", allow_duplicate=True),
    ],
    Input("cone-url", "search"),
    State("active-settings-store", "data"),
    prevent_initial_call=True,
)
def run_cone_search(search, settings):
    """Run the cone search described by the current query string.

    Fires when `submit_cone_search` writes a new query string, and when the
    user walks the history with the browser's back/forward buttons. Cold loads
    are handled by `layout()` instead — see its docstring.
    """
    logger = current_app.config["TXV_LOGGER"]

    try:
        coordinates = parse_cone_search_string(search)
    except ValueError as exc:
        warning_banner = create_message_banner(str(exc), "warning")
        return html.Div(), "", warning_banner, no_update, no_update

    if not coordinates:
        return no_update, no_update, no_update, no_update, no_update

    ra, dec, radius = coordinates

    token = get_jwt_from_request(request)

    if not isinstance(settings, dict):
        settings = {}

    settings.update({"tarxiv_user_token": token})  # Save token to active settings

    results, status_msg, banner, store_data = render_cone_search(
        ra, dec, radius, token, logger
    )

    return (
        results,
        status_msg,
        banner,
        store_data if store_data is not None else no_update,
        settings,
    )


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
    logger.debug({"debug": f"Cone search raw response: {response_cone.text}"})

    if response_cone.status_code == 200:
        try:
            data = ConeSearchResponseModel.validate_json(response_cone.text)
            results = ConeSearchResponseModel.dump_python(data)

            logger.debug({
                "debug": f"Cone search results for RA={ra}, Dec={dec}, "
                f"radius={radius} arcsec: {len(results)} objects found"
            })
        except ValidationError as e:
            logger.error({"error": f"Failed to parse cone search results: {str(e)}"})
    elif response_cone.status_code == 401:
        logger.warning({
            "warning": "Unauthorized cone search attempt. Check API token validity."
        })
        raise Unauthorized("Invalid API token. Check your token.")
    else:
        logger.error({
            "error": f"Cone search request failed: Status {response_cone.status_code}"
        })

    return results
