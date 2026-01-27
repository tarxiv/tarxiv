"""ORCID OAuth helpers used by the dashboard."""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

ORCID_AUTH_URL = os.environ.get("ORCID_AUTH_URL", "https://orcid.org/oauth/authorize")
ORCID_TOKEN_URL = os.environ.get("ORCID_TOKEN_URL", "https://orcid.org/oauth/token")
ORCID_API_BASE = os.environ.get("ORCID_API_BASE", "https://pub.orcid.org/v3.0")
ORCID_SCOPE = os.environ.get("ORCID_SCOPE", "/authenticate")


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing {name} in environment.")
    return value


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
    provider_user_id: Optional[str] = None
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


def build_orcid_authorize_url(state: str) -> str:
    """Return an ORCID authorize URL for the current environment."""
    client_id = _require_env("ORCID_CLIENT_ID")
    redirect_uri = _require_env("ORCID_REDIRECT_URI")
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": ORCID_SCOPE,
        "redirect_uri": redirect_uri,
        "state": state,
    }
    return f"{ORCID_AUTH_URL}?{urlencode(params)}"


def exchange_code_for_token(code: str) -> Dict[str, Any]:
    """Exchange an authorization code for an ORCID access token."""
    client_id = _require_env("ORCID_CLIENT_ID")
    client_secret = _require_env("ORCID_CLIENT_SECRET")
    redirect_uri = _require_env("ORCID_REDIRECT_URI")
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
    }
    response = requests.post(
        ORCID_TOKEN_URL,
        data=payload,
        headers={"Accept": "application/json"},
        timeout=20,
    )
    if not response.ok:
        raise RuntimeError(f"ORCID token exchange failed: {response.text}")
    return response.json()


def fetch_orcid_profile(orcid_id: str, access_token: str) -> Dict[str, Any]:
    """Fetch the ORCID person record for the authenticated user."""
    url = f"{ORCID_API_BASE}/{orcid_id}/person"
    response = requests.get(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {access_token}",
        },
        timeout=20,
    )
    if not response.ok:
        logger.warning("Failed to fetch ORCID profile: %s", response.text)
        return {}
    return response.json()


def _extract_email(person: Dict[str, Any]) -> Optional[str]:
    emails = (person.get("emails") or {}).get("email") or []
    primary = next((item.get("email") for item in emails if item.get("primary")), None)
    return primary or (emails[0].get("email") if emails else None)


def _extract_name(person: Dict[str, Any]) -> Dict[str, Optional[str]]:
    name = person.get("name") or {}
    given = (name.get("given-names") or {}).get("value")
    family = (name.get("family-name") or {}).get("value")
    credit = (name.get("credit-name") or {}).get("value")
    return {"given": given, "family": family, "credit": credit}


def normalize_orcid_profile(orcid_id: str, token_data: Dict[str, Any], person: Dict[str, Any]) -> Dict[str, Any]:
    """Create a profile payload from ORCID API responses."""
    name = _extract_name(person)
    email = _extract_email(person)
    display_name = name["credit"] or token_data.get("name") or ""
    profile = ProfileRow(
        id=orcid_id,
        provider_user_id=orcid_id,
        email=email,
        username=display_name or None,
        nickname=display_name or None,
        forename=name["given"],
        surname=name["family"],
        bio=(person.get("biography") or {}).get("content"),
    ).model_dump(exclude_none=True)
    return serialize_profile(profile, fallback_email=email or "")


def complete_orcid_login(code: str) -> Dict[str, Any]:
    """Finalize ORCID login using the authorization code."""
    token_data = exchange_code_for_token(code)
    orcid_id = token_data.get("orcid")
    access_token = token_data.get("access_token")
    if not orcid_id or not access_token:
        raise RuntimeError("ORCID login did not return a user identifier.")
    person = fetch_orcid_profile(orcid_id, access_token)
    profile = normalize_orcid_profile(orcid_id, token_data, person)
    return {
        "access_token": access_token,
        "refresh_token": token_data.get("refresh_token"),
        "user": profile,
        "provider": "orcid",
    }
