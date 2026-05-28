"""Main dashboard layout."""

import os

from dash import html, dcc
import dash
import flask
import dash_mantine_components as dmc
import requests
from ..components import (
    get_theme_components,
    footer_card,
    get_cookie_popup,
    create_nav_link,
    avatar_fallback,
    avatar_image,
)
from ...auth import get_authenticated_user, get_jwt_from_request


def _fetch_live_profile(token):
    """Fetch the current profile from the API.

    The JWT ``profile`` claim is a snapshot taken at login, so fields edited
    afterwards (e.g. email) can be stale. This reads the live record and falls
    back to ``None`` on any error so the caller can use the JWT snapshot.
    """
    if not token:
        return None
    host = os.getenv("TARXIV_API_HOST", "tarxiv-api")
    port = os.getenv("TARXIV_API_PORT", "9001")
    api_url = os.getenv("TARXIV_INTERNAL_API_URL", f"http://{host}:{port}")
    try:
        response = requests.get(
            url=f"{api_url}/user",
            timeout=5,
            headers={
                "accept": "application/json",
                "Authorization": f"Bearer {token}",
            },
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    return response.json()


SETTING_DEFAULTS = {  # These defaults need to correspond with the PERMISSION_MAP in cookie_callbacks.py
    "theme": "tarxiv_light",
    "analytics_on": False,
    "user": None,
}


def account_nav_hovercard(
    user_icon, user_page, account_name, account_email, account_avatar
):
    """Wrap the Account nav link in a hover card showing a profile summary."""
    nav_link = create_nav_link(
        icon=user_icon,
        label=user_page["name"],
        href=user_page["relative_path"],
        is_active=False,
    )

    if not account_name:
        dropdown_children = [
            dmc.Text("Not signed in", fw=600, size="sm"),
            dmc.Anchor("Sign in", href=user_page["relative_path"], size="xs"),
        ]
    else:
        dropdown_children = [
            dmc.Group(
                [
                    account_avatar,
                    dmc.Stack(
                        [
                            dmc.Text(account_name, fw=600, size="sm"),
                            dmc.Text(
                                account_email or "No email",
                                size="xs",
                                c="dimmed",
                            ),
                        ],
                        gap=0,
                    ),
                ],
                gap="xs",
                wrap="nowrap",
            ),
            dmc.Anchor(
                "View account", href=user_page["relative_path"], size="xs", mt="xs"
            ),
            dmc.Button(
                "Logout",
                variant="outline",
                size="xs",
                id="auth-logout-button"
            ),
        ]

    return dmc.HoverCard(
        withArrow=True,
        position="right",
        shadow="md",
        openDelay=150,
        closeDelay=500,
        children=[
            dmc.HoverCardTarget(
                nav_link,
                # Here we have to pass style props to the dmc.Box wrapper using
                # boxWrapperProps (see https://www.dash-mantine-components.com/components/hovercard
                # and https://www.dash-mantine-components.com/style-props)
                boxWrapperProps={"w": "100%"},
            ),
            dmc.HoverCardDropdown(
                dmc.Stack(dropdown_children, gap="xs"),
            ),
        ],
    )


def create_layout() -> dmc.MantineProvider:
    """Create the main dashboard layout.

    Note: This is evaluated dynamically on every page load via app.layout = create_layout

    Returns
    -------
        html.Div containing the complete dashboard layout
    """
    theme, theme_switch = get_theme_components()
    user_page = dash.page_registry.get(
        "tarxiv.dashboard.pages.user",
        {
            "name": "Acc",
            "icon": "mdi:user-outline",
            "relative_path": "/user",
        },
    )

    # Check if user is authenticated and update layout
    user_profile = None
    user_icon = user_page.get("icon", "mdi:help-circle")
    account_name = None
    account_email = None
    account_avatar = None
    if flask.has_request_context():
        user_profile = get_authenticated_user(flask.request)
        if user_profile:
            # Prefer the live record (the JWT snapshot can be stale, e.g. email).
            live_profile = _fetch_live_profile(get_jwt_from_request(flask.request))
            profile = {**user_profile, **(live_profile or {})}
            name = (
                profile.get("username")
                or profile.get("forename")
                or profile.get("email")
                or "User"
            )
            avatar_src = profile.get("picture_url")
            user_icon = (
                avatar_image(avatar_src) if avatar_src else avatar_fallback(name[:1])
            )
            account_name = name
            account_email = profile.get("email")
            account_avatar = (
                avatar_image(avatar_src) if avatar_src else avatar_fallback(name[:1])
            )

    return dmc.MantineProvider(
        theme=theme,
        # children=html.Div(
        children=dmc.AppShell(
            navbar={
                "width": 100,
                "breakpoint": "sm",
                "collapsed": {"mobile": True},
            },
            header={
                "height": {
                    # "base": 50,
                    "sm": 50,
                },
                "collapsed": {"mobile": False},
            },
            padding="md",
            layout="alt",
            # dmc.Box(
            children=[
                # 1. PERMISSIONS (local): Remembers what the user said 'Yes' to.
                dcc.Store(id="cookie-consent-store", storage_type="local"),
                # 2. PERMANENT DATA (Local): Stores actual values (e.g. theme='dark') only if permitted.
                dcc.Store(id="local-settings-store", storage_type="local"),
                # 3. LIVE STATE (Session): What the app currently uses to render.
                dcc.Store(
                    id="active-settings-store",
                    storage_type="session",
                    data=SETTING_DEFAULTS,
                ),
                # Authentication and profile management
                dcc.Location(
                    id="auth-location", refresh=True
                ),  # Note: Changed to refresh=True for full layout rebuilds
                dcc.Store(id="orcid-redirect-dummy", storage_type="memory"),
                html.Div(
                    id="dummy-output", style={"display": "none"}
                ),  # Dummy output for clientside callback
                get_cookie_popup(),
                # Navigation rail
                dmc.AppShellHeader(
                    hiddenFrom="sm",
                    children=[
                        dmc.Burger(
                            id="burger",
                            opened=False,
                            size="sm",
                        ),
                        dmc.Text("TarXiv Dashboard"),
                    ],
                ),
                dmc.AppShellNavbar(
                    p="xs",
                    style={"backgroundColor": "var(--tarxiv-surface-1)"},
                    children=[
                        dmc.Stack(
                            h="100%",
                            gap="xs",
                            children=[
                                # The main navigation items (populated by callback)
                                html.Div(id="nav-rail-content"),
                                # The "Magic" bottom pin
                                html.Div(
                                    children=[
                                        account_nav_hovercard(
                                            user_icon=user_icon,
                                            user_page=user_page,
                                            account_name=account_name,
                                            account_email=account_email,
                                            account_avatar=account_avatar,
                                        ),
                                        theme_switch,
                                    ],
                                    style={
                                        "marginTop": "auto"
                                    },  # Pushes theme toggle to the very bottom
                                ),
                            ],
                        )
                    ],
                ),
                # Content container
                dmc.AppShellMain(
                    # p="md",
                    children=[
                        html.Div(
                            style={
                                "display": "flex",
                                "flexDirection": "column",
                                "minHeight": "calc(100vh - 32px)",  # Adjust 32px based on your padding
                            },
                            children=[
                                dcc.Location(
                                    id="url",
                                    refresh=True,  # Refresh page on URL change
                                ),  # Essential for tracking the current page
                                html.Div(
                                    id="page-content",  # Container for page content
                                    style={
                                        "flex": "1"
                                    },  # Allow this div to grow to push footer down
                                    children=[
                                        html.Div(id="auth-message-banner"),
                                        dash.page_container,
                                    ],
                                ),
                                # Footer
                                footer_card(),
                            ],
                        ),
                    ],
                ),
                # permanent footer not used
                # dmc.AppShellFooter("Footer", p="md"),
            ],
        ),
    )
