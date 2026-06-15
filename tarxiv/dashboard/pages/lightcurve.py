import dash
from dash import html, callback, no_update, dcc, clientside_callback
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
from ...dto import (
    LightcurveResponseModel,
)
from ..schemas import (
    MetadataResponseModel,
)
from ...auth import (
    get_authenticated_user,
    get_jwt_from_request,
    validate_token,
    TokenStatus,
)
import requests
from pydantic import ValidationError
import os

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

    token = get_jwt_from_request(request)
    user = get_authenticated_user(jwt_token=token)

    if id and user:
        # User came via deep link and has a saved session
        (
            results_top,
            citations_card,
            full_metadata,
            status,
            banner,
            lc_store,
            aladin_store,
        ) = perform_search(id, token, logger)
    elif id and not user:
        validation = validate_token(token)

        # Deep link but no token: Show the search bar pre-filled with ID
        # but warn the user that a token is missing.
        results_top, citations_card, full_metadata = (
            html.Div(),
            html.Div(),
            html.Div(),
        )
        status = "Authentication required"

        if validation["status"] == TokenStatus.EXPIRED:
            banner = create_message_banner(
                "Your session has expired. Please log in again.", "warning"
            )
        elif validation["status"] == TokenStatus.INVALID and token:
            banner = create_message_banner(
                "Invalid authentication token. Please log in again.", "error"
            )
        else:
            banner = create_message_banner("Please log in to view data.", "warning")

        lc_store = None
        aladin_store = None
    else:
        # Default empty search page
        results_top, citations_card, full_metadata, status, banner = (
            html.Div(),
            html.Div(),
            html.Div(),
            "",
            html.Div(),
        )
        lc_store = None
        aladin_store = None

    return dmc.Stack(
        children=[
            # NOTE JL: Switched to memory storage since we want the data to be cleared when the user leaves the page.
            dcc.Store(id="lightcurve-store", storage_type="memory", data=lc_store),
            dcc.Store(id="lightcurve-tags-store", storage_type="memory", data=[]),
            dcc.Store(
                id="lightcurve-object-tags-store", storage_type="memory", data=[]
            ),
            dcc.Store(
                id="lightcurve-aladin-store",
                storage_type="memory",
                data=aladin_store,
            ),
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
                        children=[results_top],
                    ),
                    # Citations sits half-half with the object tagging panel. The
                    # tagging container lives here in the base layout (not inside
                    # the search results) so its callbacks always have a target,
                    # even on the empty page.
                    dmc.Grid(
                        [
                            dmc.GridCol(citations_card, span=6),
                            dmc.GridCol(
                                html.Div(id="object-tagging-container"), span=6
                            ),
                        ],
                        gutter="md",
                    ),
                    # Full metadata JSON dump pinned to the very bottom.
                    full_metadata,
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


clientside_callback(
    """
    function(storeData) {
    if (!storeData || storeData.ra_deg === null || storeData.dec_deg === null) {
        return "No TNS coordinates available for Aladin";
    }

    const ra = storeData.ra_deg;
    const dec = storeData.dec_deg;

    // log the coordinates for debugging
    console.log("Initializing Aladin with coordinates:", ra, dec);

    // The ID Plotly generates for pattern-matching is complex,
    // so we target the container expressive_card or a stable parent.
    const graphContainer = document.body;

    const observer = new MutationObserver((mutations, obs) => {
        // Look for the Plotly internal class that signifies rendering is done
        const graphExists = document.querySelector('.js-plotly-plot');

        if (graphExists) {
            obs.disconnect(); // Stop watching

            window.A.init.then(() => {
                const container = document.getElementById('aladin-lite-div');
                if (container) {
                    container.innerHTML = '';
                    window.A.aladin('#aladin-lite-div', {
                        survey: 'P/PanSTARRS/DR1/color-z-zg-g',
                        target: ra + ' ' + dec,
                        fov: 0.025,
                    });
                }
            });
        }
    });

    observer.observe(graphContainer, {
        childList: true,
        subtree: true
    });

    return "Observer active";
}
    """,
    Output("aladin-status-dummy", "children"),
    Input("lightcurve-aladin-store", "data"),
)


# Map source-keyed metadata source names to citation .bib file stems.
# New-schema source keys use underscores (e.g. asas_sn) while the bib files
# in aux/citations use hyphens (asas-sn.bib); this bridges the two.
SOURCE_TO_BIB = {
    "tns": "tns",
    "ztf": "ztf",
    "atlas": "atlas",
    "atlas_twb": "atlas_twb",
    "fink": "fink",
    "mangrove": "mangrove",
    "sherlock": "sherlock",
    "asas_sn": "asas-sn",
    "asas-sn": "asas-sn",
    "asas_sn_skypatrol": "asas-sn_skypatrol",
    "asas-sn_skypatrol": "asas-sn_skypatrol",
    "lasair": "lasair",
    "lsst": "lsst",
}


def _extract_object_coordinates(meta):
    """Return (ra, dec) for the Aladin target from source-keyed metadata.

    Prefers TNS decimal coordinates, then any source providing
    ``ra_deg``/``dec_deg``, and finally the top-level HMS/DMS strings (Aladin
    accepts sexagesimal targets too). Returns (None, None) if nothing usable
    is found.
    """
    data_sources = meta.get("data_sources") or {}

    preferred = ["tns"] + [key for key in data_sources if key != "tns"]
    for source in preferred:
        payload = data_sources.get(source) or {}
        ra = payload.get("ra_deg")
        dec = payload.get("dec_deg")
        if ra is not None and dec is not None:
            return ra, dec

    ra = meta.get("ra")
    dec = meta.get("dec")
    if ra and dec:
        return ra, dec

    return None, None


def _build_aladin_store(meta):
    ra, dec = _extract_object_coordinates(meta)
    if ra is None or dec is None:
        return None
    return {
        "source": "tns",
        "ra_deg": ra,
        "dec_deg": dec,
    }


def fetch_api_data(endpoint, object_id, token, logger):
    """Helper to perform API requests."""
    # TODO: Refactor to use a shared API client module instead of hardcoding requests here
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response = requests.post(
        url=f"{api_url}/{endpoint}/{object_id}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response


def api_base_url():
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    return os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")


def fetch_visible_tags(token, logger):
    response = requests.get(
        url=f"{api_base_url()}/tags",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"tags response status: {response.status_code}"})
    return response


def fetch_object_tags(object_id, token, logger):
    response = requests.get(
        url=f"{api_base_url()}/objects/{object_id}/tags",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"object tags response status: {response.status_code}"})
    return response


def assign_object_tag(object_id, tag_id, token, logger):
    response = requests.post(
        url=f"{api_base_url()}/objects/{object_id}/tags",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json={"tag_id": tag_id},
    )
    logger.info({"info": f"assign object tag response status: {response.status_code}"})
    return response


def delete_object_tag(object_id, assignment_id, token, logger):
    response = requests.delete(
        url=f"{api_base_url()}/objects/{object_id}/tags/{assignment_id}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"delete object tag response status: {response.status_code}"})
    return response


def render_tagging_panel(object_id, visible_tags, assigned_tags):
    assigned_tag_ids = {item["tag"]["id"] for item in assigned_tags}
    available_options = [
        {
            "value": tag["id"],
            "label": f"{tag['name']} ({tag['owner_type']})",
        }
        for tag in visible_tags
        if tag["id"] not in assigned_tag_ids
    ]

    assigned_blocks = (
        [
            dmc.Paper(
                withBorder=True,
                p="sm",
                radius="md",
                children=dmc.Group(
                    [
                        dmc.Group(
                            [
                                dmc.Badge(
                                    item["tag"]["name"],
                                    color=(item["tag"].get("color") or "gray").lstrip(
                                        "#"
                                    ),
                                    variant="light",
                                ),
                                dmc.Text(
                                    item["owner_type"].capitalize(),
                                    size="sm",
                                    c="dimmed",
                                ),
                            ],
                            gap="xs",
                        ),
                        dmc.Button(
                            "Remove",
                            id={
                                "type": "remove-object-tag",
                                "assignment_id": item["id"],
                            },
                            n_clicks=0,
                            variant="subtle",
                            color="red",
                        ),
                    ],
                    justify="space-between",
                ),
            )
            for item in assigned_tags
        ]
        if assigned_tags
        else [dmc.Text("No tags assigned to this object.", c="dimmed")]
    )

    return expressive_card(
        title=f"Object Tags: {object_id}",
        children=[
            dmc.Text(
                "Assign any tag available to you, including personal tags and team tags from your memberships.",
                c="dimmed",
            ),
            dmc.Group([
                dmc.Select(
                    id="assign-object-tag-select",
                    placeholder="Choose a tag",
                    data=available_options,
                    value=None,
                    style={"minWidth": "320px"},
                ),
                dmc.Button("Assign tag", id="assign-object-tag-button", n_clicks=0),
            ]),
            html.Div(id="object-tagging-banner"),
            dmc.Stack(id="object-tagging-list", children=assigned_blocks),
        ],
    )


# TEMPORARY: point the object page at the dummy endpoint that serves the new
# source-keyed schema (see api.py:get_object_meta_dummy). Flip to False once the
# real /get_object_meta endpoint emits the new schema.
USE_DUMMY_META_ENDPOINT = True


def get_metadata_data(object_id, token, logger):
    """Fetch metadata for an object."""
    endpoint = "get_object_meta_dummy" if USE_DUMMY_META_ENDPOINT else "get_object_meta"
    response = fetch_api_data(endpoint, object_id, token, logger)

    if response.status_code == 200:
        try:
            data = MetadataResponseModel.model_validate_json(
                response.text, strict=False
            )
            return data.model_dump()
        except ValidationError as e:
            logger.exception(e)
            logger.error({
                "error": f"Failed to parse metadata for object {object_id}: {str(e)}"
            })
    # authentication error
    elif response.status_code == 401:
        logger.warning({
            "warning": f"Unauthorized access when fetching metadata for object {object_id}. "
            f"Check if the token is valid."
        })
        raise Unauthorized("Invalid API token. Check your token.")

    logger.error({
        "error": f"Metadata request failed for object {object_id}: "
        f"Status {response.status_code}"
    })
    return None


def get_citations_data(sources, token, logger):
    """Fetch concatenated BibTeX citations for a list of metadata source keys.

    The ``/citations`` endpoint takes a JSON body of bib-file stems and returns
    ``{"citations": "<concatenated bibtex>"}``. Source keys with no matching
    .bib file are skipped. Returns the citation string, or None on failure /
    when no sources resolve to a citation.
    """
    bib_names = []
    unmapped = []
    for source in sources or []:
        bib = SOURCE_TO_BIB.get(source)
        if bib:
            if bib not in bib_names:
                bib_names.append(bib)
        else:
            unmapped.append(source)
    if unmapped:
        logger.warning({"warning": f"No citation .bib mapping for sources: {unmapped}"})
    logger.info({"info": f"Citations: requesting bib files for {bib_names}"})
    if not bib_names:
        return None

    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    try:
        response = requests.post(
            url=f"{api_url}/citations",
            json={"sources": bib_names},
            timeout=10,
            headers={
                "accept": "application/json",
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
    except requests.RequestException as e:
        logger.error({"error": f"Citations request failed: {str(e)}"})
        return None

    logger.info({"info": f"citations response status: {response.status_code}"})
    if response.status_code == 200:
        try:
            citation_str = response.json().get("citations")
        except ValueError as e:
            logger.error({"error": f"Failed to parse citations response: {str(e)}"})
            return None
        logger.info({
            "info": f"Citations: received {len(citation_str or '')} chars from API"
        })
        return citation_str or None

    logger.warning({
        "warning": (
            f"Citations request returned status {response.status_code}: "
            f"{response.text[:200]}"
        )
    })
    return None


def get_lightcurve_data(object_id, token, logger):
    """Fetch lightcurve data for an object."""
    response = fetch_api_data("get_object_lc", object_id, token, logger)
    if response and response.status_code == 200:
        try:
            data = LightcurveResponseModel.validate_json(response.text)
            logger.info({
                "success": f"Parsed lightcurve for object {object_id}: {len(data)} points"
            })
            return LightcurveResponseModel.dump_python(data)
        except ValidationError as e:
            logger.error({
                "error": f"Failed to parse lightcurve for object {object_id}: {str(e)}"
            })
    else:
        if response:
            logger.error({
                "error": f"Lightcurve request failed for object {object_id}: "
                f"Status {response.status_code}"
            })
    return None


def perform_search(object_id, token, logger):
    """The core logic shared by both Button and URL triggers.

    Returns a tuple of
    ``(results_top, citations_card, full_metadata, status, banner, lc_store,
    aladin_store)``. The three render slots correspond to the pieces produced by
    ``format_object_metadata``; ``layout`` drops them into the page so the
    object-tagging container can stay in the always-present base layout.
    """
    # Render slots used by every non-success early return (no object to show).
    empty_render = (html.Div(), html.Div(), html.Div())

    status_msg = f"Searching for object: {object_id}"
    logger.info({"search_type": "id", "object_id": object_id})

    # Fetch Metadata
    try:
        meta = get_metadata_data(object_id, token, logger)
    except Unauthorized as e:
        return (
            *empty_render,
            "Authentication required",
            create_message_banner(str(e), "error"),
            None,
            None,
        )
    except Exception as e:
        logger.error({
            "error": f"Unexpected error fetching metadata for {object_id}: {str(e)}"
        })
        logger.exception(e)
        return (
            *empty_render,
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
        return (*empty_render, status_msg, error_banner, None, None)

    # Fetch Lightcurve
    lc_data = get_lightcurve_data(object_id, token, logger)

    # Fetch citations for the sources present in the metadata.
    citation_str = get_citations_data(
        list((meta.get("data_sources") or {}).keys()), token, logger
    )

    # Display metadata
    results_top, citations_card, full_metadata = format_object_metadata(
        object_id, meta, citation_str, logger
    )
    success_banner = create_message_banner(
        f"Successfully loaded object: {object_id}", "success"
    )
    logger.info({"info": f"Object {object_id} loaded successfully."})

    lc_store = {"data": lc_data, "id": object_id}
    aladin_store = _build_aladin_store(meta)
    if aladin_store is None:
        logger.warning({
            "warning": (
                f"No TNS RA/Dec found for object {object_id}; "
                "Aladin widget will not be initialized."
            )
        })

    return (
        results_top,
        citations_card,
        full_metadata,
        status_msg,
        success_banner,
        lc_store,
        aladin_store,
    )


@callback(
    [
        Output("object-tagging-container", "children"),
        Output("lightcurve-tags-store", "data"),
        Output("lightcurve-object-tags-store", "data"),
    ],
    Input("lightcurve-store", "data"),
    prevent_initial_call=False,
)
def load_object_tagging_panel(lightcurve_store):
    # The tagging container only exists inside the loaded-object results, so when
    # no object is shown (empty page / deep link without auth) we must no_update
    # rather than write to a component that isn't in the layout.
    if not lightcurve_store or not isinstance(lightcurve_store, dict):
        return no_update, no_update, no_update

    object_id = lightcurve_store.get("id")
    if not object_id:
        return no_update, no_update, no_update

    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    validation = validate_token(token)
    if validation["status"] != TokenStatus.VALID:
        return no_update, no_update, no_update

    tags_response = fetch_visible_tags(token, logger)
    object_tags_response = fetch_object_tags(object_id, token, logger)
    if tags_response.status_code != 200 or object_tags_response.status_code != 200:
        return (
            create_message_banner("Could not load tagging controls.", "warning"),
            [],
            [],
        )

    visible_tags = tags_response.json()
    assigned_tags = object_tags_response.json()
    return (
        render_tagging_panel(object_id, visible_tags, assigned_tags),
        visible_tags,
        assigned_tags,
    )


@callback(
    [
        Output("object-tagging-container", "children", allow_duplicate=True),
        Output("lightcurve-object-tags-store", "data", allow_duplicate=True),
        Output("assign-object-tag-select", "value"),
    ],
    Input("assign-object-tag-button", "n_clicks"),
    [
        State("assign-object-tag-select", "value"),
        State("lightcurve-store", "data"),
        State("lightcurve-tags-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_assign_object_tag(n_clicks, tag_id, lightcurve_store, visible_tags):
    if not n_clicks or not lightcurve_store or not tag_id:
        return no_update, no_update, no_update

    object_id = lightcurve_store.get("id")
    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    response = assign_object_tag(object_id, tag_id, token, logger)
    if response.status_code != 201:
        assigned_tags = fetch_object_tags(object_id, token, logger)
        current_assignments = (
            assigned_tags.json() if assigned_tags.status_code == 200 else []
        )
        panel = render_tagging_panel(object_id, visible_tags or [], current_assignments)
        return panel, current_assignments, no_update

    updated_response = fetch_object_tags(object_id, token, logger)
    updated_assignments = (
        updated_response.json() if updated_response.status_code == 200 else []
    )
    panel = render_tagging_panel(object_id, visible_tags or [], updated_assignments)
    return panel, updated_assignments, None


@callback(
    [
        Output("object-tagging-container", "children", allow_duplicate=True),
        Output("lightcurve-object-tags-store", "data", allow_duplicate=True),
    ],
    Input({"type": "remove-object-tag", "assignment_id": dash.ALL}, "n_clicks"),
    [
        State({"type": "remove-object-tag", "assignment_id": dash.ALL}, "id"),
        State("lightcurve-store", "data"),
        State("lightcurve-tags-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_remove_object_tag(n_clicks, button_ids, lightcurve_store, visible_tags):
    if not lightcurve_store or not any(n_clicks or []):
        return no_update, no_update

    triggered = dash.ctx.triggered_id
    if not triggered:
        return no_update, no_update

    object_id = lightcurve_store.get("id")
    assignment_id = triggered.get("assignment_id")
    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    delete_object_tag(object_id, assignment_id, token, logger)

    updated_response = fetch_object_tags(object_id, token, logger)
    updated_assignments = (
        updated_response.json() if updated_response.status_code == 200 else []
    )
    panel = render_tagging_panel(object_id, visible_tags or [], updated_assignments)
    return panel, updated_assignments
