import os

from dash import dcc, html
import plotly.io as pio
import plotly.graph_objects as go

from ..styles import COLORS, FILTER_COLORS
from .cards import create_nav_item


brand_palette = [COLORS["primary"]] * 10
THEME = {
    "primaryColor": "arxiv_red",
    "colors": {
        "arxiv_red": brand_palette,
    },
    # Material 3 Expressive uses very rounded corners
    "defaultRadius": "xl",
    "white": COLORS["bg_light"],
    "black": COLORS["bg_dark"],
    # Customizing component defaults for that 'Expressive' feel
    "components": {
        "Card": {
            "defaultProps": {
                "padding": "xl",
                "shadow": "sm",
                # "withBorder": True,
            }
        },
        "TextInput": {
            "defaultProps": {
                "size": "md",
            }
        },
        "PasswordInput": {
            "defaultProps": {
                "size": "md",
            }
        },
        "Button": {
            "defaultProps": {
                # "fw": 600,
                "size": "md",
            }
        },
    },
}


def generate_css():
    """Generates CSS variables for light and dark themes."""
    light_css = f"""
:root[data-mantine-color-scheme="light"] {{
    --mantine-color-bg: {COLORS["bg_light"]};
    --mantine-color-body: {COLORS["bg_light"]};
    --mantine-color-text: {COLORS["bg_dark"]};
    --tarxiv-color-primary: {COLORS["primary"]};
    --tarxiv-card-1: {COLORS["card_light"]};
    --tarxiv-footer-bg: {COLORS["card_dark"]};
    --tarxiv-surface-1: {COLORS["vlight_gray"]};
    --tarxiv-surface-2: {COLORS["surface_light"]};
}}

"""
    #     light_css = f"""
    # [data-mantine-color-scheme="light"] {{
    #     --mantine-color-bg: {COLORS["bg_light"]};
    #     --mantine-color-body: {COLORS["bg_light"]};
    #     --mantine-color-text: {COLORS["bg_dark"]};
    #     --tarxiv-card-1: {COLORS["card_light"]};
    # }}

    # """

    dark_css = f"""
:root[data-mantine-color-scheme="dark"] {{
    --mantine-color-bg: {COLORS["bg_dark"]};
    --mantine-color-body: {COLORS["bg_dark"]};
    --mantine-color-text: {COLORS["bg_light"]};
    --tarxiv-color-primary: {COLORS["primary"]};
    --tarxiv-card-1: {COLORS["card_dark"]};
    --tarxiv-footer-bg: {COLORS["bg_dark"]};
    --tarxiv-surface-1: {COLORS["surface_dark"]};
    --tarxiv-surface-2: {COLORS["surface_dark"]};
}}

"""

    nav_hover = """
/* Only apply hover colors on devices with a mouse/pointer */
@media (hover: hover) {
    .nav-item-hover:hover {
        background-color: var(--mantine-color-bg);
        transform: scale(1.03);
        transition: transform 200ms ease;
    }

    /* Change the icon/text color on hover */
    .nav-item-hover:hover * {
        color: var(--mantine-color-indigo-6);
    }
}

/* Tactile feedback for mobile and desktop when clicking */
.nav-item-hover:active {
    transform: scale(0.95);
    transition: transform 50ms ease;
}

/* Ensure long words wrap instead of clipping */
.nav-text-wrap {
    white-space: normal;
    word-break: break-word;
    line-height: 1.1;
}

"""
    os.makedirs(
        # TODO JL: Two things
        # 1) Hardcoded path is not ideal - probably should be a config or 
        #    environment variable
        # 2) We should probably commit this file to the repo and only regenerate 
        #    it when styles.py changes, instead of regenerating on every app 
        #    start
        "tarxiv/dashboard/assets", exist_ok=True
    )  # TODO: Update if dashboard moves to another repo
    with open("tarxiv/dashboard/assets/theme.css", "w") as f:
        f.write(light_css)
        f.write(dark_css)
        f.write(nav_hover)
    return None


def get_theme_components() -> tuple[dict, html.Div]:
    """Returns the Theme and the Toggle Button for the rail."""
    return (
        THEME,
        # The Toggle Button (Unstyled to match your Rail)
        html.Div(
            create_nav_item(
                icon="line-md:moon-to-sunny-outline-transition",
                label="Light/Dark",
                is_active=False,
                id="theme-icon",
            ),
            id="color-scheme-toggle",
            style={"marginTop": "auto"},  # Pushes theme toggle to the very bottom
        ),
    )


def apply_theme(fig, theme_template):
    # If theme_template is just "light" or "dark", map it:
    if theme_template == "light":
        theme_template = "tarxiv_light"
    elif theme_template == "dark":
        theme_template = "tarxiv_dark"

    fig.update_layout(template=pio.templates[theme_template])
    return fig


def register_tarxiv_templates():
    # 1. Define the Dark Template
    dark_layout = go.layout.Template()
    dark_layout.layout = {
        "paper_bgcolor": "#1A1B1E",  # Matches Mantine Dark Default
        "plot_bgcolor": "#1A1B1E",
        # "font": {"color": "#C1C2C5", "family": "Arial"},
        "font": {"color": "#E1E2E5", "family": "Arial"},
        "xaxis": {
            "gridcolor": "#373A40",
            "linecolor": "#373A40",
            "zerolinecolor": "#373A40",
        },
        "yaxis": {
            "gridcolor": "#373A40",
            "linecolor": "#373A40",
            "zerolinecolor": "#373A40",
        },
        # This is where you inject your styles.py primary color
        # "colorway": [COLORS["primary"], "#2ecc71", "#e74c3c", "#f1c40f"],
        "colorway": ["#4C84C6", "#27ae60", "#c0392b", "#f39c12"],
    }
    pio.templates["tarxiv_dark"] = dark_layout

    # 2. Define the Light Template
    light_layout = go.layout.Template()
    light_layout.layout = {
        "paper_bgcolor": "#FEFEFE",
        "plot_bgcolor": "#ffffff",
        # "font": {"color": COLORS["secondary"], "family": "Arial"},
        "font": {"color": "#121617", "family": "Arial"},
        "xaxis": {
            "gridcolor": "#f1f3f5",
            "linecolor": "#dee2e6",
            "zerolinecolor": "#dee2e6",
        },
        "yaxis": {
            "gridcolor": "#f1f3f5",
            "linecolor": "#dee2e6",
            "zerolinecolor": "#dee2e6",
        },
        # "colorway": [COLORS["primary"], "#27ae60", "#c0392b", "#f39c12"],
        "colorway": ["#4C84C6", "#27ae60", "#c0392b", "#f39c12"],
    }
    pio.templates["tarxiv_light"] = light_layout


def get_filter_style(filter_name):
    """Returns marker color based on filter name from styles.py."""
    return FILTER_COLORS.get(filter_name, FILTER_COLORS["Unknown"])
