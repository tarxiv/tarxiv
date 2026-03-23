"""Authentication callbacks for the dashboard."""

import os
from urllib.parse import parse_qs

from dash import (
    Input,
    Output,
    State,
    no_update,
    callback_context,
)
from flask import request, has_request_context

from ...auth import verify_token
from ..components import create_message_banner


def _api_login_url(provider: str = "orcid") -> str:
    api_url = os.environ.get("TARXIV_EXTERNAL_API_URL", "").rstrip("/")
    return f"{api_url}/auth/{provider}/login"


def register_auth_callbacks(app, logger):
    """Wire up authentication-related callbacks."""
    # Redirect the browser to the API login endpoint.
    # The API handles the full OAuth exchange and redirects back with ?token=...
    app.clientside_callback(
        f"""
        function(n_clicks) {{
            if (n_clicks) {{
                window.location.href = "{_api_login_url("orcid")}";
            }}
            return window.dash_clientside.no_update;
        }}
        """,
        Output("orcid-redirect-dummy", "data"),
        Input("auth-orcid-login", "n_clicks"),
        prevent_initial_call=True,
    )

    @app.callback(
        [
            Output("auth-message-banner", "children", allow_duplicate=True),
            Output("url", "href", allow_duplicate=True),
        ],
        Input("auth-location", "search"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def handle_token_callback(search, pathname):
        """Pick up ?token=<jwt> after API redirects back, validate, and store."""
        if not search:
            return no_update, no_update

        params = parse_qs(search.lstrip("?"))
        token = (params.get("token") or [None])[0]
        if not token:
            return no_update, no_update

        try:
            payload = verify_token(token)
        except Exception as exc:
            expired = "expired" in str(exc).lower() or "Signature has expired" in str(
                exc
            )
            msg = (
                "Session expired — please log in again."
                if expired
                else "Login failed: invalid token."
            )
            logger.error({"jwt_error": str(exc)})
            banner = create_message_banner(msg, "error")
            return banner, no_update

        profile = payload.get("profile", {})
        name = (
            profile.get("username")
            or profile.get("nickname")
            or profile.get("forename")
            or profile.get("email")
            or "ORCID user"
        )
        banner = create_message_banner(f"Logged in as {name}", "success")

        is_secure = request.scheme == "https" if has_request_context() else False

        callback_context.response.set_cookie(
            "tarxiv_token",
            token,
            httponly=True,
            secure=is_secure,
            samesite="Lax",
            max_age=86400,
        )

        return banner, pathname or "/"

    @app.callback(
        [
            Output("auth-message-banner", "children", allow_duplicate=True),
            Output("url", "href", allow_duplicate=True),
        ],
        Input("auth-logout-button", "n_clicks"),
        State("url", "pathname"),
        prevent_initial_call=True,
    )
    def handle_logout(logout_clicks, pathname):
        if not logout_clicks:
            return no_update, no_update
        info = create_message_banner("You have been logged out.", "info")

        is_secure = request.scheme == "https" if has_request_context() else False

        callback_context.response.delete_cookie("tarxiv_token")
        callback_context.response.set_cookie(
            "tarxiv_token",
            "",
            max_age=0,
            secure=is_secure,
            httponly=True,
            samesite="Lax",
        )
        return info, pathname or "/"
