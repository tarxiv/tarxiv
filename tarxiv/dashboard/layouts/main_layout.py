"""Main dashboard layout."""

import os

from dash import html, dcc
import dash
import flask
import dash_mantine_components as dmc
import requests
from dash_extensions import Keyboard
from dash_iconify import DashIconify
from ..components import (
    get_theme,
    footer_card,
    get_cookie_popup,
    avatar_fallback,
    avatar_image,
)
from ...auth import get_authenticated_user, get_jwt_from_request

TOPBAR_HEIGHT_PX = 52
# Page content sits in a centred column; matches the mockup's .container.
CONTENT_MAX_WIDTH_PX = 1380


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


def wordmark():
    """The "tarXiv" wordmark, linking home, with the X in brand red."""
    return dcc.Link(
        href="/",
        className="tarxiv-wordmark",
        children=[
            "tar",
            html.Span("X", className="x"),
            "iv",
        ],
    )


def global_search_box():
    """Topbar object-ID search, present on every page.

    Enter is captured by ``Keyboard`` and handled by the ``global_search``
    callback in ``callbacks/style_callbacks.py``.
    """
    return Keyboard(
        id="global-search-keyboard",
        captureKeys=["Enter"],
        n_keydowns=0,
        children=[
            dmc.TextInput(
                id="global-search-input",
                placeholder="Search object ID…",
                size="xs",
                w=220,
                leftSection=DashIconify(icon="mdi:magnify", width=16),
            )
        ],
    )


def theme_toggle():
    """Light/dark switch.

    Both ids matter: ``color-scheme-toggle`` is the input of
    ``update_active_theme`` and ``theme-icon`` is swapped by
    ``update_all_plots_theme``.
    """
    return dmc.Tooltip(
        label="Toggle light/dark theme",
        withArrow=True,
        children=dmc.ActionIcon(
            DashIconify(
                icon="line-md:moon-to-sunny-outline-transition",
                width=18,
                id="theme-icon",
            ),
            id="color-scheme-toggle",
            variant="subtle",
            color="gray",
            size="lg",
            **{"aria-label": "Toggle light/dark theme"},
        ),
    )


def account_nav_hovercard(
    user_icon, user_page, account_name, account_email, account_avatar
):
    """Wrap the account avatar in a hover card showing a profile summary."""
    # ``user_icon`` is either an avatar component (signed in) or an icon name.
    if isinstance(user_icon, str):
        target = dmc.ActionIcon(
            DashIconify(icon=user_icon, width=18),
            variant="subtle",
            color="gray",
            size="lg",
        )
    else:
        target = dcc.Link(
            user_icon,
            href=user_page["relative_path"],
            style={"display": "flex", "alignItems": "center"},
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
                id="nav-logout-button",
            ),
        ]

    return dmc.HoverCard(
        withArrow=True,
        position="bottom-end",
        shadow="md",
        openDelay=150,
        closeDelay=500,
        children=[
            dmc.HoverCardTarget(target),
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
    theme = get_theme()
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
            id="app-shell",
            # The navbar is a mobile-only drawer now that navigation lives in
            # the header; it stays permanently collapsed on desktop.
            navbar={
                "width": 260,
                "breakpoint": "sm",
                "collapsed": {"mobile": True, "desktop": True},
            },
            header={"height": TOPBAR_HEIGHT_PX},
            padding="md",
            bg="var(--tarxiv-bg)",
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
                # Top navigation bar (all breakpoints)
                dmc.AppShellHeader(
                    px="md",
                    style={
                        "backgroundColor": "var(--tarxiv-card)",
                        "borderBottom": "1px solid var(--tarxiv-border)",
                    },
                    children=dmc.Group(
                        h=TOPBAR_HEIGHT_PX,
                        gap="sm",
                        wrap="nowrap",
                        align="center",
                        children=[
                            dmc.Burger(
                                id="burger",
                                opened=False,
                                size="sm",
                                hiddenFrom="sm",
                            ),
                            wordmark(),
                            # Nav links (populated by refresh_navigation).
                            # dmc.Box, not html.Div: visibleFrom is a Mantine
                            # style prop and the html.* components reject it.
                            dmc.Box(id="topbar-nav", visibleFrom="sm"),
                            dmc.Box(style={"flex": 1}),
                            dmc.Box(global_search_box(), visibleFrom="md"),
                            theme_toggle(),
                            account_nav_hovercard(
                                user_icon=user_icon,
                                user_page=user_page,
                                account_name=account_name,
                                account_email=account_email,
                                account_avatar=account_avatar,
                            ),
                        ],
                    ),
                ),
                # Mobile navigation drawer. Nav clicks reload the page (the
                # url Location has refresh=True), so it resets closed by itself.
                dmc.AppShellNavbar(
                    p="md",
                    children=dmc.Stack(
                        gap="xs",
                        children=[
                            html.Div(id="mobile-nav-content"),
                            dmc.NavLink(
                                label=user_page["name"],
                                href=user_page["relative_path"],
                                leftSection=DashIconify(
                                    icon=user_page.get("icon", "mdi:user-outline"),
                                    width=20,
                                ),
                            ),
                        ],
                    ),
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
                                # Centred content column; the topbar stays
                                # full-bleed. Below this width it goes fluid.
                                "maxWidth": f"{CONTENT_MAX_WIDTH_PX}px",
                                "width": "100%",
                                "margin": "0 auto",
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
