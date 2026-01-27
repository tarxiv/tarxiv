"""Dashboard components."""
from .plots import create_lightcurve_plot, create_sky_plot
from .cards import format_object_metadata, format_cone_search_results
from .search import create_search_by_id, create_cone_search, create_results_section, create_unified_search
from .auth import (
    create_navbar,
    create_profile_drawer,
    avatar_fallback,
    avatar_image,
)

__all__ = [
    "create_lightcurve_plot",
    "create_sky_plot",
    "format_object_metadata",
    "format_cone_search_results",
    "create_search_by_id",
    "create_cone_search",
    "create_results_section",
    "create_unified_search",
    "create_navbar",
    "create_profile_drawer",
    "avatar_fallback",
    "avatar_image",
]
