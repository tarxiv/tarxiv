import os
from urllib.parse import unquote

import dash
import dash_mantine_components as dmc
import flask
import requests
from flask import current_app, request

from ...auth import get_authenticated_user, get_jwt_from_request
from ..components.auth import avatar_fallback, avatar_image
from ..components.cards import expressive_card, title_card
from ..styles import ORCID_BUTTON_STYLE

dash.register_page(
    __name__,
    path="/user",
    title="TarXiv - User",
    name="User",
    icon="mdi:user-outline",
)


def layout(**kwargs):
    token = unquote(request.cookies.get("tarxiv_token", ""))
    user_profile = None
    team_memberships = []
    fetch_error = None

    if flask.has_request_context():
        token = get_jwt_from_request(flask.request) or token
        user_profile = get_authenticated_user(jwt_token=token)

        if token and user_profile:
            logger = current_app.config["TXV_LOGGER"]
            user_profile, team_memberships, fetch_error = fetch_user_page_data(
                token, logger
            )

    if user_profile:
        name = (
            user_profile.get("username")
            or user_profile.get("nickname")
            or user_profile.get("forename")
            or user_profile.get("email")
            or "User"
        )
        email = user_profile.get("email", "")
        avatar_src = user_profile.get("picture_url")
        avatar = avatar_image(avatar_src) if avatar_src else avatar_fallback(name[:1])

        auth_content = dmc.Stack([
            dmc.Stack(
                id="user-profile-panel",
                children=[
                    line("Username", user_profile.get("username")),
                    line("Nickname", user_profile.get("nickname")),
                    line("Forename", user_profile.get("forename")),
                    line("Surname", user_profile.get("surname")),
                    line("Institution", user_profile.get("institution")),
                    line("Bio", user_profile.get("bio")),
                    dmc.Divider(label="Teams", labelPosition="left", my="sm"),
                    team_membership_block(team_memberships),
                    dmc.Divider(label="Tags", labelPosition="left", my="sm"),
                    dmc.Text(
                        "Personal and team object tags will appear here once the dashboard tagging UI is wired up.",
                        size="sm",
                        c="dimmed",
                    ),
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
                ],
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


def line(label, value):
    return dmc.Group([dmc.Text(f"{label}: ", fw=700), dmc.Text(value or "-")], gap="xs")


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
                            dmc.Text(
                                f"Team ID: {item.get('team_id', '-')}",
                                fw=600,
                            ),
                            dmc.Badge(item.get("role", "member"), variant="light"),
                        ],
                        justify="space-between",
                    )
                ],
            )
            for item in memberships
        ],
        gap="sm",
    )


def fetch_user_page_data(token: str, logger):
    profile_response = fetch_api_data("user", token, logger)
    teams_response = fetch_api_data("user/teams", token, logger)

    if profile_response.status_code == 401:
        return None, [], "Session expired. Please log in again."

    profile = None
    memberships = []
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

    return profile, memberships, " ".join(errors) if errors else None


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
