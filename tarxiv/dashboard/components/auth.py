"""Auth UI components for the dashboard."""

from dash import html
from ..styles import (
    AVATAR_STYLE,
    AVATAR_FALLBACK_STYLE,
)


def avatar_fallback(initials: str):
    """Simple fallback avatar badge."""
    return html.Div(
        # return dmc.Avatar(
        initials.upper()[:2],
        style=AVATAR_FALLBACK_STYLE,
    )


def avatar_image(src: str):
    """Return an avatar image element."""
    return html.Img(src=src, style=AVATAR_STYLE)
    # return dmc.Avatar(src=src, style=AVATAR_STYLE)
