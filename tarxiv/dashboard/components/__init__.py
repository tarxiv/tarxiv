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
)
from .theme_manager import (
    get_theme_components,
    apply_theme,
    get_filter_style,
    register_tarxiv_templates,
    PLOT_TYPE,
    THEME_STORE_ID,
)

from .search import (
    # create_search_by_id,
    # create_cone_search,
    create_results_section,
    # create_unified_search,
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
    # "create_search_by_id",
    # "create_cone_search",
    "create_results_section",
    # "create_unified_search",
    "get_theme_components",
    "apply_theme",
    "get_filter_style",
    "register_tarxiv_templates",
    "PLOT_TYPE",
    "THEME_STORE_ID",
]
