"""ORCID OAuth helpers used by the dashboard."""

import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from pydantic import BaseModel, ConfigDict

from ..utils import TarxivModule

logger = logging.getLogger(__name__)

ORCID_AUTH_URL = os.environ.get(
    "ORCID_AUTH_URL", "https://sandbox.orcid.org/oauth/authorize"
)
ORCID_TOKEN_URL = os.environ.get(
    "ORCID_TOKEN_URL", "https://sandbox.orcid.org/oauth/token"
)
ORCID_API_BASE = os.environ.get("ORCID_API_BASE", "https://pub.sandbox.orcid.org/v3.0")
ORCID_SCOPE = os.environ.get("ORCID_SCOPE", "/authenticate")


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
    # email: str = ""
    email: Optional[str] = None
    username: Optional[str] = None
    nickname: Optional[str] = None
    picture_url: Optional[str] = None
    forename: Optional[str] = None
    surname: Optional[str] = None
    institution: Optional[str] = None
    bio: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class ORCIDAuthClient(TarxivModule):
    """Helper for ORCID OAuth authentication."""

    def __init__(self, script_name: str, reporting_mode: str, debug: bool = False):
        super().__init__(
            script_name=script_name,
            module="orcid_client",
            reporting_mode=reporting_mode,
            debug=debug,
        )

    def serialize_profile(
        self, user_row: Dict[str, Any], fallback_email: str = ""
    ) -> Dict[str, Any]:
        """Normalize a profile payload for UI storage."""
        data = dict(user_row or {})
        if fallback_email and not data.get("email"):
            data["email"] = fallback_email
        profile = ProfileView.model_validate(data)
        return profile.model_dump()

    def build_orcid_authorize_url(self, state: str) -> str:
        """Return an ORCID authorize URL for the current environment."""
        status = {"status": "building ORCID authorize URL"}
        self.logger.info(status, extra=status)

        client_id = self._require_env("ORCID_CLIENT_ID")
        # redirect_uri = self._require_env("ORCID_REDIRECT_URI")
        redirect_uri = self._require_env("TARXIV_ORCID_REDIRECT_URI")

        params = {
            "client_id": client_id,
            "response_type": "code",
            "scope": ORCID_SCOPE,
            "redirect_uri": redirect_uri,
            "state": state,
        }

        status = {
            "status": f"built ORCID authorize URL: {ORCID_AUTH_URL} with params: {params}"
        }
        self.logger.info(status, extra=status)

        return f"{ORCID_AUTH_URL}?{urlencode(params)}"

    def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange an authorization code for an ORCID access token."""
        status = {"status": "exchanging ORCID code for token"}
        self.logger.info(status, extra=status)

        client_id = self._require_env("ORCID_CLIENT_ID")
        client_secret = self._require_env("ORCID_CLIENT_SECRET")
        # redirect_uri = self._require_env("ORCID_REDIRECT_URI")
        redirect_uri = self._require_env("TARXIV_ORCID_REDIRECT_URI")
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

        status = {
            "status": f"ORCID token exchange response code: {response.status_code}"
        }
        self.logger.info(status, extra=status)

        if not response.ok:
            raise RuntimeError(f"ORCID token exchange failed: {response.text}")
        return response.json()

    def fetch_orcid_profile(self, orcid_id: str, access_token: str) -> Dict[str, Any]:
        """Fetch the ORCID person record for the authenticated user."""
        status = {"status": f"fetching ORCID profile for ID: {orcid_id}"}
        self.logger.info(status, extra=status)

        url = f"{ORCID_API_BASE}/{orcid_id}/person"
        response = requests.get(
            url,
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {access_token}",
            },
            timeout=20,
        )

        status = {
            "status": f"fetched ORCID profile with response code: {response.status_code}"
        }
        self.logger.info(status, extra=status)

        if not response.ok:
            logger.warning("Failed to fetch ORCID profile: %s", response.text)
            return {}
        return response.json()

    def _require_env(self, name: str) -> str:
        value = os.environ.get(name)
        if not value:
            raise RuntimeError(f"Missing {name} in environment.")
        return value

    def _extract_email(self, person: Dict[str, Any]) -> Optional[str]:
        emails = (person.get("emails") or {}).get("email") or []
        primary = next(
            (item.get("email") for item in emails if item.get("primary")), None
        )
        return primary or (emails[0].get("email") if emails else None)

    def _extract_name(self, person: Dict[str, Any]) -> Dict[str, Optional[str]]:
        name = person.get("name") or {}
        given = (name.get("given-names") or {}).get("value")
        family = (name.get("family-name") or {}).get("value")
        credit = (name.get("credit-name") or {}).get("value")
        return {"given": given, "family": family, "credit": credit}

    def normalize_orcid_profile(
        self, orcid_id: str, token_data: Dict[str, Any], person: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a profile payload from ORCID API responses."""
        name = self._extract_name(person)
        email = self._extract_email(person)
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
        return self.serialize_profile(profile, fallback_email=email or "")

    def complete_orcid_login(self, code: str) -> Dict[str, Any]:
        """Finalize ORCID login using the authorization code."""
        token_data = self.exchange_code_for_token(code)
        orcid_id = token_data.get("orcid")
        access_token = token_data.get("access_token")
        if not orcid_id or not access_token:
            raise RuntimeError("ORCID login did not return a user identifier.")
        person = self.fetch_orcid_profile(orcid_id, access_token)
        profile = self.normalize_orcid_profile(orcid_id, token_data, person)
        return {
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "user": profile,
            "provider": "orcid",
        }
