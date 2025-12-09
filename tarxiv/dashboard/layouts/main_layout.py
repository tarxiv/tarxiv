"""Main dashboard layout."""
from dash import html
from ..styles import HEADER_STYLE, CONTAINER_STYLE, PAGE_STYLE, COLORS
from ..components import (
    create_unified_search,
    create_results_section
)


def create_layout():
    """Create the main dashboard layout.

    Returns
    -------
        html.Div containing the complete dashboard layout
    """
    return html.Div(
        [
            # Header
            html.Div(
                [
                    html.H1(
                        "TarXiv Database Explorer",
                        style={"marginBottom": "5px", "color": COLORS["secondary"]}
                    ),
                    html.P(
                        "Explore astronomical transients and their lightcurves",
                        style={"color": COLORS["muted"], "fontSize": "16px"}
                    ),
                ],
                style=HEADER_STYLE
            ),

            # Content container
            html.Div(
                [
                    # Error/Message banner
                    html.Div(
                        id="message-banner",
                        children=[],
                        style={"marginBottom": "20px"}
                    ),

                    # Unified search with tabs
                    create_unified_search(),

                    # Results section
                    create_results_section(),
                ],
                style=CONTAINER_STYLE
            ),
        ],
        style=PAGE_STYLE
    )
