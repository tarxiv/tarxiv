"""Auth UI components for the dashboard."""
from dash import html
from ..styles import (
    NAVBAR_STYLE,
    NAV_TITLE_STYLE,
    NAV_RIGHT_STYLE,
    USER_CHIP_STYLE,
    AVATAR_STYLE,
    AVATAR_FALLBACK_STYLE,
    ORCID_BUTTON_STYLE,
    PROFILE_BUTTON_STYLE,
    BUTTON_STYLE,
    COLORS,
    PROFILE_DRAWER_STYLE,
)


def create_navbar():
    """Top navigation bar with auth controls."""
    return html.Div(
        [
            html.Div(
                [
                    html.Div("TarXiv", style={"fontWeight": "700", "fontSize": "18px", "color": COLORS["secondary"]}),
                    html.Div(
                        "Transient Archive dashboard",
                        style={"color": COLORS["muted"], "fontSize": "13px"},
                    ),
                ],
                style=NAV_TITLE_STYLE,
            ),
            html.Div(
                [
                    html.Div(
                        id="auth-user-chip",
                        children=[
                            html.Div(id="auth-avatar-wrapper"),
                            html.Div(
                                [
                                    html.Div(
                                        id="auth-user-name",
                                        children="",
                                        style={"fontWeight": "600", "fontSize": "14px"},
                                    ),
                                    html.Div(
                                        id="auth-user-email",
                                        children="",
                                        style={"fontSize": "12px", "color": COLORS["muted"]},
                                    ),
                                ]
                            ),
                            html.Button(
                                "Logout",
                                id="auth-logout-button",
                                n_clicks=0,
                                style={**BUTTON_STYLE, "padding": "6px 10px"},
                            ),
                        ],
                        style={**USER_CHIP_STYLE, "display": "none"},
                    ),
                    html.Button(
                        "Profile",
                        id="auth-profile-toggle",
                        n_clicks=0,
                        style={**PROFILE_BUTTON_STYLE, "display": "none"},
                    ),
                    html.Button(
                        "Sign in with ORCID",
                        id="auth-orcid-login",
                        n_clicks=0,
                        style=ORCID_BUTTON_STYLE,
                    ),
                ],
                style=NAV_RIGHT_STYLE,
            ),
        ],
        style=NAVBAR_STYLE,
    )


def create_profile_drawer():
    """Slide-out drawer containing profile info."""
    return html.Div(
        id="profile-drawer",
        style=PROFILE_DRAWER_STYLE,
        children=[
            html.Div(
                [
                    html.H3(
                        "Your profile",
                        style={"marginTop": 0, "marginBottom": "6px", "color": COLORS["secondary"]},
                    ),
                    html.Button(
                        "Close",
                        id="auth-profile-close",
                        n_clicks=0,
                        style={
                            **BUTTON_STYLE,
                            "backgroundColor": "white",
                            "color": COLORS["secondary"],
                            "border": "1px solid #e5e7eb",
                            "padding": "4px 10px",
                        },
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "justifyContent": "space-between"},
            ),
            html.Div(id="user-profile-panel"),
        ],
    )


def avatar_fallback(initials: str):
    """Simple fallback avatar badge."""
    return html.Div(
        initials.upper()[:2],
        style=AVATAR_FALLBACK_STYLE,
    )


def avatar_image(src: str):
    """Return an avatar image element."""
    return html.Img(src=src, style=AVATAR_STYLE)
