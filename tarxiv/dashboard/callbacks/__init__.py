"""Dashboard callbacks."""

from .search_callbacks import register_search_callbacks
from .style_callbacks import register_style_callbacks
from .plotting_callbacks import register_plotting_callbacks

__all__ = [
    "register_search_callbacks",
    "register_style_callbacks",
    "register_plotting_callbacks",
]
