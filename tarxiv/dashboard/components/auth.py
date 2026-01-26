"""Auth UI components for the dashboard."""
from dash import dcc, html
from ..styles import (
    NAVBAR_STYLE,
    NAV_TITLE_STYLE,
    NAV_RIGHT_STYLE,
    USER_CHIP_STYLE,
    AVATAR_STYLE,
    AVATAR_FALLBACK_STYLE,
    LOGIN_BUTTON_STYLE,
    SIGNUP_BUTTON_STYLE,
    PROFILE_BUTTON_STYLE,
    AUTH_MODAL_STYLE,
    AUTH_MODAL_CONTENT_STYLE,
    INPUT_STYLE,
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
                        "Sign up",
                        id="auth-open-signup",
                        n_clicks=0,
                        style=SIGNUP_BUTTON_STYLE,
                    ),
                    html.Button(
                        "Log in",
                        id="auth-open-login",
                        n_clicks=0,
                        style=LOGIN_BUTTON_STYLE,
                    ),
                ],
                style=NAV_RIGHT_STYLE,
            ),
        ],
        style=NAVBAR_STYLE,
    )


def create_login_modal():
    """Lightweight login modal (email/password for now)."""
    return html.Div(
        id="auth-login-modal",
        style=AUTH_MODAL_STYLE,
        children=html.Div(
            [
                html.H3("Sign in to TarXiv", style={"marginTop": 0, "marginBottom": "12px", "color": COLORS["secondary"]}),
                html.Div(
                    [
                        html.Label("Email", style={"fontWeight": "600", "fontSize": "13px"}),
                        dcc.Input(
                            id="auth-email-input",
                            type="email",
                            placeholder="you@example.com",
                            style={**INPUT_STYLE, "width": "100%", "marginTop": "6px", "marginBottom": "12px"},
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Label("Password", style={"fontWeight": "600", "fontSize": "13px"}),
                        dcc.Input(
                            id="auth-password-input",
                            type="password",
                            placeholder="••••••••",
                            style={**INPUT_STYLE, "width": "100%", "marginTop": "6px", "marginBottom": "12px"},
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Button(
                            "Sign in",
                            id="auth-submit-login",
                            n_clicks=0,
                            style={**BUTTON_STYLE, "width": "100%"},
                        ),
                        html.Button(
                            "Cancel",
                            id="auth-close-login",
                            n_clicks=0,
                            style={
                                "marginTop": "10px",
                                "width": "100%",
                                "backgroundColor": "white",
                                "color": COLORS["secondary"],
                                "border": "1px solid #e5e7eb",
                                "borderRadius": "6px",
                                "padding": "8px 12px",
                                "cursor": "pointer",
                            },
                        ),
                        html.Div(
                            id="auth-modal-message",
                            style={"marginTop": "12px"},
                        ),
                    ]
                ),
            ],
            style=AUTH_MODAL_CONTENT_STYLE,
        ),
    )


def create_signup_modal():
    """Modal form to register a user."""
    return html.Div(
        id="auth-signup-modal",
        style=AUTH_MODAL_STYLE,
        children=html.Div(
            [
                html.H3(
                    "Create a TarXiv account",
                    style={"marginTop": 0, "marginBottom": "12px", "color": COLORS["secondary"]},
                ),
                html.Div(
                    [
                        html.Label("Email", style={"fontWeight": "600", "fontSize": "13px"}),
                        dcc.Input(
                            id="auth-signup-email",
                            type="email",
                            placeholder="you@example.com",
                            style={**INPUT_STYLE, "width": "100%", "marginTop": "6px", "marginBottom": "12px"},
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Label("Password", style={"fontWeight": "600", "fontSize": "13px"}),
                        dcc.Input(
                            id="auth-signup-password",
                            type="password",
                            placeholder="••••••••",
                            style={**INPUT_STYLE, "width": "100%", "marginTop": "6px", "marginBottom": "12px"},
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Label("Display name", style={"fontWeight": "600", "fontSize": "13px"}),
                        dcc.Input(
                            id="auth-signup-username",
                            type="text",
                            placeholder="e.g., astro_hunter",
                            style={**INPUT_STYLE, "width": "100%", "marginTop": "6px", "marginBottom": "12px"},
                        ),
                    ]
                ),
                html.Div(
                    [
                        html.Button(
                            "Create account",
                            id="auth-submit-signup",
                            n_clicks=0,
                            style={**SIGNUP_BUTTON_STYLE, "width": "100%"},
                        ),
                        html.Button(
                            "Cancel",
                            id="auth-close-signup",
                            n_clicks=0,
                            style={
                                "marginTop": "10px",
                                "width": "100%",
                                "backgroundColor": "white",
                                "color": COLORS["secondary"],
                                "border": "1px solid #e5e7eb",
                                "borderRadius": "6px",
                                "padding": "8px 12px",
                                "cursor": "pointer",
                            },
                        ),
                        html.Div(
                            id="auth-signup-message",
                            style={"marginTop": "12px"},
                        ),
                    ]
                ),
            ],
            style=AUTH_MODAL_CONTENT_STYLE,
        ),
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
