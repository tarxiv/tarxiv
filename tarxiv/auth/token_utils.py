"""JWT utilities for TarXiv API authentication.

Tokens are signed with HS256 using the TARXIV_JWT_SECRET environment variable,
which must be present on both the API (signs) and dashboard (verifies) services.
"""

import os
import time
from typing import Any, Dict

from flask import Request
import jwt as pyjwt

_ALGORITHM = "HS256"
_DEFAULT_TTL = 86400  # 24 hours


class TokenStatus:
    """Constants for token validation results."""

    VALID = "valid"
    EXPIRED = "expired"
    INVALID = "invalid"


def _secret() -> str:
    secret = os.environ.get("TARXIV_JWT_SECRET")
    if not secret:
        raise RuntimeError("TARXIV_JWT_SECRET is not set in the environment.")
    return secret


def sign_token(
    sub: str,
    provider: str,
    profile: Dict[str, Any],
    ttl: int = _DEFAULT_TTL,
) -> str:
    """Issue a signed TarXiv JWT.

    Parameters
    ----------
    sub:
        Stable provider-issued user identifier (e.g. ORCID iD).
    provider:
        Identity provider name (e.g. ``"orcid"``).
    profile:
        Normalised user profile dict (ProfileView fields).
    ttl:
        Token lifetime in seconds. Defaults to 24 hours.

    Returns
    -------
    str
        Encoded JWT string.
    """
    now = int(time.time())
    payload = {
        "sub": sub,
        "provider": provider,
        "iat": now,
        "exp": now + ttl,
        "profile": profile,
    }
    return pyjwt.encode(payload, _secret(), algorithm=_ALGORITHM)


def get_jwt_from_request(req: Request) -> str | None:
    """Extract a JWT from the Authorization header or cookies in a Flask request."""
    auth_header = req.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.removeprefix("Bearer ").strip()

    cookie_token = req.cookies.get("tarxiv_token")
    if cookie_token:
        return cookie_token.strip()

    return None


def verify_token(token: str) -> Dict[str, Any]:
    """Decode and verify a TarXiv JWT.

    Parameters
    ----------
    token:
        Raw JWT string. May include a ``Bearer `` prefix.

    Returns
    -------
    dict
        Decoded payload including ``sub``, ``provider``, ``profile``,
        ``iat``, and ``exp``.

    Raises
    ------
    jwt.ExpiredSignatureError
        If the token has expired.
    jwt.InvalidTokenError
        If the signature is invalid or the token is malformed.
    """
    raw = token.removeprefix("Bearer ").strip()
    return pyjwt.decode(raw, _secret(), algorithms=[_ALGORITHM])


def get_authenticated_user(
    req: Request | None = None,
    jwt_token: str | None = None,
) -> Dict[str, Any] | None:
    """Extract and validate the active user from the request context.

    Checks for authentication via:
    1. HTTP Authorization header (Bearer token)
    2. HttpOnly cookie (tarxiv_token)
    3. Direct JWT input (jwt_token parameter)

    Parameters
    ----------
    req: Request | None
        The Flask request object, used to extract headers and cookies.
    jwt_token: str | None
        An optional JWT string to validate directly.

    Returns
    -------
    dict | None
        The user's profile dict if authenticated and valid, else None.
    """
    token = jwt_token or (get_jwt_from_request(req) if req else None)

    if not token:
        return None

    try:
        payload = verify_token(token)
        return payload.get("profile")
    except Exception:
        return None


def validate_token(jwt_token: str | None) -> Dict[str, Any]:
    """Validate a JWT and return structured status.

    Distinguishes between expired, invalid, and valid tokens.

    Parameters
    ----------
    jwt_token: str | None
        Raw JWT string to validate.

    Returns
    -------
    dict
        {
            "status": "valid" | "expired" | "invalid",
            "profile": {...} if valid, else None,
            "error": error message if not valid, else None
        }
    """
    if not jwt_token:
        return {
            "status": TokenStatus.INVALID,
            "profile": None,
            "error": "No token provided",
        }

    try:
        payload = verify_token(jwt_token)
        return {
            "status": TokenStatus.VALID,
            "profile": payload.get("profile"),
            "error": None,
        }
    except pyjwt.ExpiredSignatureError as e:
        return {
            "status": TokenStatus.EXPIRED,
            "profile": None,
            "error": f"Token expired: {str(e)}",
        }
    except (pyjwt.InvalidTokenError, pyjwt.DecodeError) as e:
        return {
            "status": TokenStatus.INVALID,
            "profile": None,
            "error": f"Invalid token: {str(e)}",
        }
    except Exception as e:
        return {
            "status": TokenStatus.INVALID,
            "profile": None,
            "error": f"Token verification failed: {str(e)}",
        }
