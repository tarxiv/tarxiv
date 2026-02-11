"""Dashboard callbacks."""

from .style_callbacks import register_style_callbacks
from .plotting_callbacks import register_plotting_callbacks

__all__ = [
    "register_style_callbacks",
    "register_plotting_callbacks",
]
