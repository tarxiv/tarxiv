"""Main dashboard layout."""

from dash import html, dcc
import dash_mantine_components as dmc
from ..components import (
    create_unified_search,
    create_results_section,
    get_theme_components,
    TitleCard,
)
# from ..styles import HEADER_STYLE, CONTAINER_STYLE, PAGE_STYLE, COLORS


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
                # Header - not used
                # TitleCard(
                #     title_text="TarXiv Database Explorer",
                #     subtitle_text="Explore astronomical transients and their lightcurves",
                #     # right_component=theme_switch,
                #     # style=HEADER_STYLE,
                # ),
                # Content container
                dmc.AppShellMain(
                    # p="md",
                    children=[
                        theme_switch_state_store,
                        dcc.Store(id="lightcurve-store"),
                        dcc.Store(id="cone-search-store"),
                        dcc.Location(
                            id="url", refresh=False
                        ),  # Essential for tracking the current page
                        TitleCard(
                            title_text="TarXiv Database Explorer",
                            subtitle_text="Explore astronomical transients and their lightcurves",
                        ),
                        # Error/Message banner
                        #
                        dmc.Box(
                            id="message-banner",
                            children=[],
                            style={"marginBottom": "20px"},
                        ),
                        # Unified search with tabs
                        create_unified_search(),
                        # Results section
                        create_results_section(),
                    ],
                ),
                # dmc.AppShellFooter("Footer", p="md"),
            ],
        ),
    )
