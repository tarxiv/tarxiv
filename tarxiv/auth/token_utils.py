"""JWT utilities for TarXiv API authentication.

Tokens are signed with HS256 using the TARXIV_JWT_SECRET environment variable,
which must be present on both the API (signs) and dashboard (verifies) services.
"""

import os
import time
from typing import Any, Dict

import jwt

import jwt as _jwt

_ALGORITHM = "HS256"
_DEFAULT_TTL = 86400  # 24 hours


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
    return _jwt.encode(payload, _secret(), algorithm=_ALGORITHM)


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
    return _jwt.decode(raw, _secret(), algorithms=[_ALGORITHM])
