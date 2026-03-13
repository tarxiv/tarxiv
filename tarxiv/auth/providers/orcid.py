"""ORCID OAuth provider for the TarXiv auth system.

Implements the AuthProvider protocol used by ``tarxiv/api.py``::

    build_authorize_url(state) -> str
    complete_login(code)       -> dict   (normalised profile)

Environment variables required on the API service:
    ORCID_CLIENT_ID
    ORCID_CLIENT_SECRET
    TARXIV_ORCID_REDIRECT_URI   — must point to <API_URL>/auth/orcid/callback
    ORCID_AUTH_URL              — optional, defaults to ORCID sandbox
    ORCID_TOKEN_URL             — optional
    ORCID_API_BASE              — optional
    ORCID_SCOPE                 — optional
"""

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, ConfigDict

logger = logging.getLogger(__name__)

# TODO: Move these to .env file
ORCID_AUTH_URL = os.environ.get(
    "ORCID_AUTH_URL", "https://sandbox.orcid.org/oauth/authorize"
)
ORCID_TOKEN_URL = os.environ.get(
    "ORCID_TOKEN_URL", "https://sandbox.orcid.org/oauth/token"
)
ORCID_API_BASE = os.environ.get("ORCID_API_BASE", "https://pub.sandbox.orcid.org/v3.0")
ORCID_SCOPE = os.environ.get("ORCID_SCOPE", "/authenticate")


class _ProfileRow(BaseModel):
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


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def build_authorize_url(state: str) -> str:
    """Return the ORCID OAuth authorization URL for the given CSRF state."""
    params = {
        "client_id": _require_env("ORCID_CLIENT_ID"),
        "response_type": "code",
        "scope": ORCID_SCOPE,
        "redirect_uri": _require_env("TARXIV_ORCID_REDIRECT_URI"),
        # "redirect_uri": f"{_require_env('VIRTUAL_HOST').rstrip('/')}/auth/orcid/callback",
        "state": state,
    }
    return f"{ORCID_AUTH_URL}?{urlencode(params)}"


def _exchange_code(code: str) -> Dict[str, Any]:
    payload = {
        "client_id": _require_env("ORCID_CLIENT_ID"),
        "client_secret": _require_env("ORCID_CLIENT_SECRET"),
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": _require_env("TARXIV_ORCID_REDIRECT_URI"),
        # "redirect_uri": f"{_require_env('VIRTUAL_HOST').rstrip('/')}/auth/orcid/callback",
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


def _fetch_person(orcid_id: str, access_token: str) -> Dict[str, Any]:
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
    return {
        "given": (name.get("given-names") or {}).get("value"),
        "family": (name.get("family-name") or {}).get("value"),
        "credit": (name.get("credit-name") or {}).get("value"),
    }


def complete_login(code: str) -> Dict[str, Any]:
    """Exchange an authorization code for a normalised user profile.

    Returns
    -------
    dict
        Keys: ``sub`` (ORCID iD), ``provider`` (``"orcid"``), ``profile``
        (normalised ProfileRow dict).
    """
    token_data = _exchange_code(code)
    orcid_id = token_data.get("orcid")
    access_token = token_data.get("access_token")
    if not orcid_id or not access_token:
        raise RuntimeError("ORCID login did not return a user identifier.")

    person = _fetch_person(orcid_id, access_token)
    name = _extract_name(person)
    email = _extract_email(person)
    display_name = name["credit"] or token_data.get("name") or ""

    profile = _ProfileRow(
        id=orcid_id,
        provider_user_id=orcid_id,
        email=email,
        username=display_name or None,
        nickname=display_name or None,
        forename=name["given"],
        surname=name["family"],
        bio=(person.get("biography") or {}).get("content"),
    ).model_dump(exclude_none=True)

    return {
        "sub": orcid_id,
        "provider": "orcid",
        "profile": profile,
    }
