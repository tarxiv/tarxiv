import dash
import dash_mantine_components as dmc
from ..components.cards import (
    title_card,
    expressive_card,
)
from ..components.auth import avatar_fallback, avatar_image
from ..styles import ORCID_BUTTON_STYLE
from urllib.parse import unquote
import flask
from flask import request
from ...auth import get_authenticated_user

dash.register_page(
    __name__,
    path="/user",
    title="TarXiv - User",
    name="User",
    icon="mdi:user-outline",
    # order must be blank for it to be hidden from the nav rail
)


def layout(**kwargs):
    token = unquote(request.cookies.get("tarxiv_token", ""))

    user_profile = None
    if flask.has_request_context():
        user_profile = get_authenticated_user(flask.request)

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

        def line(label, value):
            return dmc.Group(
                [dmc.Text(f"{label}: ", fw=700), dmc.Text(value or "—")], gap="xs"
            )

        auth_content = dmc.Stack(
            [
                dmc.Stack(
                    id="user-profile-panel",
                    children=[
                        line("Institution", user_profile.get("institution")),
                        line("Bio", user_profile.get("bio")),
                        dmc.Text(
                            "Tags and team membership will appear here as we flesh out permissions.",
                            size="sm",
                            c="dimmed",
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
                                    email, id="auth-user-email", size="xs", c="dimmed"
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
                dmc.Group(  # Field to show token for API access. The token is very long... Include a copy to clipboard button and wrap the text
                    id="api-token-group",
                    children=[
                        dmc.Text("Your API token:", size="sm", fw=500),
                        dmc.Group(
                            [
                                dmc.Text(
                                    token,
                                    size="xs",
                                    c="dimmed",
                                    id="api-token",
                                    truncate=True,
                                ),
                                # dmc.CopyButton(  # TODO: WHY DOESN'T THIS WORK?!?!
                                #     id="copy-token-button",
                                #     value=str(token),
                                #     children="Copy to clipboard",
                                #     timeout=60 * 1000,  # Reset after 1 minute
                                #     variant="outline",
                                #     size="xs",
                                #     copiedColor="blue",
                                #     copiedChildren="Copied!",
                                # ),
                            ]
                        ),
                    ],
                ),
            ]
        )
    else:
        auth_content = dmc.Stack(
            [
                dmc.Text(
                    "Sign in with ORCID to see your profile, tags, and teams. "
                    "This section will grow as we add permissions and roles."
                ),
                dmc.Group(
                    [
                        dmc.Button(
                            "Sign in with ORCID",
                            id="auth-orcid-login",
                            n_clicks=0,
                            style=ORCID_BUTTON_STYLE,
                        )
                    ]
                ),
            ]
        )

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
