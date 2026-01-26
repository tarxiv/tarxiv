from dash import Output, Input, Patch, ALL, clientside_callback, ctx
import dash_mantine_components as dmc
import plotly.io as pio
from ..components import PLOT_TYPE, THEME_STORE_ID


def register_style_callbacks(app, logger):
    # Add light/dark mode toggle callback
    clientside_callback(
        """
        (switchOn) => {
        document.documentElement.setAttribute('data-mantine-color-scheme', switchOn ? 'dark' : 'light');
        return window.dash_clientside.no_update
        }
        """,
        Output("color-scheme-switch", "id"),
        Input("color-scheme-switch", "checked"),
    )

    @app.callback(
        Output({"type": PLOT_TYPE, "index": ALL}, "figure", allow_duplicate=True),
        Output(THEME_STORE_ID, "data"),
        Input("color-scheme-switch", "checked"),
        prevent_initial_call=True,
    )
    def update_all_plots_theme(switch_on):
        """Triggers when the switch flips.

        It returns a list of 'Patches'—one for every plot found on the page.
        """
        # Ensure mantine_dark & mantine_light templates are registered
        dmc.add_figure_templates()
        template_name = "mantine_dark" if switch_on else "mantine_light"

        # Create a partial update (Patch) so we don't resend all the data
        theme_patch = Patch()
        # Pass the full template object because client-side Plotly may not
        # know the 'mantine_dark'/'mantine_light' string names.
        theme_patch["layout"]["template"] = pio.templates[template_name]

        # We must return a list of updates.
        # ctx.outputs_list is [ [plot_ids...], store_id ]
        plot_matches = ctx.outputs_list[0] if isinstance(ctx.outputs_list, list) else []

        # Ensure it's a list (it should be for ALL wildcards)
        # if not isinstance(plot_matches, list):
        #     plot_matches = []

        num_plots = len(plot_matches)

        return [theme_patch] * num_plots, template_name
