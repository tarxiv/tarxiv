"""Thin Supabase client wrapper used by the dashboard."""
from __future__ import annotations

import os
from typing import Any, Dict, Optional
import logging

from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

try:
    from supabase import Client, create_client
except ImportError as exc:  # pragma: no cover - provides clearer error
    raise ImportError(
        "The supabase package is required. Install with `pip install supabase`."
    ) from exc


def get_supabase_client(api_key: Optional[str] = None) -> Client:
    """Create a Supabase client from environment variables."""
    url = (
        os.environ.get("SUPABASE_API_EXTERNAL_URL")
        or os.environ.get("SUPABASE_URL")
    )
    key = api_key or os.environ.get("SUPABASE_ANON_KEY")

    if not url or not key:
        raise RuntimeError(
            "Supabase configuration missing. Set SUPABASE_API_EXTERNAL_URL "
            "and SUPABASE_ANON_KEY in your environment."
        )

    return create_client(url, key)


class ProfileRow(BaseModel):
    id: Optional[str] = None
    provider_user_id: Optional[str] = None
    email: Optional[str] = None
    username: Optional[str] = None
    nickname: Optional[str] = None
    picture_url: Optional[str] = None
    forename: Optional[str] = None
    surname: Optional[str] = None
    institution: Optional[str] = None
    bio: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ProfileView(BaseModel):
    id: Optional[str] = None
    email: str = ""
    username: Optional[str] = None
    nickname: Optional[str] = None
    picture_url: Optional[str] = None
    forename: Optional[str] = None
    surname: Optional[str] = None
    institution: Optional[str] = None
    bio: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


def serialize_profile(user_row: Dict[str, Any], fallback_email: str = "") -> Dict[str, Any]:
    """Normalize a profile payload for UI storage."""
    data = dict(user_row or {})
    if fallback_email and not data.get("email"):
        data["email"] = fallback_email
    profile = ProfileView.model_validate(data)
    return profile.model_dump()


def ensure_user_record(client: Client, user: Any) -> Dict[str, Any]:
    """Upsert a row in public.users for the authenticated user."""
    print(f"Ensuring user record for user: {user}")
    metadata = getattr(user, "user_metadata", {}) or {}
    payload = ProfileRow(
        id=user.id,
        provider_user_id=user.id,
        email=getattr(user, "email", None),
        username=metadata.get("preferred_username") or metadata.get("user_name"),
        nickname=metadata.get("full_name") or metadata.get("name"),
        forename=metadata.get("first_name"),
        surname=metadata.get("last_name"),
        picture_url=metadata.get("avatar_url") or metadata.get("picture"),
        bio=metadata.get("bio"),
        institution=metadata.get("institution"),
    ).model_dump(exclude_none=True)

    response = (
        client.table("users")
        .upsert(payload, on_conflict="id")
        .execute()
    )
    response_data = getattr(response, "data", None)
    if isinstance(response_data, list):
        if not response_data:
            raise RuntimeError("Failed to upsert user record in Supabase.")
        data = response_data[0] if len(response_data) == 1 else response_data[-1]
    elif isinstance(response_data, dict):
        data = response_data
    else:
        data = payload
    print(f"Supabase upsert response: {response}")

    print(f"Supabase user record: {data}")
    print("finishing ensure_user_record")
    return serialize_profile(data, fallback_email=payload.get("email", ""))


def login_with_password(email: str, password: str, client: Optional[Client] = None) -> Dict[str, Any]:
    """Sign in a user and return session metadata for the UI."""
    client = client or get_supabase_client()

    auth_response = client.auth.sign_in_with_password(
        {"email": email, "password": password}
    )
    session = getattr(auth_response, "session", None)
    user = getattr(auth_response, "user", None)
    logger.debug(f"Supabase login response: {auth_response}")

    if not session or not user:
        raise RuntimeError("Login failed: missing session or user from Supabase.")

    profile = ensure_user_record(client, user)
    return {
        "access_token": session.access_token,
        "refresh_token": session.refresh_token,
        "user": profile,
    }


def register_user(email: str, password: str, username: Optional[str] = None) -> Dict[str, Any]:
    """Register a user (and immediately sign them in)."""
    client = get_supabase_client()

    options = {}
    metadata: Dict[str, Any] = {}
    if username:
        metadata["preferred_username"] = username
        metadata["full_name"] = username
    if metadata:
        options["data"] = metadata

    payload: Dict[str, Any] = {"email": email, "password": password}
    if options:
        payload["options"] = options

    response = client.auth.sign_up(payload)
    if getattr(response, "user", None) is None:
        raise RuntimeError("Sign up failed. Check email configuration or duplicate accounts.")

    # Automatically log them in to reuse the same session shape as the login flow
    return login_with_password(email, password, client=client)
