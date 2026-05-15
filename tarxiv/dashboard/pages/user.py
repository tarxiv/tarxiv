import os
from urllib.parse import unquote

import dash
from dash import Input, Output, State, callback, dcc, html, no_update
import dash_mantine_components as dmc
import flask
import requests
from flask import current_app, request

from ...auth import (
    TokenStatus,
    get_authenticated_user,
    get_jwt_from_request,
    validate_token,
)
from ..components.auth import avatar_fallback, avatar_image
from ..components.cards import create_message_banner, expressive_card, title_card
from ..styles import ORCID_BUTTON_STYLE


dash.register_page(
    __name__,
    path="/user",
    title="TarXiv - Account",
    name="Account",
    icon="mdi:user-outline",
)


PROFILE_FIELDS = [
    ("username", "Username"),
    ("forename", "Forename"),
    ("surname", "Surname"),
    ("email", "Email"),
    ("institution", "Institution"),
    ("picture_url", "Profile image URL"),
]


def layout(**kwargs):
    token = unquote(request.cookies.get("tarxiv_token", ""))
    user_profile = None
    team_memberships = []
    discovered_teams = []
    tags = []
    fetch_error = None

    if flask.has_request_context():
        token = get_jwt_from_request(flask.request) or token
        user_profile = get_authenticated_user(jwt_token=token)

        if token and user_profile:
            logger = current_app.config["TXV_LOGGER"]
            user_profile, team_memberships, tags, fetch_error = fetch_user_page_data(
                token, logger
            )

    if user_profile:
        name = (
            user_profile.get("username")
            or user_profile.get("forename")
            or user_profile.get("email")
            or "User"
        )
        email = user_profile.get("email", "")
        avatar_src = user_profile.get("picture_url")
        avatar = avatar_image(avatar_src) if avatar_src else avatar_fallback(name[:1])

        auth_content = dmc.Stack([
            dcc.Store(
                id="user-profile-store", storage_type="memory", data=user_profile
            ),
            dcc.Store(id="user-tags-store", storage_type="memory", data=tags),
            dcc.Store(
                id="user-teams-store", storage_type="memory", data=team_memberships
            ),
            dcc.Store(
                id="user-team-search-results-store",
                storage_type="memory",
                data=discovered_teams,
            ),
            dcc.Store(id="user-profile-editing", storage_type="memory", data=False),
            dcc.Store(id="user-tag-create-open", storage_type="memory", data=False),
            dcc.Store(id="user-team-create-open", storage_type="memory", data=False),
            dmc.Box(id="user-page-banner"),
            dmc.Stack(
                id="user-profile-panel",
                children=render_profile_panel(user_profile, False),
            ),
            dmc.Divider(label="Teams", labelPosition="left", my="sm"),
            dmc.Stack([
                dmc.Text("Your Teams", fw=600),
                html.Div(
                    id="user-teams-panel",
                    children=team_membership_block(team_memberships),
                ),
                dmc.Text("Discover Teams", fw=600, mt="sm"),
                dmc.Text(
                    "Search for teams to join or manage your current memberships.",
                    size="sm",
                    c="dimmed",
                ),
                dmc.Group([
                    dmc.TextInput(
                        id="team-search-input",
                        placeholder="Search teams by name or description",
                        style={"minWidth": "320px"},
                    ),
                    dmc.Button("Search", id="team-search-button", n_clicks=0),
                ]),
                html.Div(
                    id="user-team-search-results-panel",
                    children=team_search_results_block([]),
                ),
                dmc.Text("Create Team", fw=600, mt="sm"),
                dmc.Group([
                    dmc.Button("Create Team", id="add-team-button", n_clicks=0),
                ]),
                html.Div(id="user-team-create-panel"),
            ]),
            dmc.Divider(label="Tags", labelPosition="left", my="sm"),
            dmc.Stack([
                dmc.Text(
                    "Your tags include personal tags and tags owned by teams you belong to.",
                    size="sm",
                    c="dimmed",
                ),
                dmc.Group([
                    dmc.Button("Add Tag", id="add-tag-button", n_clicks=0),
                ]),
                html.Div(id="user-tag-create-panel"),
                html.Div(
                    id="user-tags-panel",
                    children=tag_block(tags),
                ),
            ]),
            (
                dmc.Alert(
                    fetch_error,
                    color="yellow",
                    title="Partial profile load",
                    variant="light",
                )
                if fetch_error
                else None
            ),
            dmc.Group(
                id="auth-user-chip",
                children=[
                    dmc.Group(id="auth-avatar-wrapper", children=avatar),
                    dmc.Stack(
                        [
                            dmc.Text(name, id="auth-user-name", fw=600, size="sm"),
                            dmc.Text(
                                email,
                                id="auth-user-email",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap=0,
                    ),
                    dmc.Button(
                        "Logout",
                        id="auth-logout-button",
                        n_clicks=0,
                        variant="light",
                        color="red",
                    ),
                ],
                justify="space-between",
                mt="md",
            ),
            dmc.Group(
                id="api-token-group",
                children=[
                    dmc.Text("Your API token:", size="sm", fw=500),
                    dmc.Group([
                        dmc.Text(
                            token,
                            size="xs",
                            c="dimmed",
                            id="api-token",
                            truncate=True,
                        )
                    ]),
                ],
            ),
        ])
    else:
        auth_content = dmc.Stack([
            dmc.Text(
                "Sign in with ORCID to see your profile, tags, and teams. "
                "This section will grow as we add permissions and roles."
            ),
            dmc.Group([
                dmc.Button(
                    "Sign in with ORCID",
                    id="auth-orcid-login",
                    n_clicks=0,
                    style=ORCID_BUTTON_STYLE,
                )
            ]),
        ])

    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="ORCID Account",
                children=[auth_content],
            ),
        ]
    )


def render_profile_panel(profile, editing):
    if editing:
        fields = [
            dmc.TextInput(
                id={"type": "user-profile-field", "field": field_name},
                label=label,
                value=profile.get(field_name) or "",
            )
            for field_name, label in PROFILE_FIELDS
        ]
        fields.append(
            dmc.Textarea(
                id="user-profile-bio-input",
                label="Bio",
                value=profile.get("bio") or "",
                minRows=4,
                autosize=True,
            )
        )
        fields.append(
            dmc.Group([
                dmc.Button("Save", id="user-profile-save-button", n_clicks=0),
                dmc.Button(
                    "Cancel",
                    id="user-profile-cancel-button",
                    n_clicks=0,
                    variant="light",
                ),
            ])
        )
        return fields

    lines = [
        line(label, profile.get(field_name)) for field_name, label in PROFILE_FIELDS
    ]
    lines.append(line("Bio", profile.get("bio")))
    lines.append(
        dmc.Group([
            dmc.Button("Edit profile", id="user-profile-edit-button", n_clicks=0),
        ])
    )
    return lines


def render_tag_create_form(team_memberships):
    options = [{"value": "personal", "label": "Personal tag"}] + [
        {
            "value": str(team.get("team_id")),
            "label": team.get("team_name") or f"Team {team.get('team_id')}",
        }
        for team in team_memberships
    ]

    return dmc.Stack(
        [
            dmc.Text("Create a new tag", fw=600),
            dmc.TextInput(
                id="new-tag-name", label="Tag name", placeholder="interesting"
            ),
            dmc.TextInput(
                id="new-tag-description",
                label="Description",
                placeholder="Optional description",
            ),
            dmc.TextInput(
                id="new-tag-color",
                label="Color",
                placeholder="#7c3aed",
            ),
            dmc.Select(
                id="new-tag-owner",
                label="Tag owner",
                data=options,
                value="personal",
                allowDeselect=False,
            ),
            dmc.Group([
                dmc.Button("Create tag", id="create-tag-button", n_clicks=0),
                dmc.Button(
                    "Cancel",
                    id="cancel-tag-button",
                    n_clicks=0,
                    variant="light",
                ),
            ]),
        ],
        gap="sm",
    )


def render_team_create_form():
    return dmc.Stack(
        [
            dmc.Text("Create a new team", fw=600),
            dmc.TextInput(
                id="new-team-name",
                label="Team name",
                placeholder="Transient classifiers",
            ),
            dmc.Textarea(
                id="new-team-description",
                label="Description",
                placeholder="Optional description",
                minRows=3,
                autosize=True,
            ),
            dmc.Group([
                dmc.Button("Create team", id="create-team-button", n_clicks=0),
                dmc.Button(
                    "Cancel",
                    id="cancel-team-button",
                    n_clicks=0,
                    variant="light",
                ),
            ]),
        ],
        gap="sm",
    )


def line(label, value):
    display_value = value or "-"
    return dmc.Group(
        [dmc.Text(f"{label}: ", fw=700), dmc.Text(display_value)], gap="xs"
    )


def team_membership_block(memberships):
    if not memberships:
        return dmc.Text("No team memberships yet.", size="sm", c="dimmed")

    return dmc.Stack(
        [
            dmc.Paper(
                withBorder=True,
                p="sm",
                radius="md",
                children=[
                    dmc.Group(
                        [
                            dmc.Stack(
                                [
                                    dmc.Text(
                                        item.get("team_name")
                                        or f"Team {item.get('team_id')}",
                                        fw=600,
                                    ),
                                    dmc.Text(
                                        item.get("team_description")
                                        or str(item.get("team_id")),
                                        size="sm",
                                        c="dimmed",
                                    ),
                                ],
                                gap=0,
                            ),
                            dmc.Group([
                                dmc.Badge(item.get("role", "member"), variant="light"),
                                dmc.Button(
                                    "Leave",
                                    id={
                                        "type": "leave-team-button",
                                        "team_id": item.get("team_id"),
                                    },
                                    n_clicks=0,
                                    variant="subtle",
                                    color="red",
                                ),
                            ]),
                        ],
                        justify="space-between",
                    )
                ],
            )
            for item in memberships
        ],
        gap="sm",
    )


def tag_block(tags):
    if not tags:
        return dmc.Text("No tags yet.", size="sm", c="dimmed")

    personal_tags = [tag for tag in tags if tag.get("owner_type") == "user"]
    team_tags = [tag for tag in tags if tag.get("owner_type") == "team"]

    sections = []
    if personal_tags:
        sections.append(tag_section("Personal tags", personal_tags))
    if team_tags:
        sections.append(tag_section("Team tags", team_tags))

    return dmc.Stack(sections, gap="sm")


def team_search_results_block(teams):
    if not teams:
        return dmc.Text("No team search results yet.", size="sm", c="dimmed")

    return dmc.Stack(
        [
            dmc.Paper(
                withBorder=True,
                p="sm",
                radius="md",
                children=dmc.Group(
                    [
                        dmc.Stack(
                            [
                                dmc.Text(team.get("name") or "Unnamed team", fw=600),
                                dmc.Text(
                                    team.get("description") or "No description",
                                    size="sm",
                                    c="dimmed",
                                ),
                            ],
                            gap=0,
                        ),
                        dmc.Group([
                            dmc.Badge(
                                "Member" if team.get("is_member") else "Not a member",
                                variant="light",
                            ),
                            dmc.Button(
                                "Leave" if team.get("is_member") else "Join",
                                id={
                                    "type": "team-membership-action",
                                    "team_id": team.get("id"),
                                    "action": "leave"
                                    if team.get("is_member")
                                    else "join",
                                },
                                n_clicks=0,
                                variant="light",
                            ),
                        ]),
                    ],
                    justify="space-between",
                ),
            )
            for team in teams
        ],
        gap="sm",
    )


def tag_section(title, tags):
    return dmc.Stack(
        [
            dmc.Text(title, fw=600),
            dmc.Stack(
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
                                            tag.get("name", "Unnamed"),
                                            color=(tag.get("color") or "gray").lstrip(
                                                "#"
                                            ),
                                            variant="light",
                                        ),
                                        dmc.Text(
                                            tag.get("description") or "No description",
                                            size="sm",
                                            c="dimmed",
                                        ),
                                    ],
                                    gap="xs",
                                ),
                                dmc.Text(
                                    tag.get("owner_type", "user").capitalize(),
                                    size="sm",
                                    c="dimmed",
                                ),
                            ],
                            justify="space-between",
                        ),
                    )
                    for tag in tags
                ],
                gap="xs",
            ),
        ],
        gap="xs",
    )


def fetch_user_page_data(token: str, logger):
    profile_response = fetch_api_data("user", token, logger)
    teams_response = fetch_api_data("user/teams", token, logger)
    tags_response = fetch_api_data("tags", token, logger)

    if profile_response.status_code == 401:
        return None, [], [], "Session expired. Please log in again."

    profile = None
    memberships = []
    tags = []
    errors = []

    if profile_response.status_code == 200:
        profile = profile_response.json()
    else:
        errors.append(
            f"Profile request failed with status {profile_response.status_code}."
        )

    if teams_response.status_code == 200:
        memberships = teams_response.json()
    else:
        errors.append(
            f"Team membership request failed with status {teams_response.status_code}."
        )

    if tags_response.status_code == 200:
        tags = tags_response.json()
    else:
        errors.append(f"Tags request failed with status {tags_response.status_code}.")

    return profile, memberships, tags, " ".join(errors) if errors else None


def fetch_api_data(endpoint: str, token: str, logger):
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response = requests.get(
        url=f"{api_url}/{endpoint}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response


def delete_api_data(endpoint: str, token: str, logger):
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response = requests.delete(
        url=f"{api_url}/{endpoint}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response


def patch_api_data(endpoint: str, token: str, payload: dict, logger):
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response = requests.patch(
        url=f"{api_url}/{endpoint}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response


def post_api_data(endpoint: str, token: str, payload: dict, logger):
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    response = requests.post(
        url=f"{api_url}/{endpoint}",
        timeout=10,
        headers={
            "accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        },
        json=payload,
    )
    logger.info({"info": f"{endpoint} response status: {response.status_code}"})
    return response


@callback(
    [
        Output("user-profile-panel", "children"),
        Output("user-profile-editing", "data"),
        Output("user-page-banner", "children", allow_duplicate=True),
    ],
    Input("user-profile-edit-button", "n_clicks"),
    State("user-profile-store", "data"),
    prevent_initial_call=True,
)
def start_profile_edit(n_clicks, profile):
    if not n_clicks:
        return no_update, no_update, no_update

    return render_profile_panel(profile or {}, True), True, html.Div()


@callback(
    [
        Output("user-profile-panel", "children", allow_duplicate=True),
        Output("user-profile-editing", "data", allow_duplicate=True),
        Output("user-page-banner", "children", allow_duplicate=True),
    ],
    Input("user-profile-cancel-button", "n_clicks"),
    State("user-profile-store", "data"),
    prevent_initial_call=True,
)
def cancel_profile_edit(n_clicks, profile):
    if not n_clicks:
        return no_update, no_update, no_update

    return render_profile_panel(profile or {}, False), False, html.Div()


@callback(
    [
        Output("user-profile-panel", "children", allow_duplicate=True),
        Output("user-profile-store", "data", allow_duplicate=True),
        Output("user-profile-editing", "data", allow_duplicate=True),
        Output("user-page-banner", "children", allow_duplicate=True),
    ],
    Input("user-profile-save-button", "n_clicks"),
    [
        State({"type": "user-profile-field", "field": "username"}, "value"),
        State({"type": "user-profile-field", "field": "forename"}, "value"),
        State({"type": "user-profile-field", "field": "surname"}, "value"),
        State({"type": "user-profile-field", "field": "email"}, "value"),
        State({"type": "user-profile-field", "field": "institution"}, "value"),
        State({"type": "user-profile-field", "field": "picture_url"}, "value"),
        State("user-profile-bio-input", "value"),
    ],
    prevent_initial_call=True,
)
def save_profile(
    n_clicks,
    username,
    forename,
    surname,
    email,
    institution,
    picture_url,
    bio,
):
    if not n_clicks:
        return no_update, no_update, no_update, no_update

    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    validation = validate_token(token)
    if validation["status"] != TokenStatus.VALID:
        return (
            no_update,
            no_update,
            no_update,
            create_message_banner(
                "Please log in again before saving changes.", "warning"
            ),
        )

    payload = {
        "username": username or None,
        "forename": forename or None,
        "surname": surname or None,
        "email": email or None,
        "institution": institution or None,
        "picture_url": picture_url or None,
        "bio": bio or None,
    }
    response = patch_api_data("user", token, payload, logger)

    if response.status_code != 200:
        error_message = "Could not save your profile right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return (
            no_update,
            no_update,
            no_update,
            create_message_banner(error_message, "error"),
        )

    updated_profile = response.json()
    return (
        render_profile_panel(updated_profile, False),
        updated_profile,
        False,
        create_message_banner("Profile updated.", "success"),
    )


@callback(
    [
        Output("user-team-search-results-panel", "children"),
        Output("user-team-search-results-store", "data"),
        Output("user-page-banner", "children", allow_duplicate=True),
    ],
    Input("team-search-button", "n_clicks"),
    State("team-search-input", "value"),
    prevent_initial_call=True,
)
def search_teams(n_clicks, query):
    if not n_clicks:
        return no_update, no_update, no_update

    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    normalized_query = (query or "").strip()
    if not normalized_query:
        return (
            team_search_results_block([]),
            [],
            create_message_banner("Enter a team search query.", "warning"),
        )

    response = fetch_api_data(f"teams/search?q={normalized_query}", token, logger)
    if response.status_code != 200:
        error_message = "Could not search teams right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return no_update, no_update, create_message_banner(error_message, "error")

    teams = response.json()
    return team_search_results_block(teams), teams, html.Div()


@callback(
    [
        Output("user-tag-create-panel", "children"),
        Output("user-tag-create-open", "data"),
    ],
    Input("add-tag-button", "n_clicks"),
    State("user-teams-store", "data"),
    prevent_initial_call=True,
)
def open_tag_create_form(n_clicks, team_memberships):
    if not n_clicks:
        return no_update, no_update

    return render_tag_create_form(team_memberships or []), True


@callback(
    [
        Output("user-tag-create-panel", "children", allow_duplicate=True),
        Output("user-tag-create-open", "data", allow_duplicate=True),
    ],
    Input("cancel-tag-button", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_tag_create_form(n_clicks):
    if not n_clicks:
        return no_update, no_update

    return html.Div(), False


@callback(
    [
        Output("user-team-create-panel", "children"),
        Output("user-team-create-open", "data"),
    ],
    Input("add-team-button", "n_clicks"),
    prevent_initial_call=True,
)
def open_team_create_form(n_clicks):
    if not n_clicks:
        return no_update, no_update

    return render_team_create_form(), True


@callback(
    [
        Output("user-team-create-panel", "children", allow_duplicate=True),
        Output("user-team-create-open", "data", allow_duplicate=True),
    ],
    Input("cancel-team-button", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_team_create_form(n_clicks):
    if not n_clicks:
        return no_update, no_update

    return html.Div(), False


@callback(
    [
        Output("user-teams-panel", "children"),
        Output("user-teams-store", "data"),
        Output("user-page-banner", "children", allow_duplicate=True),
        Output("new-team-name", "value"),
        Output("new-team-description", "value"),
        Output("user-team-create-panel", "children", allow_duplicate=True),
        Output("user-team-create-open", "data", allow_duplicate=True),
        Output("user-tag-create-panel", "children", allow_duplicate=True),
    ],
    Input("create-team-button", "n_clicks"),
    [
        State("new-team-name", "value"),
        State("new-team-description", "value"),
        State("user-tag-create-open", "data"),
        State("user-tag-create-panel", "children"),
    ],
    prevent_initial_call=True,
)
def create_team(n_clicks, name, description, tag_form_open, tag_form_children):
    if not n_clicks:
        return (
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    if not name or not str(name).strip():
        return (
            no_update,
            no_update,
            create_message_banner("Team name is required.", "warning"),
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    response = post_api_data(
        "teams",
        token,
        {"name": str(name).strip(), "description": description or None},
        logger,
    )
    if response.status_code != 201:
        error_message = "Could not create team right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return (
            no_update,
            no_update,
            create_message_banner(error_message, "error"),
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    updated_teams_response = fetch_api_data("user/teams", token, logger)
    updated_teams = []
    if updated_teams_response.status_code == 200:
        updated_teams = updated_teams_response.json()

    refreshed_tag_panel = tag_form_children
    if tag_form_open:
        refreshed_tag_panel = render_tag_create_form(updated_teams)

    return (
        team_membership_block(updated_teams),
        updated_teams,
        create_message_banner("Team created.", "success"),
        "",
        "",
        html.Div(),
        False,
        refreshed_tag_panel,
    )


@callback(
    [
        Output("user-teams-panel", "children", allow_duplicate=True),
        Output("user-teams-store", "data", allow_duplicate=True),
        Output("user-team-search-results-panel", "children", allow_duplicate=True),
        Output("user-team-search-results-store", "data", allow_duplicate=True),
        Output("user-page-banner", "children", allow_duplicate=True),
    ],
    Input(
        {"type": "team-membership-action", "team_id": dash.ALL, "action": dash.ALL},
        "n_clicks",
    ),
    [
        State(
            {"type": "team-membership-action", "team_id": dash.ALL, "action": dash.ALL},
            "id",
        ),
        State("user-team-search-results-store", "data"),
    ],
    prevent_initial_call=True,
)
def handle_team_membership_action(n_clicks, button_ids, current_search_results):
    if not any(n_clicks or []):
        return no_update, no_update, no_update, no_update, no_update

    triggered = dash.ctx.triggered_id
    if not triggered:
        return no_update, no_update, no_update, no_update, no_update

    team_id = triggered.get("team_id")
    action = triggered.get("action")
    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)

    if action == "join":
        response = post_api_data(f"teams/{team_id}/join", token, {}, logger)
        success_message = "Joined team."
    else:
        response = delete_api_data(f"user/teams/{team_id}", token, logger)
        success_message = "Left team."

    if response.status_code not in {200, 201}:
        error_message = "Could not update team membership right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return (
            no_update,
            no_update,
            no_update,
            no_update,
            create_message_banner(error_message, "error"),
        )

    updated_teams_response = fetch_api_data("user/teams", token, logger)
    updated_teams = (
        updated_teams_response.json()
        if updated_teams_response.status_code == 200
        else []
    )

    updated_results = current_search_results or []
    if updated_results:
        for team in updated_results:
            if str(team.get("id")) == str(team_id):
                team["is_member"] = action == "join"

    return (
        team_membership_block(updated_teams),
        updated_teams,
        team_search_results_block(updated_results),
        updated_results,
        create_message_banner(success_message, "success"),
    )


@callback(
    [
        Output("user-teams-panel", "children", allow_duplicate=True),
        Output("user-teams-store", "data", allow_duplicate=True),
        Output("user-page-banner", "children", allow_duplicate=True),
    ],
    Input({"type": "leave-team-button", "team_id": dash.ALL}, "n_clicks"),
    State({"type": "leave-team-button", "team_id": dash.ALL}, "id"),
    prevent_initial_call=True,
)
def leave_team_from_membership_list(n_clicks, button_ids):
    if not any(n_clicks or []):
        return no_update, no_update, no_update

    triggered = dash.ctx.triggered_id
    if not triggered:
        return no_update, no_update, no_update

    team_id = triggered.get("team_id")
    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    response = delete_api_data(f"user/teams/{team_id}", token, logger)

    if response.status_code != 200:
        error_message = "Could not leave team right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return no_update, no_update, create_message_banner(error_message, "error")

    updated_teams_response = fetch_api_data("user/teams", token, logger)
    updated_teams = (
        updated_teams_response.json()
        if updated_teams_response.status_code == 200
        else []
    )
    return (
        team_membership_block(updated_teams),
        updated_teams,
        create_message_banner("Left team.", "success"),
    )


@callback(
    [
        Output("user-tags-panel", "children"),
        Output("user-tags-store", "data"),
        Output("user-page-banner", "children", allow_duplicate=True),
        Output("new-tag-name", "value"),
        Output("new-tag-description", "value"),
        Output("new-tag-color", "value"),
        Output("user-tag-create-panel", "children", allow_duplicate=True),
        Output("user-tag-create-open", "data", allow_duplicate=True),
    ],
    Input("create-tag-button", "n_clicks"),
    [
        State("new-tag-name", "value"),
        State("new-tag-description", "value"),
        State("new-tag-color", "value"),
        State("new-tag-owner", "value"),
        State("user-tags-store", "data"),
    ],
    prevent_initial_call=True,
)
def create_tag(n_clicks, name, description, color, owner_value, existing_tags):
    if not n_clicks:
        return (
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    if not name or not str(name).strip():
        return (
            no_update,
            no_update,
            create_message_banner("Tag name is required.", "warning"),
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    logger = current_app.config["TXV_LOGGER"]
    token = get_jwt_from_request(request)
    payload = {
        "name": str(name).strip(),
        "description": description or None,
        "color": color or None,
    }
    if owner_value and owner_value != "personal":
        payload["owner_team_id"] = owner_value

    response = post_api_data("tags", token, payload, logger)
    if response.status_code != 201:
        error_message = "Could not create tag right now."
        try:
            error_message = response.json().get("error", error_message)
        except ValueError:
            pass
        return (
            no_update,
            no_update,
            create_message_banner(error_message, "error"),
            no_update,
            no_update,
            no_update,
            no_update,
            no_update,
        )

    updated_tags_response = fetch_api_data("tags", token, logger)
    updated_tags = existing_tags or []
    if updated_tags_response.status_code == 200:
        updated_tags = updated_tags_response.json()

    return (
        tag_block(updated_tags),
        updated_tags,
        create_message_banner("Tag created.", "success"),
        "",
        "",
        "",
        html.Div(),
        False,
    )
