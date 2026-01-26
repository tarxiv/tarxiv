"""Auth helpers for TarXiv."""

from .supabase_client import (
    ensure_user_record,
    get_supabase_client,
    login_with_password,
    register_user,
    serialize_profile,
)

__all__ = [
    "ensure_user_record",
    "get_supabase_client",
    "login_with_password",
    "register_user",
    "serialize_profile",
]
