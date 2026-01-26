from dash import dcc
import dash_mantine_components as dmc
from dash_iconify import DashIconify

# 1. Constants for Pattern Matching
PLOT_TYPE = "themeable-plot"
THEME_STORE_ID = "theme-store"


def get_theme_components() -> tuple[dcc.Store, dmc.Switch]:
    """Returns the Store and the Switch for the layout."""
    return (
        dcc.Store(id=THEME_STORE_ID, storage_type="local", data="mantine_dark"),
        dmc.Switch(
            offLabel=DashIconify(
                icon="radix-icons:sun", width=15, color="var(--mantine-color-yellow-8)"
            ),
            onLabel=DashIconify(
                icon="radix-icons:moon", width=15, color="var(--mantine-color-yellow-6)"
            ),
            id="color-scheme-switch",
            persistence=True,
            color="gray",
            size="lg",
        ),
    )


def apply_theme(fig, theme_template):
    """Helper to apply the current theme to any Plotly figure."""
    fig.update_layout(template=theme_template)
    return fig
