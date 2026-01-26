"""Main dashboard layout."""

from dash import html, dcc
import dash_mantine_components as dmc
from ..styles import HEADER_STYLE, CONTAINER_STYLE, PAGE_STYLE, COLORS
from ..components import (
    create_unified_search,
    create_results_section,
    get_theme_components,
)


def create_layout() -> dmc.MantineProvider:
    """Create the main dashboard layout.

    Returns
    -------
        html.Div containing the complete dashboard layout
    """
    theme_store, theme_toggle = get_theme_components()
    return dmc.MantineProvider(
        html.Div(
            # return dmc.Stack(
            [
                theme_store,
                dcc.Store(id="lightcurve-store"),
                dcc.Store(id="cone-search-store"),
                # Header
                html.Div(
                    [
                        html.Span(
                            theme_toggle,
                            style={
                                "position": "absolute",
                                "top": "20px",
                                "right": "20px",
                            },
                        ),
                        dmc.Title(
                            "TarXiv Database Explorer",
                            order=1,
                            style={"marginBottom": "5px"},
                        ),
                        dmc.Text(
                            "Explore astronomical transients and their lightcurves",
                            style={"fontSize": "16px"},
                        ),
                    ],
                    style=HEADER_STYLE,
                ),
                # Content container
                html.Div(
                    [
                        # Error/Message banner
                        html.Div(
                            id="message-banner",
                            children=[],
                            style={"marginBottom": "20px"},
                        ),
                        # Unified search with tabs
                        create_unified_search(),
                        # Results section
                        create_results_section(),
                    ],
                    style=CONTAINER_STYLE,
                ),
            ],
            style=PAGE_STYLE,
        )
    )
