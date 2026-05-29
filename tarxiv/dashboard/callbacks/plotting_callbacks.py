"""Plotting callbacks for the dashboard."""

from dash import Output, Input, State, no_update
from ..components import (
    create_lightcurve_plot,
)


def register_plotting_callbacks(app, logger):
    """Register all plotting-related callbacks.

    Args:
        app: Dash app instance
        logger: Logger instance
    """

    @app.callback(
        Output(
            {"type": "themeable-plot", "index": "lightcurve-plot"},
            "figure",
            allow_duplicate=True,
        ),
        Input("lightcurve-store", "data"),
        State("active-settings-store", "data"),
        prevent_initial_call="initial_duplicate",
    )
    def update_lightcurve_plot_callback(data, settings):
        """Update the lightcurve plot when data changes."""
        if not data or not data.get("id"):
            return no_update

        lc_data = data.get("data")
        object_id = data.get("id")

        theme_template = (
            settings.get("theme", "tarxiv_light") if settings else "tarxiv_light"
        )

        # create_lightcurve_plot now returns the figure directly (dict/go.Figure)
        fig = create_lightcurve_plot(lc_data, object_id, theme_template, logger)
        if fig:
            return fig
        return {}
