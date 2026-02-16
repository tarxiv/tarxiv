"""Dashboard components."""

from .plots import create_lightcurve_plot, create_sky_plot
from .cards import (
    format_object_metadata,
    format_cone_search_results,
    expressive_card,
    title_card,
    footer_card,
    create_nav_item,
    create_nav_link,
    create_message_banner,
)
from .theme_manager import (
    get_theme_components,
    apply_theme,
    get_filter_style,
    register_tarxiv_templates,
)
from .cookies import (
    get_cookie_popup,
    COOKIE_DEFAULTS,
)

__all__ = [
    "create_lightcurve_plot",
    "create_sky_plot",
    "format_object_metadata",
    "format_cone_search_results",
    "expressive_card",
    "title_card",
    "footer_card",
    "create_nav_item",
    "create_nav_link",
    "create_message_banner",
    "get_theme_components",
    "apply_theme",
    "get_filter_style",
    "register_tarxiv_templates",
    "get_cookie_popup",
    "COOKIE_DEFAULTS",
]
