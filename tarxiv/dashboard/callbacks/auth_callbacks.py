"""Authentication callbacks for the dashboard."""
from dash import Input, Output, State, ctx, html, no_update

from ...auth import login_with_password, register_user
from ..components import avatar_fallback, avatar_image
from ..styles import (
    AUTH_MODAL_STYLE,
    LOGIN_BUTTON_STYLE,
    SIGNUP_BUTTON_STYLE,
    PROFILE_BUTTON_STYLE,
    USER_CHIP_STYLE,
    PROFILE_DRAWER_STYLE,
    PROFILE_DRAWER_OPEN_STYLE,
)
from .search_callbacks import create_message_banner


def register_auth_callbacks(app, logger):
    """Wire up authentication-related callbacks."""

    @app.callback(
        Output("auth-modal-open", "data", allow_duplicate=True),
        [
            Input("auth-open-login", "n_clicks"),
            Input("auth-close-login", "n_clicks"),
            Input("auth-session-store", "data"),
        ],
        State("auth-modal-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_modal(open_clicks, close_clicks, session_data, modal_open):
        triggered = ctx.triggered_id
        if triggered == "auth-open-login":
            return True
        if triggered in ("auth-close-login", "auth-session-store"):
            return False
        return modal_open

    @app.callback(
        Output("auth-login-modal", "style"),
        Input("auth-modal-open", "data"),
    )
    def set_modal_visibility(is_open):
        base = dict(AUTH_MODAL_STYLE)
        if is_open:
            base["display"] = "flex"
        else:
            base["display"] = "none"
        return base

    @app.callback(
        Output("auth-signup-modal-open", "data", allow_duplicate=True),
        [
            Input("auth-open-signup", "n_clicks"),
            Input("auth-close-signup", "n_clicks"),
            Input("auth-session-store", "data"),
        ],
        State("auth-signup-modal-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_signup_modal(open_clicks, close_clicks, session_data, modal_open):
        triggered = ctx.triggered_id
        if triggered == "auth-open-signup":
            return True
        if triggered in ("auth-close-signup", "auth-session-store"):
            return False
        return modal_open

    @app.callback(
        Output("auth-signup-modal", "style"),
        Input("auth-signup-modal-open", "data"),
    )
    def set_signup_modal_visibility(is_open):
        base = dict(AUTH_MODAL_STYLE)
        base["display"] = "flex" if is_open else "none"
        return base

    @app.callback(
        [
            Output("auth-session-store", "data", allow_duplicate=True),
            Output("auth-message-banner", "children", allow_duplicate=True),
            Output("auth-modal-open", "data", allow_duplicate=True),
            Output("auth-modal-message", "children"),
        ],
        Input("auth-submit-login", "n_clicks"),
        [State("auth-email-input", "value"), State("auth-password-input", "value")],
        prevent_initial_call=True,
    )
    def handle_login(submit_clicks, email, password):
        if not submit_clicks:
            return no_update, no_update, no_update, no_update

        if not email or not password:
            warning = create_message_banner("Please enter email and password.", "warning")
            return no_update, warning, True, warning

        try:
            session_payload = login_with_password(email, password)
            user = session_payload.get("user", {})
            success = create_message_banner(
                f"Logged in as {user.get('username') or user.get('email')}",
                "success",
            )
            return session_payload, success, False, []
        except Exception as exc:  # broad to surface auth issues to UI
            logger.error({"auth_error": str(exc)})
            error_banner = create_message_banner(
                f"Login failed: {exc}", "error"
            )
            return no_update, error_banner, True, error_banner

    @app.callback(
        [
            Output("auth-session-store", "data", allow_duplicate=True),
            Output("auth-message-banner", "children", allow_duplicate=True),
            Output("auth-signup-modal-open", "data", allow_duplicate=True),
            Output("auth-signup-message", "children"),
        ],
        Input("auth-submit-signup", "n_clicks"),
        [
            State("auth-signup-email", "value"),
            State("auth-signup-password", "value"),
            State("auth-signup-username", "value"),
        ],
        prevent_initial_call=True,
    )
    def handle_signup(submit_clicks, email, password, username):
        if not submit_clicks:
            return no_update, no_update, no_update, no_update

        if not email or not password:
            warning = create_message_banner("Email and password are required.", "warning")
            return no_update, warning, True, warning

        try:
            session_payload = register_user(email, password, username)
            user = session_payload.get("user", {})
            success = create_message_banner(
                f"Welcome {user.get('username') or user.get('email')}! Account created.",
                "success",
            )
            return session_payload, success, False, []
        except Exception as exc:
            logger.error({"signup_error": str(exc)})
            error_banner = create_message_banner(f"Sign up failed: {exc}", "error")
            return no_update, error_banner, True, error_banner

    @app.callback(
        [
            Output("auth-user-chip", "children"),
            Output("auth-user-chip", "style"),
            Output("auth-open-login", "style"),
            Output("auth-open-signup", "style"),
            Output("auth-profile-toggle", "style"),
        ],
        Input("auth-session-store", "data"),
    )
    def update_nav_user(session_data):
        profile = (session_data or {}).get("user")
        if not profile:
            return (
                [],
                {**USER_CHIP_STYLE, "display": "none"},
                LOGIN_BUTTON_STYLE,
                SIGNUP_BUTTON_STYLE,
                {**PROFILE_BUTTON_STYLE, "display": "none"},
            )

        name = (
            profile.get("username")
            or profile.get("nickname")
            or profile.get("forename")
            or profile.get("email")
            or "User"
        )
        email = profile.get("email", "")
        avatar_src = profile.get("picture_url")
        avatar = avatar_image(avatar_src) if avatar_src else avatar_fallback(name[:1])

        chip_children = [
            avatar,
            html.Div(
                [
                    html.Div(name, style={"fontWeight": "600", "fontSize": "14px"}),
                    html.Div(email, style={"fontSize": "12px", "color": "#6b7280"}),
                ]
            ),
            html.Button(
                "Logout",
                id="auth-logout-button",
                n_clicks=0,
                style={**LOGIN_BUTTON_STYLE, "backgroundColor": "#e5e7eb", "color": "#111827"},
            ),
        ]
        return (
            chip_children,
            USER_CHIP_STYLE,
            {**LOGIN_BUTTON_STYLE, "display": "none"},
            {**SIGNUP_BUTTON_STYLE, "display": "none"},
            PROFILE_BUTTON_STYLE,
        )

    @app.callback(
        [
            Output("auth-session-store", "data", allow_duplicate=True),
            Output("auth-message-banner", "children", allow_duplicate=True),
            Output("profile-drawer-open", "data", allow_duplicate=True),
        ],
        Input("auth-logout-button", "n_clicks"),
        prevent_initial_call=True,
    )
    def handle_logout(logout_clicks):
        if not logout_clicks:
            return no_update, no_update, no_update
        info = create_message_banner("You have been logged out.", "info")
        return None, info, False

    @app.callback(
        Output("profile-drawer-open", "data", allow_duplicate=True),
        [
            Input("auth-profile-toggle", "n_clicks"),
            Input("auth-profile-close", "n_clicks"),
            Input("auth-session-store", "data"),
        ],
        State("profile-drawer-open", "data"),
        prevent_initial_call=True,
    )
    def toggle_profile_drawer(toggle_clicks, close_clicks, session_data, is_open):
        triggered = ctx.triggered_id
        if triggered == "auth-profile-toggle":
            if not session_data:
                return False
            return not bool(is_open)
        if triggered == "auth-profile-close":
            return False
        if triggered == "auth-session-store" and not session_data:
            return False
        return is_open

    @app.callback(
        Output("profile-drawer", "style"),
        Input("profile-drawer-open", "data"),
    )
    def set_profile_drawer(open_state):
        return PROFILE_DRAWER_OPEN_STYLE if open_state else PROFILE_DRAWER_STYLE

    @app.callback(
        Output("user-profile-panel", "children"),
        Input("auth-session-store", "data"),
    )
    def render_profile(session_data):
        profile = (session_data or {}).get("user")
        if not profile:
            return [
                html.H3("Your profile", style={"marginTop": 0, "color": "#2c3e50"}),
                html.P(
                    "Sign in to see your profile, tags, and teams. This section will grow as we add permissions and roles.",
                    style={"color": "#7f8c8d", "fontSize": "14px"},
                ),
            ]

        def line(label, value):
            return html.Div(
                [
                    html.Span(f"{label}: ", style={"fontWeight": "600"}),
                    html.Span(value or "—"),
                ],
                style={"marginBottom": "6px", "fontSize": "14px"},
            )

        initials = "".join(
            filter(
                None,
                [
                    (profile.get("forename") or "")[:1],
                    (profile.get("surname") or "")[:1],
                ],
            )
        ) or (profile.get("username") or "U")[:2]

        return [
            html.Div(
                [
                    avatar_image(profile.get("picture_url"))
                    if profile.get("picture_url")
                    else avatar_fallback(initials),
                    html.Div(
                        [
                            html.Div(
                                profile.get("nickname") or profile.get("username") or profile.get("email"),
                                style={"fontWeight": "600", "fontSize": "16px"},
                            ),
                            html.Div(profile.get("email"), style={"fontSize": "13px", "color": "#7f8c8d"}),
                        ]
                    ),
                ],
                style={"display": "flex", "alignItems": "center", "gap": "12px", "marginBottom": "16px"},
            ),
            html.Div(
                [
                    line("Institution", profile.get("institution")),
                    line("Bio", profile.get("bio")),
                ]
            ),
            html.Div(
                "Tags and team membership will appear here as we flesh out permissions.",
                style={"color": "#7f8c8d", "fontSize": "13px", "marginTop": "12px"},
            ),
        ]
