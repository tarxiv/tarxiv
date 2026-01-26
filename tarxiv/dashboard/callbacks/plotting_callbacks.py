"""Plotting callbacks for the dashboard."""

from dash import Output, Input, State, no_update
from ..components import (
    create_lightcurve_plot,
    create_sky_plot,
    THEME_STORE_ID,
    PLOT_TYPE,
)


def register_plotting_callbacks(app, logger):
    """Register all plotting-related callbacks.

    Args:
        app: Dash app instance
        logger: Logger instance
    """

    @app.callback(
        Output({"type": PLOT_TYPE, "index": "lightcurve-plot"}, "figure"),
        Input("lightcurve-store", "data"),
        State(THEME_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_lightcurve_plot_callback(data, theme_template):
        """Update the lightcurve plot when data changes."""
        if not data or not data.get("id"):
            return no_update

        lc_data = data.get("data")
        object_id = data.get("id")

        # create_lightcurve_plot now returns the figure directly (dict/go.Figure)
        fig = create_lightcurve_plot(lc_data, object_id, theme_template, logger)
        if fig:
            return fig
        return {}

    @app.callback(
        Output({"type": PLOT_TYPE, "index": "sky-plot"}, "figure"),
        Input("cone-search-store", "data"),
        State(THEME_STORE_ID, "data"),
        prevent_initial_call=True,
    )
    def update_sky_plot_callback(data, theme_template):
        """Update the sky plot when data changes."""
        if not data or not data.get("results"):
            return no_update

        results = data.get("results")
        ra = data.get("ra")
        dec = data.get("dec")

        fig = create_sky_plot(results, ra, dec, theme_template, logger)
        if fig:
            return fig
        return {}
