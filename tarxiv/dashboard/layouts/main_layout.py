"""Main dashboard layout."""

from dash import html, dcc
import dash
import dash_mantine_components as dmc
from ..components import (
    # create_unified_search,
    # create_results_section,
    get_theme_components,
    # title_card,
    footer_card,
)


def create_layout() -> dmc.MantineProvider:
    """Create the main dashboard layout.

    Returns
    -------
        html.Div containing the complete dashboard layout
    """
    theme, theme_switch_state_store, theme_switch = get_theme_components()
    return dmc.MantineProvider(
        theme=theme,
        # children=html.Div(
        children=dmc.AppShell(
            navbar={
                "width": 100,
                "breakpoint": "sm",
                "collapsed": {"mobile": True},
            },
            # header={"height": 60},
            # footer={"height": 60},
            padding="md",
            layout="alt",
            # dmc.Box(
            children=[
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
                                theme_switch_state_store,
                                dcc.Location(
                                    id="url",
                                    refresh=False,  # don't refresh the page on URL change
                                ),  # Essential for tracking the current page
                                # dcc.Store(id="lightcurve-store"),
                                dcc.Store(id="cone-search-store"),
                                html.Div(
                                    id="page-content",  # Container for page content
                                    style={
                                        "flex": "1"
                                    },  # Allow this div to grow to push footer down
                                    children=[
                                        # title_card(
                                        #     title_text="TarXiv Database Explorer",
                                        #     subtitle_text="Explore astronomical transients and their lightcurves",
                                        # ),
                                        # Error/Message banner
                                        #
                                        # dmc.Box(
                                        #     id="message-banner",
                                        #     children=[],
                                        #     style={"marginBottom": "20px"},
                                        # ),
                                        # Unified search with tabs
                                        # create_unified_search(),
                                        # Results section
                                        # create_results_section(),
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
