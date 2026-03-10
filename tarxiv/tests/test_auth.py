"""Tests for TarXiv authentication: token_utils, ORCID provider, and API auth routes.

Structure
---------
TestSignToken       — sign_token() emits valid JWTs with the expected claims
TestVerifyToken     — verify_token() round-trips correctly and rejects bad tokens
TestBuildAuthorizeUrl — ORCID provider URL construction
TestCompleteLogin   — ORCID code exchange and profile normalisation (HTTP mocked)
TestAuthLogin       — GET /auth/<provider>/login route
TestAuthCallback    — GET /auth/<provider>/callback route
TestCheckToken      — API.check_token() boolean gate used by protected endpoints
"""

import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import jwt as _pyjwt
import pytest
from unittest.mock import MagicMock

import tarxiv.auth.providers.orcid as orcid_provider
from tarxiv.api import API
from tarxiv.auth.token_utils import sign_token, verify_token
import os

# ─── Constants ───────────────────────────────────────────────────────────────

_TEST_JWT_SECRET = "test-jwt-secret-for-auth-tests-32b"
_TEST_DASHBOARD_URL = "http://localhost:8050"

# Realistic ORCID API responses used across multiple tests
ORCID_TOKEN_RESPONSE = {
    "access_token": "test-access-token-abc123",
    "orcid": "0000-0002-1825-0097",
    "name": "Ada Lovelace",
    "token_type": "bearer",
    "scope": "/authenticate",
}

ORCID_PERSON_RESPONSE = {
    "name": {
        "given-names": {"value": "Ada"},
        "family-name": {"value": "Lovelace"},
        "credit-name": {"value": "A. Lovelace"},
    },
    "emails": {
        "email": [{"email": "ada@example.com", "primary": True, "verified": True}]
    },
    "biography": {"content": "First programmer."},
}


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _make_http_response(json_data=None, status=200):
    """Minimal mock of a requests.Response object."""
    m = MagicMock()
    m.ok = status < 400
    m.status_code = status
    m.json.return_value = json_data or {}
    m.text = str(json_data)
    return m


def _token_from_location(location: str) -> str:
    """Extract the raw JWT from a redirect Location URL containing ?token=..."""
    params = parse_qs(urlparse(location).query)
    return params["token"][0]


class MockTarxivModule:
    """Mirrors test_api.MockTarxivModule — prevents file I/O during fixture setup."""

    def __init__(self, *args, **kwargs):
        self.module = "mock tarxiv module"
        self.config_dir = os.environ.get(
            "TARXIV_CONFIG_DIR", os.path.join(os.path.dirname(__file__), "../aux")
        )
        self.config_file = os.path.join(self.config_dir, "config.yml")
        self.config = {"log_dir": None, "api_port": 5000}
        self.logger = MagicMock()
        self.debug = False


# ─── Shared fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def jwt_secret(monkeypatch):
    """Set TARXIV_JWT_SECRET for the duration of the test."""
    monkeypatch.setenv("TARXIV_JWT_SECRET", _TEST_JWT_SECRET)
    return _TEST_JWT_SECRET


@pytest.fixture
def valid_profile():
    return {
        "id": "0000-0002-1825-0097",
        "provider_user_id": "0000-0002-1825-0097",
        "email": "ada@example.com",
        "username": "Ada Lovelace",
        "forename": "Ada",
        "surname": "Lovelace",
    }


@pytest.fixture
def mock_api(monkeypatch, tmp_path, jwt_secret):
    """API instance with mocked DB, TarxivModule, JWT secret and dashboard URL."""
    monkeypatch.setenv("TARXIV_DASHBOARD_URL", _TEST_DASHBOARD_URL)
    monkeypatch.setattr(
        "tarxiv.database.TarxivDB.__init__", lambda self, *args, **kwargs: None
    )
    monkeypatch.setattr("tarxiv.utils.TarxivModule.__init__", MockTarxivModule.__init__)
    api = API("mock", str(tmp_path))
    api.txv_db = MagicMock()
    return api


@pytest.fixture
def mock_orcid_provider(monkeypatch, valid_profile):
    """Replace tarxiv.api.PROVIDERS with a controllable mock ORCID provider."""
    provider = MagicMock()
    provider.build_authorize_url.return_value = (
        "https://sandbox.orcid.org/oauth/authorize?client_id=test&state=teststate"
    )
    provider.complete_login.return_value = {
        "sub": "0000-0002-1825-0097",
        "provider": "orcid",
        "profile": valid_profile,
    }
    monkeypatch.setattr("tarxiv.api.PROVIDERS", {"orcid": provider})
    return provider


@pytest.fixture
def orcid_env(monkeypatch):
    """Set all ORCID environment variables and patch module-level URL constants."""
    monkeypatch.setenv("ORCID_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("ORCID_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv(
        "TARXIV_ORCID_REDIRECT_URI", "http://localhost:9001/auth/orcid/callback"
    )
    # These are read at import time, so we patch the module attributes directly
    monkeypatch.setattr(
        orcid_provider, "ORCID_AUTH_URL", "https://sandbox.orcid.org/oauth/authorize"
    )
    monkeypatch.setattr(
        orcid_provider, "ORCID_TOKEN_URL", "https://sandbox.orcid.org/oauth/token"
    )
    monkeypatch.setattr(
        orcid_provider, "ORCID_API_BASE", "https://pub.sandbox.orcid.org/v3.0"
    )
    monkeypatch.setattr(orcid_provider, "ORCID_SCOPE", "/authenticate")


# ─── sign_token ──────────────────────────────────────────────────────────────


@pytest.mark.auth
class TestSignToken:
    def test_sign_token_basic(self, jwt_secret, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        payload = _pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert payload["sub"] == "test-sub"
        assert payload["provider"] == "orcid"
        assert "iat" in payload
        assert "exp" in payload
        assert payload["profile"] == valid_profile

    def test_sign_token_default_ttl_is_24h(self, jwt_secret, valid_profile):
        token = sign_token("sub", "orcid", valid_profile)
        payload = _pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert 86390 <= payload["exp"] - payload["iat"] <= 86410

    def test_sign_token_custom_ttl(self, jwt_secret, valid_profile):
        token = sign_token("sub", "orcid", valid_profile, ttl=3600)
        payload = _pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert 3590 <= payload["exp"] - payload["iat"] <= 3610

    def test_sign_token_embeds_full_profile(self, jwt_secret, valid_profile):
        token = sign_token("sub", "orcid", valid_profile)
        payload = _pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert payload["profile"]["email"] == valid_profile["email"]
        assert payload["profile"]["forename"] == valid_profile["forename"]
        assert payload["profile"]["surname"] == valid_profile["surname"]

    def test_sign_token_missing_secret_raises(self, monkeypatch, valid_profile):
        monkeypatch.delenv("TARXIV_JWT_SECRET", raising=False)
        with pytest.raises(RuntimeError, match="TARXIV_JWT_SECRET"):
            sign_token("sub", "orcid", valid_profile)


# ─── verify_token ────────────────────────────────────────────────────────────


@pytest.mark.auth
class TestVerifyToken:
    def test_verify_token_round_trip(self, jwt_secret, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        payload = verify_token(token)
        assert payload["sub"] == "test-sub"
        assert payload["provider"] == "orcid"
        assert payload["profile"] == valid_profile

    def test_verify_token_strips_bearer_prefix(self, jwt_secret, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        payload = verify_token(f"Bearer {token}")
        assert payload["sub"] == "test-sub"

    def test_verify_token_preserves_timestamps(self, jwt_secret, valid_profile):
        before = int(time.time())
        token = sign_token("test-sub", "orcid", valid_profile)
        payload = verify_token(token)
        assert before <= payload["iat"] <= before + 2
        assert payload["exp"] == payload["iat"] + 86400

    def test_verify_token_expired_raises(self, jwt_secret, valid_profile):
        # ttl=-1 produces exp = now - 1, which is immediately expired
        token = sign_token("test-sub", "orcid", valid_profile, ttl=-1)
        with pytest.raises(_pyjwt.ExpiredSignatureError):
            verify_token(token)

    def test_verify_token_tampered_signature_raises(self, jwt_secret, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        header, payload_b64, _ = token.split(".")
        tampered = f"{header}.{payload_b64}.invalidsignatureXXX"
        with pytest.raises(_pyjwt.InvalidTokenError):
            verify_token(tampered)

    def test_verify_token_tampered_payload_raises(self, jwt_secret, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        header, payload_b64, sig = token.split(".")
        # Decode, modify sub, re-encode without re-signing
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        data["sub"] = "evil-user"
        new_b64 = (
            base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
        )
        with pytest.raises(_pyjwt.InvalidTokenError):
            verify_token(f"{header}.{new_b64}.{sig}")

    def test_verify_token_garbage_string_raises(self, jwt_secret):
        with pytest.raises(_pyjwt.InvalidTokenError):
            verify_token("not-a-jwt-at-all")

    def test_verify_token_missing_secret_raises(self, monkeypatch, valid_profile):
        monkeypatch.setenv("TARXIV_JWT_SECRET", "sign-secret-long-enough-32-bytes!")
        token = sign_token("sub", "orcid", valid_profile)
        monkeypatch.delenv("TARXIV_JWT_SECRET")
        with pytest.raises(RuntimeError, match="TARXIV_JWT_SECRET"):
            verify_token(token)

    def test_verify_token_wrong_secret_raises(self, monkeypatch, valid_profile):
        monkeypatch.setenv("TARXIV_JWT_SECRET", "secret-aaaaaaaaaaaaaaaaaa-32-bytes")
        token = sign_token("sub", "orcid", valid_profile)
        monkeypatch.setenv("TARXIV_JWT_SECRET", "secret-bbbbbbbbbbbbbbbbbbb-32-bytes")
        with pytest.raises(_pyjwt.InvalidSignatureError):
            verify_token(token)


# ─── providers/orcid.py: build_authorize_url ─────────────────────────────────


@pytest.mark.auth
class TestBuildAuthorizeUrl:
    def test_url_starts_with_auth_base(self, orcid_env):
        url = orcid_provider.build_authorize_url("my-state")
        assert url.startswith("https://sandbox.orcid.org/oauth/authorize")

    def test_includes_client_id(self, orcid_env):
        url = orcid_provider.build_authorize_url("my-state")
        assert "client_id=test-client-id" in url

    def test_includes_redirect_uri(self, orcid_env):
        url = orcid_provider.build_authorize_url("my-state")
        assert "redirect_uri=" in url
        assert "localhost" in url  # URL-encoded redirect_uri contains localhost

    def test_includes_state(self, orcid_env):
        url = orcid_provider.build_authorize_url("abc123")
        assert "state=abc123" in url

    def test_includes_scope(self, orcid_env):
        url = orcid_provider.build_authorize_url("s")
        assert "scope=" in url

    def test_missing_client_id_raises(self, monkeypatch, orcid_env):
        monkeypatch.delenv("ORCID_CLIENT_ID")
        with pytest.raises(RuntimeError, match="ORCID_CLIENT_ID"):
            orcid_provider.build_authorize_url("state")

    def test_missing_redirect_uri_raises(self, monkeypatch, orcid_env):
        monkeypatch.delenv("TARXIV_ORCID_REDIRECT_URI")
        with pytest.raises(RuntimeError, match="TARXIV_ORCID_REDIRECT_URI"):
            orcid_provider.build_authorize_url("state")


# ─── providers/orcid.py: complete_login ──────────────────────────────────────


@pytest.mark.auth
class TestCompleteLogin:
    def _setup_mocks(self, monkeypatch, token_response=None, person_response=None):
        mock_post = MagicMock(
            return_value=_make_http_response(token_response or ORCID_TOKEN_RESPONSE)
        )
        mock_get = MagicMock(
            return_value=_make_http_response(person_response or ORCID_PERSON_RESPONSE)
        )
        monkeypatch.setattr(orcid_provider.requests, "post", mock_post)
        monkeypatch.setattr(orcid_provider.requests, "get", mock_get)
        return mock_post, mock_get

    def test_success_returns_expected_keys(self, monkeypatch, orcid_env):
        self._setup_mocks(monkeypatch)
        result = orcid_provider.complete_login("test-code")
        assert set(result.keys()) == {"sub", "provider", "profile"}

    def test_sub_matches_orcid_id(self, monkeypatch, orcid_env):
        self._setup_mocks(monkeypatch)
        result = orcid_provider.complete_login("test-code")
        assert result["sub"] == "0000-0002-1825-0097"

    def test_provider_field_is_orcid(self, monkeypatch, orcid_env):
        self._setup_mocks(monkeypatch)
        result = orcid_provider.complete_login("test-code")
        assert result["provider"] == "orcid"

    def test_profile_contains_normalised_fields(self, monkeypatch, orcid_env):
        self._setup_mocks(monkeypatch)
        result = orcid_provider.complete_login("test-code")
        profile = result["profile"]
        assert profile["forename"] == "Ada"
        assert profile["surname"] == "Lovelace"
        assert profile["email"] == "ada@example.com"

    def test_token_endpoint_receives_code_and_credentials(self, monkeypatch, orcid_env):
        mock_post, _ = self._setup_mocks(monkeypatch)
        orcid_provider.complete_login("my-auth-code")
        data = mock_post.call_args.kwargs["data"]
        assert data["code"] == "my-auth-code"
        assert data["grant_type"] == "authorization_code"
        assert data["client_id"] == "test-client-id"
        assert data["client_secret"] == "test-client-secret"

    def test_profile_endpoint_uses_bearer_access_token(self, monkeypatch, orcid_env):
        _, mock_get = self._setup_mocks(monkeypatch)
        orcid_provider.complete_login("code")
        auth_header = mock_get.call_args.kwargs["headers"]["Authorization"]
        assert auth_header == "Bearer test-access-token-abc123"

    def test_token_endpoint_failure_raises(self, monkeypatch, orcid_env):
        monkeypatch.setattr(
            orcid_provider.requests,
            "post",
            MagicMock(return_value=_make_http_response({}, status=401)),
        )
        with pytest.raises(RuntimeError, match="token exchange"):
            orcid_provider.complete_login("bad-code")

    def test_missing_orcid_id_in_token_response_raises(self, monkeypatch, orcid_env):
        incomplete = {k: v for k, v in ORCID_TOKEN_RESPONSE.items() if k != "orcid"}
        self._setup_mocks(monkeypatch, token_response=incomplete)
        with pytest.raises(RuntimeError):
            orcid_provider.complete_login("code")

    def test_missing_access_token_in_response_raises(self, monkeypatch, orcid_env):
        incomplete = {
            k: v for k, v in ORCID_TOKEN_RESPONSE.items() if k != "access_token"
        }
        self._setup_mocks(monkeypatch, token_response=incomplete)
        with pytest.raises(RuntimeError):
            orcid_provider.complete_login("code")

    def test_missing_client_secret_raises(self, monkeypatch, orcid_env):
        monkeypatch.delenv("ORCID_CLIENT_SECRET")
        with pytest.raises(RuntimeError, match="ORCID_CLIENT_SECRET"):
            orcid_provider.complete_login("code")


# ─── GET /auth/<provider>/login ──────────────────────────────────────────────


@pytest.mark.auth
class TestAuthLogin:
    def test_redirects_to_provider_oauth_url(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        response = client.get("/auth/orcid/login")
        assert response.status_code == 302
        assert "sandbox.orcid.org" in response.headers["Location"]

    def test_state_is_passed_to_build_authorize_url(
        self, mock_api, mock_orcid_provider
    ):
        client = mock_api.app.test_client()
        client.get("/auth/orcid/login")
        state_arg = mock_orcid_provider.build_authorize_url.call_args.args[0]
        assert isinstance(state_arg, str) and len(state_arg) > 0

    def test_unknown_provider_returns_404(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        response = client.get("/auth/nonexistent/login")
        assert response.status_code == 404
        assert "Unknown provider" in response.json["error"]

    def test_provider_config_error_returns_500(self, mock_api, mock_orcid_provider):
        mock_orcid_provider.build_authorize_url.side_effect = RuntimeError(
            "Missing ORCID_CLIENT_ID"
        )
        client = mock_api.app.test_client()
        response = client.get("/auth/orcid/login")
        assert response.status_code == 500


# ─── GET /auth/<provider>/callback ───────────────────────────────────────────


@pytest.mark.auth
class TestAuthCallback:
    def _seed_session_state(self, client, state, provider="orcid"):
        """Write oauth_state and oauth_provider into the Flask session."""
        with client.session_transaction() as sess:
            sess["oauth_state"] = state
            sess["oauth_provider"] = provider

    # ── happy path ──────────────────────────────────────────────────────────

    def test_success_redirects_to_dashboard(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "valid-state")
        response = client.get("/auth/orcid/callback?code=authcode123&state=valid-state")
        assert response.status_code == 302
        assert _TEST_DASHBOARD_URL in response.headers["Location"]

    def test_success_location_contains_token(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "valid-state")
        response = client.get("/auth/orcid/callback?code=authcode123&state=valid-state")
        assert "token=" in response.headers["Location"]

    def test_issued_jwt_is_valid(self, mock_api, mock_orcid_provider, jwt_secret):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "valid-state")
        response = client.get("/auth/orcid/callback?code=authcode123&state=valid-state")
        token = _token_from_location(response.headers["Location"])
        payload = _pyjwt.decode(token, jwt_secret, algorithms=["HS256"])
        assert payload["sub"] == "0000-0002-1825-0097"
        assert payload["provider"] == "orcid"

    def test_issued_jwt_contains_profile(
        self, mock_api, mock_orcid_provider, jwt_secret, valid_profile
    ):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "valid-state")
        response = client.get("/auth/orcid/callback?code=authcode123&state=valid-state")
        token = _token_from_location(response.headers["Location"])
        profile = _pyjwt.decode(token, jwt_secret, algorithms=["HS256"])["profile"]
        assert profile["email"] == valid_profile["email"]
        assert profile["forename"] == valid_profile["forename"]

    # ── error cases ─────────────────────────────────────────────────────────

    def test_missing_code_returns_400(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "valid-state")
        response = client.get("/auth/orcid/callback?state=valid-state")
        assert response.status_code == 400
        assert "authorization code" in response.json["error"].lower()

    def test_state_mismatch_returns_400(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "stored-state")
        response = client.get("/auth/orcid/callback?code=abc&state=wrong-state")
        assert response.status_code == 400
        assert "state" in response.json["error"].lower()

    def test_unknown_provider_returns_404(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        response = client.get("/auth/github/callback?code=abc&state=s")
        assert response.status_code == 404

    def test_complete_login_failure_returns_502(self, mock_api, mock_orcid_provider):
        mock_orcid_provider.complete_login.side_effect = RuntimeError(
            "ORCID token exchange failed"
        )
        client = mock_api.app.test_client()
        self._seed_session_state(client, "valid-state")
        response = client.get("/auth/orcid/callback?code=abc&state=valid-state")
        assert response.status_code == 502
        assert "Authentication failed" in response.json["error"]

    # ── redirect URL construction ────────────────────────────────────────────

    def test_redirect_uses_dashboard_env_var(self, mock_api, mock_orcid_provider):
        client = mock_api.app.test_client()
        self._seed_session_state(client, "s")
        response = client.get("/auth/orcid/callback?code=abc&state=s")
        assert response.headers["Location"].startswith(_TEST_DASHBOARD_URL)

    def test_redirect_strips_trailing_slash(
        self, mock_api, mock_orcid_provider, monkeypatch
    ):
        monkeypatch.setenv("TARXIV_DASHBOARD_URL", "http://localhost:8050/")
        client = mock_api.app.test_client()
        self._seed_session_state(client, "s")
        response = client.get("/auth/orcid/callback?code=abc&state=s")
        location = response.headers["Location"]
        assert "//?token=" not in location  # no double slash
        assert "/?token=" in location

    def test_redirect_defaults_to_root_when_env_unset(
        self, mock_api, mock_orcid_provider, monkeypatch
    ):
        monkeypatch.delenv("TARXIV_DASHBOARD_URL", raising=False)
        client = mock_api.app.test_client()
        self._seed_session_state(client, "s")
        response = client.get("/auth/orcid/callback?code=abc&state=s")
        assert response.headers["Location"].startswith("/?token=")


# ─── API.check_token ─────────────────────────────────────────────────────────


@pytest.mark.auth
class TestCheckToken:
    def test_valid_jwt_returns_true(self, mock_api, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        assert mock_api.check_token(token) is True

    def test_valid_jwt_with_bearer_prefix_returns_true(self, mock_api, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        assert mock_api.check_token(f"Bearer {token}") is True

    def test_expired_jwt_returns_false(self, mock_api, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile, ttl=-1)
        assert mock_api.check_token(token) is False

    def test_tampered_signature_returns_false(self, mock_api, valid_profile):
        token = sign_token("test-sub", "orcid", valid_profile)
        header, payload_b64, _ = token.split(".")
        tampered = f"{header}.{payload_b64}.invalidsig"
        assert mock_api.check_token(tampered) is False

    def test_garbage_string_returns_false(self, mock_api):
        assert mock_api.check_token("not-a-token") is False

    def test_empty_string_returns_false(self, mock_api):
        assert mock_api.check_token("") is False

    def test_none_returns_false(self, mock_api):
        assert mock_api.check_token(None) is False

    def test_wrong_secret_returns_false(self, mock_api, monkeypatch, valid_profile):
        # Token signed with a different secret should be rejected
        monkeypatch.setenv("TARXIV_JWT_SECRET", "different-secret-long-32-bytes!!")
        token = sign_token("sub", "orcid", valid_profile)
        monkeypatch.setenv("TARXIV_JWT_SECRET", _TEST_JWT_SECRET)
        assert mock_api.check_token(token) is False
