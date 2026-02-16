"""Main dashboard layout."""

from dash import html, dcc
import dash
import dash_mantine_components as dmc
from ..components import (
    get_theme_components,
    footer_card,
    get_cookie_popup,
    # COOKIE_DEFAULTS,
)

SETTING_DEFAULTS = {  # These defaults need to correspond with the PERMISSION_MAP in cookie_callbacks.py
    "theme": "tarxiv_light",
    "analytics_on": False,
    "user": None,
}


def create_layout() -> dmc.MantineProvider:
    """Create the main dashboard layout.

    Returns
    -------
        html.Div containing the complete dashboard layout
    """
    theme, theme_switch = get_theme_components()
    return dmc.MantineProvider(
        theme=theme,
        # children=html.Div(
        children=dmc.AppShell(
            navbar={
                "width": 100,
                "breakpoint": "sm",
                "collapsed": {"mobile": True},
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
                get_cookie_popup(),
                # Navigation rail
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
                                theme_switch,
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
                                # theme_switch_state_store,
                                dcc.Location(
                                    id="url",
                                    refresh=False,  # don't refresh the page on URL change
                                ),  # Essential for tracking the current page
                                html.Div(
                                    id="page-content",  # Container for page content
                                    style={
                                        "flex": "1"
                                    },  # Allow this div to grow to push footer down
                                    children=[
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
