from dash import (
    Output,
    Input,
    State,
    Patch,
    ALL,
    clientside_callback,
    ctx,
    dcc,
    no_update,
    page_registry,
)
import dash_mantine_components as dmc
import plotly.io as pio
from dash_iconify import DashIconify


def register_style_callbacks(app, logger):
    # Add light/dark mode toggle callback
    clientside_callback(
        """
        (settings) => {
            // 1. Extract theme from dictionary, fallback to light
            const themeStr = (settings && settings.theme) ? settings.theme : 'light';
            const isDark = themeStr.includes('dark');
            const themeValue = isDark ? 'dark' : 'light';

            // 2. Set Mantine attribute
            document.documentElement.setAttribute('data-mantine-color-scheme', themeValue);

            // 3. Dash needs an output, so we return 'no_update' to the dummy ID
            return window.dash_clientside.no_update;
        }
        """,
        Output(
            "dummy-output", "style", allow_duplicate=True
        ),  # Use the new store as dummy output
        Input("active-settings-store", "data"),
        prevent_initial_call=True,
    )

    # --- Theme toggle (active) ---
    @app.callback(
        Output("active-settings-store", "data", allow_duplicate=True),
        Input("color-scheme-toggle", "n_clicks"),
        State("active-settings-store", "data"),
        prevent_initial_call=True,
    )
    def update_active_theme(n_clicks, active_settings):
        # Ensure we use the correct ID: active-settings-store
        p = Patch()
        current_theme = active_settings.get("theme")
        p["theme"] = "tarxiv_light" if "dark" in current_theme else "tarxiv_dark"
        return p

    @app.callback(
        [
            Output(
                {"type": "themeable-plot", "index": ALL}, "figure", allow_duplicate=True
            ),
            Output("theme-icon", "icon"),
        ],
        Input("active-settings-store", "data"),
        prevent_initial_call=True,
    )
    def update_all_plots_theme(settings):
        theme_name = settings.get("theme", "tarxiv_light")

        # Determine the icon
        light_icon = "line-md:moon-to-sunny-outline-transition"
        dark_icon = "line-md:sunny-outline-to-moon-loop-transition"
        theme_icon = dark_icon if "dark" in theme_name else light_icon

        # Create Patch for plots
        plot_outputs = (
            ctx.outputs_list[0] if isinstance(ctx.outputs_list[0], list) else []
        )

        theme_patch = Patch()
        # Ensure template_key matches pio.templates keys
        template_key = theme_name if "tarxiv" in theme_name else f"tarxiv_{theme_name}"

        try:
            theme_patch["layout"]["template"] = pio.templates[template_key]
        except KeyError:
            # Fallback if template doesn't exist
            theme_patch["layout"]["template"] = pio.templates["plotly_white"]

        return [theme_patch] * len(plot_outputs), theme_icon

    @app.callback(
        [
            Output("topbar-nav", "children"),
            Output("mobile-nav-content", "children"),
        ],
        Input("url", "pathname"),  # Requires dcc.Location(id="url") in the layout
    )
    def refresh_navigation(pathname):
        # Sort pages by the 'order' key set in dash.register_page
        pages = page_registry.values()
        nav_pages = [p for p in pages if p.get("order") is not None]
        nav_pages = sorted(nav_pages, key=lambda x: x["order"])

        topbar_links = [
            dcc.Link(
                page["name"],
                href=page["relative_path"],
                className="tarxiv-topnav-link"
                + (" active" if pathname == page["relative_path"] else ""),
            )
            for page in nav_pages
        ]
        mobile_links = [
            dmc.NavLink(
                label=page["name"],
                href=page["relative_path"],
                leftSection=DashIconify(
                    icon=page.get("icon", "mdi:help-circle"), width=20
                ),
                active=(pathname == page["relative_path"]),
            )
            for page in nav_pages
        ]

        return (
            dmc.Group(topbar_links, gap=2, wrap="nowrap"),
            mobile_links,
        )

    # --- Global object search (topbar, present on every page) ---
    @app.callback(
        Output("url", "pathname", allow_duplicate=True),
        Input("global-search-keyboard", "n_keydowns"),
        State("global-search-input", "value"),
        prevent_initial_call=True,
    )
    def global_search(n_keydowns, object_id):
        if not object_id or not object_id.strip():
            return no_update
        return f"/lightcurve/{object_id.strip()}"

    # --- Mobile navigation drawer ---
    @app.callback(
        Output("app-shell", "navbar"),
        Input("burger", "opened"),
        prevent_initial_call=True,
    )
    def toggle_mobile_nav(opened):
        navbar = Patch()
        navbar["collapsed"]["mobile"] = not opened
        return navbar
