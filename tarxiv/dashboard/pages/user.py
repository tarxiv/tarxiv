import dash
from dash import callback, Output, Input, State, no_update, clientside_callback
import dash_mantine_components as dmc
from ..components.cards import (
    title_card,
    expressive_card,
    create_message_banner,
)
from urllib.parse import unquote
from flask import request
from dash_extensions import Keyboard

dash.register_page(
    __name__,
    path="/user",
    title="TarXiv - User",
    name="User",
    icon="mdi:user-outline",
    # order must be blank for it to be hidden from the nav rail
)


def layout(**kwargs):
    token = unquote(request.cookies.get("tarxiv_user_token", ""))

    return dmc.Stack(
        children=[
            title_card(
                title_text="TarXiv Database Explorer",
                subtitle_text="Explore astronomical transients and their lightcurves",
            ),
            expressive_card(
                title="User Settings",
                children=[
                    dmc.Text("Enter your token here:"),
                    dmc.Group(
                        children=[
                            Keyboard(
                                dmc.PasswordInput(
                                    id="token",
                                    placeholder="Enter your token here",
                                    value=token,
                                    w=300,
                                ),
                                captureKeys=["Enter"],
                                id="submit-token-keyboard",
                                n_keydowns=0,
                            ),
                            dmc.Button(
                                "Save Token",
                                id="submit-token-button",
                                n_clicks=0,
                            ),
                        ],
                    ),
                ],
            ),
            create_message_banner(
                message="Success! Cookie has been saved.",
                message_type="success",
                id="cookie-result-banner-success",
                hide=True,
                duration=5000,  # Auto-hide after 5 seconds
            ),
            create_message_banner(
                message="Failed to set cookie. Check browser permissions.",
                message_type="error",
                id="cookie-result-banner-failure",
                hide=True,
            ),
        ]
    )


# Register the clientside callback to set the cookie when the token is submitted
# if remember is checked,
#   set a cookie that expires in 30 days
# otherwise
#   set a session cookie
clientside_callback(
    """
    function(n_clicks, n_keydowns, token_value, cookie_permissions) {
        // Prevent running on initial load
        if (!n_clicks && !n_keydowns) {
            return [true, true];
        }

        try {
            if (cookie_permissions && cookie_permissions.remember) {
                // Set cookie to expire in 30 days
                document.cookie = "tarxiv_user_token=" + encodeURIComponent(token_value) + "; path=/; max-age=2592000; SameSite=Lax";
            } else {
                // Session cookie (expires when the browser is closed)
                document.cookie = "tarxiv_user_token=" + encodeURIComponent(token_value) + "; path=/; SameSite=Lax";
            }
            return [false, true];
        } catch (e) {
            console.error(e);
            return [true, false];
        }
    }
    """,
    [
        Output("cookie-result-banner-success", "hide"),
        Output("cookie-result-banner-failure", "hide"),
    ],
    [
        Input("submit-token-button", "n_clicks"),
        Input("submit-token-keyboard", "n_keydowns"),
    ],
    [
        State("token", "value"),
        State("cookie-consent-store", "data"),
    ],
    prevent_initial_call=True,
)


# Register the server-side callback to update the active settings store with the new token
@callback(
    Output("active-settings-store", "data", allow_duplicate=True),
    [
        Input("submit-token-button", "n_clicks"),
        Input("submit-token-keyboard", "n_keydowns"),
    ],
    [
        State("token", "value"),
        State("active-settings-store", "data"),
    ],
    prevent_initial_call=True,
)
def save_token(n_clicks, n_keydowns, token, settings):
    if not token:
        return no_update  # Don't update if token is empty

    settings.update(
        {"tarxiv_user_token": token}
    )  # Update the settings with the new token

    return settings
