"""Dashboard components."""

from .auth import (
    avatar_fallback,
    avatar_image,
)
from .plots import (
    create_lightcurve_plot,
)
from .cards import (
    format_object_metadata,
    format_cone_search_results,
    build_cone_result_cards_page,
    CONE_RESULTS_PAGE_SIZE,
    expressive_card,
    title_card,
    footer_card,
    create_message_banner,
)
from .object_view import (
    build_empty_search_state,
    build_key_facts,
    build_photometry_table,
)
from .theme_manager import (
    apply_theme,
    get_theme,
    register_tarxiv_templates,
    scheme_from_template,
)
from .cookies import (
    get_cookie_popup,
    COOKIE_DEFAULTS,
)

__all__ = [
    "avatar_fallback",
    "avatar_image",
    "create_lightcurve_plot",
    "format_object_metadata",
    "format_cone_search_results",
    "build_cone_result_cards_page",
    "CONE_RESULTS_PAGE_SIZE",
    "expressive_card",
    "title_card",
    "footer_card",
    "create_message_banner",
    "build_empty_search_state",
    "build_key_facts",
    "build_photometry_table",
    "apply_theme",
    "get_theme",
    "register_tarxiv_templates",
    "scheme_from_template",
    "get_cookie_popup",
    "COOKIE_DEFAULTS",
]
