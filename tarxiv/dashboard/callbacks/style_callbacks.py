from dash import (
    Output,
    Input,
    State,
    Patch,
    ALL,
    clientside_callback,
    ctx,
    page_registry,
)
import plotly.io as pio
from ..components import PLOT_TYPE, THEME_STORE_ID, create_nav_link


def register_style_callbacks(app, logger):
    # Add light/dark mode toggle callback
    clientside_callback(
        """
        (themeData) => {
            // 1. Determine if we should be in dark or light mode
            // This handles strings like 'tarxiv_dark' or just 'dark'
            const isDark = themeData && themeData.includes('dark');
            const themeValue = isDark ? 'dark' : 'light';

            // 2. Set the attribute on the HTML tag (This flips Mantine's CSS variables)
            document.documentElement.setAttribute('data-mantine-color-scheme', themeValue);

            // 3. Dash needs an output, so we return 'no_update' to the dummy ID
            return window.dash_clientside.no_update;
        }
        """,
        Output(THEME_STORE_ID, "id"),  # Using the store's own ID as a dummy output
        Input(THEME_STORE_ID, "data"),
    )

    @app.callback(
        Output(THEME_STORE_ID, "data"),
        Input("color-scheme-toggle", "n_clicks"),
        State(THEME_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def toggle_theme_value(n, current_theme):
        # Just flip the string. Easy.
        return "tarxiv_light" if "dark" in current_theme else "tarxiv_dark"

    @app.callback(
        Output({"type": PLOT_TYPE, "index": ALL}, "figure", allow_duplicate=True),
        Output("theme-icon", "icon"),
        Input(THEME_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_all_plots_theme(theme_name):
        # Determine the icon first (it's always needed)
        light_icon = "line-md:moon-to-sunny-outline-transition"
        dark_icon = "line-md:sunny-outline-to-moon-loop-transition"
        theme_icon = dark_icon if "dark" in theme_name else light_icon

        # ctx.outputs_list is a list of lists because we have two Outputs in the decorator.
        # The first element [0] corresponds to the ALL plots output.
        plot_outputs = (
            ctx.outputs_list[0] if isinstance(ctx.outputs_list[0], list) else []
        )

        # 1. Create the Patch for the plots
        theme_patch = Patch()
        template_key = theme_name if "tarxiv" in theme_name else f"tarxiv_{theme_name}"
        theme_patch["layout"]["template"] = pio.templates[template_key]

        # 2. Return a TUPLE: (List of patches for plots, Single icon string)
        # Even if plot_outputs is empty, we return ([], theme_icon)
        return [theme_patch] * len(plot_outputs), theme_icon

    @app.callback(
        Output("nav-rail-content", "children"),
        Input("url", "pathname"),  # Requires dcc.Location(id="url") in the layout
    )
    def refresh_navigation(pathname):
        # # Sort pages by the 'order' key you added in dash.register_page
        nav_pages = sorted(
            [p for p in page_registry.values() if "order" in p],
            key=lambda x: x["order"],
        )

        return [
            create_nav_link(
                icon=page.get("icon", "mdi:help-circle"),
                # label=page["name"],
                label=page["title"],
                href=page["relative_path"],
                is_active=(pathname == page["relative_path"]),
            )
            for page in nav_pages
        ]
