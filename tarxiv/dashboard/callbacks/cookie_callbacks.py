from dash import Output, Input, State, no_update, ALL

PERMISSION_MAP = {
    "UI": ["theme"],
    "analytics": ["analytics_on"],
    "remember": ["user", "tarxiv_user_token"],
}


def register_cookie_callbacks(app, logger):
    # --- Runs when the app loads or when the cookie-consent-store is updated ---
    @app.callback(
        [
            Output("active-settings-store", "data"),
            Output("cookie-modal", "opened"),
        ],
        Input(
            "cookie-consent-store", "modified_timestamp"
        ),  # What triggers modified_timestamp? It updates automatically when the store changes.
        [
            State("cookie-consent-store", "data"),
            State("local-settings-store", "data"),
        ],
    )
    def hydrate_app(timestamp, permissions, saved_data):
        # Initial defaults for the current session
        session_defaults = {
            "theme": "tarxiv_light",
            "analytics_on": False,
            "user": None,
        }  # TODO: These should be stored elsewhere?

        # NEW USER: No permissions found
        if permissions is None:
            return session_defaults, True

        # RETURNING USER: Load data based on permissions
        if saved_data:
            # If they have cookies already, override defaults with their saved theme
            session_defaults.update(saved_data)

        return session_defaults, False

    # --- Modal submit button callback to save permissions and close the modal ---
    @app.callback(
        [
            Output("cookie-consent-store", "data"),
            Output("cookie-modal", "opened", allow_duplicate=True),
        ],
        Input("cookie-preferences-submit", "n_clicks"),
        [
            State({"type": "permission-switch", "index": ALL}, "checked"),
            State({"type": "permission-switch", "index": ALL}, "id"),
        ],
        prevent_initial_call=True,
    )
    def save_permissions(n_clicks, switch_states, switch_ids):
        # Reconstruct the dictionary using the 'index' from the pattern-matching IDs
        new_permissions = {
            id_dict["index"]: state
            for id_dict, state in zip(switch_ids, switch_states, strict=True)
        }

        return new_permissions, False

    # --- Generic persistence (active -> local) ---
    @app.callback(
        Output("local-settings-store", "data"),
        Input("active-settings-store", "data"),
        State("cookie-consent-store", "data"),
        prevent_initial_call=True,
    )
    def persist_settings(active_settings, permissions):
        if not permissions:
            return no_update

        # Generic approach: Build a new dict containing only permitted keys
        to_persist = {}

        for permission_key, allowed in permissions.items():
            if allowed:
                # Look up which data keys belong to this permission
                data_keys = PERMISSION_MAP.get(permission_key, [])
                for dk in data_keys:
                    if dk in active_settings:
                        to_persist[dk] = active_settings[dk]

        return to_persist
