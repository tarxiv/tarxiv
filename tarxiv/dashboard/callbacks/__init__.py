"""Dashboard callbacks."""
from .search_callbacks import register_search_callbacks
from .auth_callbacks import register_auth_callbacks

__all__ = ["register_search_callbacks", "register_auth_callbacks"]
