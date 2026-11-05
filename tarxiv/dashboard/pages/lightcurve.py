import dash
from dash import (
    ClientsideFunction,
    html,
    callback,
    no_update,
    dcc,
    clientside_callback,
)
from dash.dependencies import Input, Output, State
from flask import current_app, request
from werkzeug.exceptions import Unauthorized
import dash_mantine_components as dmc
from dash_iconify import DashIconify
from ..components import (
    expressive_card,
    format_object_metadata,
    create_message_banner,
    build_empty_search_state,
    build_photometry_table,
    build_tag_chips,
    scheme_from_template,
    tag_badge,
)
from ...dto import (
    LightcurveResponseModel,
    MetadataResponseModel,
)
from ...auth import (
    get_jwt_from_request,
    validate_token,
    verify_token,
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

    if id:
        # Deep link to an object: searching is public, so no login needed.
        (
            results_top,
            metadata_card,
            citations_card,
            full_metadata,
            status,
            banner,
            lc_store,
            aladin_store,
        ) = perform_search(id, token, logger)
    else:
        # Default empty search page
        results_top = build_empty_search_state()
        metadata_card, citations_card, full_metadata, status, banner = (
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
            dcc.Store(id="lightcurve-comments-store", storage_type="memory", data=[]),
            dcc.Store(id="lightcurve-user-teams-store", storage_type="memory", data=[]),
            dcc.Store(
                id="comment-composer-store",
                storage_type="memory",
                data=NEW_COMMENT_MODE,
            ),
            dcc.Store(
                id="lightcurve-aladin-store",
                storage_type="memory",
                data=aladin_store,
            ),
            dmc.Box(id="message-banner", children=[banner]),
            dmc.Text(
                id="search-status",
                children=status,
                size="xs",
                c="dimmed",
                fs="italic",
            ),
            # Page head, key facts, lightcurve + sky view.
            dmc.Stack(
                id="results-container",
                children=[results_top],
                gap="md",
            ),
            # Per-source metadata pairs with the tagging panel and citations.
            # The tagging container lives here in the base layout (not inside
            # the search results) so its callbacks always have a target, even
            # on the empty page.
            dmc.Grid(
                [
                    dmc.GridCol(metadata_card, span={"base": 12, "lg": 7}),
                    dmc.GridCol(
                        dmc.Stack(
                            [
                                html.Div(id="object-tagging-container"),
                                html.Div(id="object-comments-container"),
                                citations_card,
                            ],
                            gap="md",
                        ),
                        span={"base": 12, "lg": 5},
                    ),
                ],
                gutter="md",
            ),
            # Full metadata JSON dump pinned to the very bottom.
            full_metadata,
        ],
        gap="md",
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


# The Aladin bootstrap lives in assets/lightcurve_aladin.js under an explicit
# clientside namespace, matching assets/cone_aladin.js. Inline callback strings
# are unreliable under Dash 4.
clientside_callback(
    ClientsideFunction(namespace="lightcurve_aladin", function_name="initialize"),
    Output("aladin-status-dummy", "children"),
    Input("lightcurve-aladin-store", "data"),
)


# "Tag" in the page head jumps to the tag card and focuses its select, so the
# card stays the single place tags are managed. See assets/object_page.js.
clientside_callback(
    ClientsideFunction(namespace="object_page", function_name="scrollToTags"),
    Output("tag-scroll-dummy", "children"),
    Input("jump-to-tags", "n_clicks"),
    prevent_initial_call=True,
)


@callback(
    [
        Output("lc-plot-wrap", "style"),
        Output("lc-table-wrap", "style"),
        Output("lc-table-wrap", "children"),
    ],
    [
        Input("lc-view-toggle", "value"),
        Input("active-settings-store", "data"),
    ],
    State("lightcurve-store", "data"),
    prevent_initial_call=True,
)
def toggle_lightcurve_view(view, settings, store):
    """Swap the lightcurve card between the plot and the photometry table.

    Also re-renders the table on a theme change so the band swatches follow the
    colour scheme.
    """
    hidden = {"display": "none"}
    shown = {"display": "block"}

    if view != "Table":
        return shown, hidden, no_update

    scheme = scheme_from_template((settings or {}).get("theme"))
    table = build_photometry_table((store or {}).get("data"), scheme)
    return hidden, shown, table


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

    Prefers the top-level decimal coordinates (``ra_deg``/``dec_deg``), then TNS
    and any other source providing ``ra_deg``/``dec_deg``, and finally the
    top-level sexagesimal strings (Aladin accepts sexagesimal targets too).
    Returns (None, None) if nothing usable is found.
    """
    ra = meta.get("ra_deg")
    dec = meta.get("dec_deg")
    if ra is not None and dec is not None:
        return ra, dec

    data_sources = meta.get("data_sources") or {}
    preferred = ["tns"] + [key for key in data_sources if key != "tns"]
    for source in preferred:
        payload = data_sources.get(source) or {}
        ra = payload.get("ra_deg")
        dec = payload.get("dec_deg")
        if ra is not None and dec is not None:
            return ra, dec

    ra = meta.get("ra_hms") or meta.get("ra")
    dec = meta.get("dec_dms") or meta.get("dec")
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

    # Assigned tags read as a compact wrapping row of chips above the assign
    # controls, rather than a stack of full-width rows.
    if assigned_tags:
        assigned_chips = [
            dmc.Group(
                [
                    tag_badge(item["tag"], size="sm"),
                    dmc.ActionIcon(
                        DashIconify(icon="mdi:close", width=12),
                        id={
                            "type": "remove-object-tag",
                            "assignment_id": item["id"],
                        },
                        n_clicks=0,
                        variant="subtle",
                        color="gray",
                        size="xs",
                        # dmc.ActionIcon 2.6.0 has no `title` prop.
                        **{
                            "aria-label": (
                                f"Remove {item['tag'].get('name', 'tag')} "
                                f"({item['owner_type']})"
                            )
                        },
                    ),
                ],
                gap=2,
                wrap="nowrap",
                align="center",
            )
            for item in assigned_tags
        ]
    else:
        assigned_chips = [
            dmc.Text("No tags assigned to this object.", size="xs", c="dimmed")
        ]

    return expressive_card(
        id="object-tag-card",
        title="Tags",
        icon="mdi:tag-outline",
        children=[
            dmc.Group(id="object-tagging-list", children=assigned_chips, gap="xs"),
            html.Div(id="object-tagging-banner"),
            dmc.Group(
                [
                    dmc.Select(
                        id="assign-object-tag-select",
                        placeholder="Choose a tag",
                        data=available_options,
                        value=None,
                        size="xs",
                        searchable=True,
                        style={"flex": 1, "minWidth": 0},
                    ),
                    dmc.Button(
                        "Assign",
                        id="assign-object-tag-button",
                        n_clicks=0,
                        size="xs",
                        variant="default",
                    ),
                ],
                gap="xs",
                wrap="nowrap",
            ),
        ],
    )


def get_metadata_data(object_id, token, logger):
    """Fetch metadata for an object."""
    response = fetch_api_data("get_object_meta", object_id, token, logger)

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
    ``(results_top, metadata_card, citations_card, full_metadata, status,
    banner, lc_store, aladin_store)``. The four render slots correspond to the
    pieces produced by ``format_object_metadata``; ``layout`` drops them into
    the page so the object-tagging container can stay in the always-present
    base layout.
    """
    # Render slots used by every non-success early return: keep the search card
    # on screen (pre-filled) so the user can correct the ID and retry.
    empty_render = (
        build_empty_search_state(prefill=object_id),
        html.Div(),
        html.Div(),
        html.Div(),
    )

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

    tarxiv_id = meta.get("tarxiv_id")
    if not tarxiv_id:
        error_banner = create_message_banner(
            f"Object {object_id} has no associated TarXiv ID.", "error"
        )
        logger.warning({"warning": f"Object {object_id} missing TarXiv ID."})
        return (*empty_render, status_msg, error_banner, None, None)

    # Fetch Lightcurve
    lc_data = get_lightcurve_data(tarxiv_id, token, logger)
    logger.info({"info": f"Lightcurve data fetched for object {object_id}."})
    logger.debug({"debug": f"Lightcurve data: {lc_data}"})

    # Fetch citations for the sources present in the metadata.
    citation_str = get_citations_data(
        list((meta.get("data_sources") or {}).keys()), token, logger
    )

    # Assigned tags, so the head chips are correct on first paint rather than
    # popping in once the tagging callback lands.
    assigned_tags = []
    tags_response = fetch_object_tags(object_id, token, logger)
    if tags_response is not None and tags_response.status_code == 200:
        assigned_tags = tags_response.json()

    # Display metadata
    results_top, metadata_card, citations_card, full_metadata = format_object_metadata(
        object_id,
        meta,
        citation_str,
        lc_data=lc_data,
        assigned_tags=assigned_tags,
        logger=logger,
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
        metadata_card,
        citations_card,
        full_metadata,
        # A successful load needs no announcement -- the page itself is the
        # feedback. Both the status line and the banner slot stay empty.
        "",
        html.Div(),
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
        # Safe to target here (unlike in load_object_tagging_panel): assigning
        # requires a loaded object, so the page head always exists.
        Output("object-tag-chips", "children", allow_duplicate=True),
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
        return no_update, no_update, no_update, no_update

    object_id = lightcurve_store.get("id")
    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    response = assign_object_tag(object_id, tag_id, token, logger)

    updated_response = fetch_object_tags(object_id, token, logger)
    updated_assignments = (
        updated_response.json() if updated_response.status_code == 200 else []
    )
    panel = render_tagging_panel(object_id, visible_tags or [], updated_assignments)
    chips = build_tag_chips(updated_assignments)

    if response.status_code != 201:
        # Surface the failure rather than silently re-rendering an unchanged
        # panel, which used to look like the click did nothing.
        logger.warning({
            "warning": (
                f"Failed to assign tag {tag_id} to {object_id}: "
                f"status {response.status_code}"
            )
        })
        return panel, updated_assignments, no_update, chips

    return panel, updated_assignments, None, chips


@callback(
    [
        Output("object-tagging-container", "children", allow_duplicate=True),
        Output("lightcurve-object-tags-store", "data", allow_duplicate=True),
        Output("object-tag-chips", "children", allow_duplicate=True),
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
        return no_update, no_update, no_update

    triggered = dash.ctx.triggered_id
    if not triggered:
        return no_update, no_update, no_update

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
    return panel, updated_assignments, build_tag_chips(updated_assignments)


# --- Comments ----------------------------------------------------------------
# One card per object: a flat list (replies indented under their parent) and a
# single composer that switches between new / reply / edit modes via
# "comment-composer-store", so there are no per-comment inline forms.

PERSONAL_OWNER = "personal"
NEW_COMMENT_MODE = {"mode": "new"}


def comments_api(method, path, token, logger, json=None):
    response = requests.request(
        method,
        url=f"{api_base_url()}{path}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json=json,
    )
    logger.info({"info": f"{method} {path} response status: {response.status_code}"})
    return response


def _format_timestamp(value):
    return (value or "")[:16].replace("T", " ")


def render_comment(comment, user_id, owned_team_ids):
    deleted = comment["deleted"]
    is_author = comment.get("author_id") == user_id
    can_delete = not deleted and (
        is_author
        or (comment["owner_type"] == "team" and comment["owner_id"] in owned_team_ids)
    )
    if comment.get("author_id") is None:
        author = "deleted user"
    else:
        author = comment.get("author_name") or "unnamed user"
    owner_label = (
        (comment.get("owner_name") or "team")
        if comment["owner_type"] == "team"
        else "Only you"
    )
    edited = not deleted and comment.get("updated_at") != comment.get("created_at")

    def action(name, label):
        return dmc.Button(
            label,
            id={
                "type": "comment-action",
                "action": name,
                "comment_id": comment["id"],
            },
            n_clicks=0,
            size="compact-xs",
            variant="subtle",
            color="gray",
        )

    actions = []
    if comment.get("parent_id") is None:
        actions.append(action("reply", "Reply"))
    if is_author and not deleted:
        actions.append(action("edit", "Edit"))
    if can_delete:
        actions.append(action("delete", "Delete"))

    return dmc.Stack(
        [
            dmc.Group(
                [
                    dmc.Text(author, size="xs", fw=600),
                    dmc.Badge(owner_label, size="xs", variant="light"),
                    dmc.Text(
                        _format_timestamp(comment.get("created_at"))
                        + (" (edited)" if edited else ""),
                        size="xs",
                        c="dimmed",
                    ),
                ],
                gap="xs",
            ),
            # Plain text: dmc.Text escapes it, pre-wrap keeps the line breaks.
            dmc.Text(
                "[deleted]" if deleted else comment["body"],
                size="sm",
                style={"whiteSpace": "pre-wrap", "overflowWrap": "anywhere"},
                # Only pass these when set: c=None reaches Mantine as null and
                # it rejects null colours ("expected string, got object").
                **({"c": "dimmed", "fs": "italic"} if deleted else {}),
            ),
            dmc.Group(actions, gap=0),
        ],
        gap=2,
        pl="lg" if comment.get("parent_id") else 0,
    )


def render_comment_list(comments, user_id, teams):
    if not comments:
        return [dmc.Text("No comments yet.", size="xs", c="dimmed")]
    owned_team_ids = {t["team_id"] for t in teams if t.get("role") == "owner"}
    replies = {}
    for comment in comments:
        if comment.get("parent_id"):
            replies.setdefault(comment["parent_id"], []).append(comment)
    return [
        render_comment(item, user_id, owned_team_ids)
        for comment in comments
        if not comment.get("parent_id")
        for item in [comment, *replies.get(comment["id"], [])]
    ]


def render_comments_panel(comments, user_id, teams):
    owner_options = [{"value": PERSONAL_OWNER, "label": "Only me"}] + [
        {"value": t["team_id"], "label": t.get("team_name") or "team"} for t in teams
    ]
    return expressive_card(
        id="object-comment-card",
        title="Comments",
        icon="mdi:comment-outline",
        children=[
            dmc.Stack(
                id="object-comments-list",
                children=render_comment_list(comments, user_id, teams),
                gap="sm",
            ),
            html.Div(id="comment-banner"),
            dmc.Text(id="comment-composer-label", size="xs", c="dimmed"),
            dmc.Textarea(
                id="comment-body",
                placeholder="Write a comment",
                autosize=True,
                minRows=2,
                # No maxLength: dmc 2.6 Textarea doesn't support it. The API
                # enforces the 5000-char cap and the error shows in the banner.
                size="xs",
            ),
            dmc.Group(
                [
                    dmc.Select(
                        id="comment-owner-select",
                        data=owner_options,
                        value=PERSONAL_OWNER,
                        allowDeselect=False,
                        size="xs",
                        style={"flex": 1, "minWidth": 0},
                        **{"aria-label": "Who can see this comment"},
                    ),
                    dmc.Button(
                        "Cancel",
                        id="comment-cancel",
                        n_clicks=0,
                        size="xs",
                        variant="subtle",
                    ),
                    dmc.Button("Post", id="comment-submit", n_clicks=0, size="xs"),
                ],
                gap="xs",
                wrap="nowrap",
            ),
        ],
    )


def _current_user_id(token):
    if validate_token(token)["status"] != TokenStatus.VALID:
        return None
    return verify_token(token).get("sub")


def _refresh_comments(object_id, token, logger):
    response = comments_api("GET", f"/objects/{object_id}/comments", token, logger)
    return response.json() if response.status_code == 200 else []


# Every composer/list update writes the same seven outputs, in this order.
COMMENT_OUTPUTS = [
    Output("object-comments-list", "children", allow_duplicate=True),
    Output("lightcurve-comments-store", "data", allow_duplicate=True),
    Output("comment-composer-store", "data", allow_duplicate=True),
    Output("comment-body", "value", allow_duplicate=True),
    Output("comment-composer-label", "children", allow_duplicate=True),
    Output("comment-owner-select", "disabled", allow_duplicate=True),
    Output("comment-banner", "children", allow_duplicate=True),
]


def _comment_state(comments, user_id, teams, banner=None):
    """Re-render the list and reset the composer to 'new comment'."""
    return (
        render_comment_list(comments, user_id, teams),
        comments,
        NEW_COMMENT_MODE,
        "",
        "",
        False,
        banner,
    )


def _error_banner(response, fallback):
    try:
        message = response.json().get("error") or fallback
    except ValueError:
        message = fallback
    return create_message_banner(message, "error")


@callback(
    [
        Output("object-comments-container", "children"),
        Output("lightcurve-user-teams-store", "data"),
        Output("lightcurve-comments-store", "data"),
    ],
    Input("lightcurve-store", "data"),
    prevent_initial_call=False,
)
def load_object_comments_panel(lightcurve_store):
    # Same guards as load_object_tagging_panel: nothing to show without an
    # object or a logged-in user.
    if not isinstance(lightcurve_store, dict) or not lightcurve_store.get("id"):
        return no_update, no_update, no_update
    token = get_jwt_from_request(request)
    user_id = _current_user_id(token)
    if user_id is None:
        return no_update, no_update, no_update

    logger = current_app.config["TXV_LOGGER"]
    object_id = lightcurve_store["id"]
    comments_response = comments_api(
        "GET", f"/objects/{object_id}/comments", token, logger
    )
    teams_response = comments_api("GET", "/user/teams", token, logger)
    if comments_response.status_code != 200 or teams_response.status_code != 200:
        return (
            create_message_banner("Could not load comments.", "warning"),
            [],
            [],
        )
    teams = teams_response.json()
    comments = comments_response.json()
    return render_comments_panel(comments, user_id, teams), teams, comments


@callback(
    COMMENT_OUTPUTS,
    Input(
        {"type": "comment-action", "action": dash.ALL, "comment_id": dash.ALL},
        "n_clicks",
    ),
    [
        State("lightcurve-store", "data"),
        State("lightcurve-comments-store", "data"),
        State("lightcurve-user-teams-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_comment_action(n_clicks, lightcurve_store, comments, teams):
    triggered = dash.ctx.triggered_id
    # Re-rendering the list re-fires this with n_clicks=0; ignore that.
    if not triggered or not any(n_clicks or []) or not lightcurve_store:
        return (no_update,) * len(COMMENT_OUTPUTS)

    comment_id = triggered["comment_id"]
    comment = next((c for c in comments or [] if c["id"] == comment_id), None)
    if comment is None:
        return (no_update,) * len(COMMENT_OUTPUTS)

    if triggered["action"] == "reply":
        label = f"Replying to {comment.get('author_name') or 'comment'}"
        return (
            no_update,
            no_update,
            {"mode": "reply", "comment_id": comment_id},
            no_update,
            label,
            True,
            None,
        )
    if triggered["action"] == "edit":
        return (
            no_update,
            no_update,
            {"mode": "edit", "comment_id": comment_id},
            comment["body"],
            "Editing your comment",
            True,
            None,
        )

    token = get_jwt_from_request(request)
    logger = current_app.config["TXV_LOGGER"]
    response = comments_api("DELETE", f"/comments/{comment_id}", token, logger)
    banner = (
        None
        if response.status_code == 200
        else _error_banner(response, "Could not delete the comment.")
    )
    object_id = lightcurve_store["id"]
    return _comment_state(
        _refresh_comments(object_id, token, logger),
        _current_user_id(token),
        teams or [],
        banner,
    )


@callback(
    COMMENT_OUTPUTS,
    Input("comment-submit", "n_clicks"),
    [
        State("comment-body", "value"),
        State("comment-owner-select", "value"),
        State("comment-composer-store", "data"),
        State("lightcurve-store", "data"),
        State("lightcurve-user-teams-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_comment_submit(n_clicks, body, owner, composer, lightcurve_store, teams):
    if not n_clicks or not lightcurve_store or not (body or "").strip():
        return (no_update,) * len(COMMENT_OUTPUTS)

    object_id = lightcurve_store["id"]
    token = get_jwt_from_request(request)
    logger = current_app.config["TXV_LOGGER"]
    composer = composer or NEW_COMMENT_MODE

    if composer["mode"] == "edit":
        response = comments_api(
            "PATCH",
            f"/comments/{composer['comment_id']}",
            token,
            logger,
            {"body": body},
        )
        ok = response.status_code == 200
    else:
        payload = {"body": body}
        if composer["mode"] == "reply":
            payload["parent_id"] = composer["comment_id"]
        elif owner and owner != PERSONAL_OWNER:
            payload["owner_team_id"] = owner
        response = comments_api(
            "POST", f"/objects/{object_id}/comments", token, logger, payload
        )
        ok = response.status_code == 201

    if not ok:
        # Keep the draft and mode so nothing typed is lost.
        return (
            *(no_update,) * (len(COMMENT_OUTPUTS) - 1),
            _error_banner(response, "Could not save the comment."),
        )
    return _comment_state(
        _refresh_comments(object_id, token, logger),
        _current_user_id(token),
        teams or [],
    )


@callback(
    [
        Output("comment-composer-store", "data", allow_duplicate=True),
        Output("comment-body", "value", allow_duplicate=True),
        Output("comment-composer-label", "children", allow_duplicate=True),
        Output("comment-owner-select", "disabled", allow_duplicate=True),
    ],
    Input("comment-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def handle_comment_cancel(n_clicks):
    if not n_clicks:
        return no_update, no_update, no_update, no_update
    return NEW_COMMENT_MODE, "", "", False
