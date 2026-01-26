"""Main dashboard layout."""
from dash import dcc, html
from ..styles import CONTAINER_STYLE, PAGE_STYLE, COLORS
from ..components import (
    create_login_modal,
    create_signup_modal,
    create_navbar,
    create_profile_drawer,
    create_unified_search,
    create_results_section,
)


def create_layout():
    """Create the main dashboard layout.

    Returns
    -------
        html.Div containing the complete dashboard layout
    """
    return html.Div(
        [
            dcc.Store(id="auth-session-store", storage_type="session"),
            dcc.Store(id="auth-modal-open", data=False),
            dcc.Store(id="auth-signup-modal-open", data=False),
            dcc.Store(id="profile-drawer-open", data=False),
            create_login_modal(),
            create_signup_modal(),
            create_navbar(),
            create_profile_drawer(),
            # Content container
            html.Div(
                [
                    html.Div(
                        "Explore astronomical transients and their lightcurves.",
                        style={"color": COLORS["muted"], "fontSize": "14px", "margin": "10px 0"},
                    ),
                    html.Div(id="auth-message-banner", style={"marginBottom": "10px"}),
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
