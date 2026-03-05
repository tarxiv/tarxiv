import base64
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, mock_open, patch

import pytest

from tarxiv.alerts import Gmail, IMAP


@pytest.fixture
def mock_config_data():
    """Provides a standard config dictionary."""
    return {
        "gmail": {
            "token_name": "token.json",
            "secrets_file": "secrets.json",
            "scopes": ["https://www.googleapis.com/auth/gmail.readonly"],
            "polling_interval": 1,
        },
        "imap": {
            "server": "imap.test.com",
            "username": "user",
            "password": "password",
            "polling_interval": 1,
        },
        "tns": {"email": "tns@example.com"},
    }


@pytest.fixture
def mock_config(monkeypatch, tmp_path, mock_config_data):
    """Mock TarxivModule to provide a standard config."""

    def mock_init(self, module, *args, **kwargs):
        self.config = mock_config_data
        self.config_dir = str(tmp_path)
        self.logger = MagicMock()

    monkeypatch.setattr("tarxiv.utils.TarxivModule.__init__", mock_init)

    # Create a dummy config.yml file
    config_file = tmp_path / "config.yml"
    config_file.write_text(
        """imap:\n  server: imap.test.com\n  username: user\n  password: password\n  polling_interval: 1\n"""
    )

    # Create a dummy secrets.json file
    secrets_file = tmp_path / "secrets.json"
    secrets_file.write_text(
        """{
        "installed": {
            "client_id": "dummy-client-id",
            "project_id": "dummy-project",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": "dummy-client-secret",
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }"""
    )
    return mock_config_data


@pytest.mark.gmail
def test_gmail_init_no_token(mock_config):
    """Test Gmail initialization when no token exists."""
    with (
        patch("os.path.exists") as mock_exists,
        patch("google.oauth2.credentials.Credentials.from_authorized_user_file"),
        patch(
            "google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file"
        ) as mock_flow_from_secrets,
        patch("tarxiv.alerts.build") as mock_build,
        patch("builtins.open", mock_open()),
    ):
        # Mock file existence: secrets.json exists, token.json does not
        def exists_side_effect(path):
            if "secrets.json" in path:
                return True
            if "token.json" in path:
                return False
            return False

        mock_exists.side_effect = exists_side_effect

        # Mock the flow creation and OAuth flow
        mock_flow_instance = MagicMock()
        mock_flow_from_secrets.return_value = mock_flow_instance

        # Mock credentials returned from OAuth flow
        mock_creds_instance = MagicMock()
        mock_creds_instance.valid = True
        mock_creds_instance.to_json.return_value = '{"token": "new_oauth_token"}'
        mock_flow_instance.run_local_server.return_value = mock_creds_instance

        # Mock Gmail API service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Create Gmail instance
        gmail = Gmail(script_name="test", reporting_mode=7)

        # Verify OAuth flow was called correctly
        config_dir = gmail.config_dir
        secrets_path = os.path.join(config_dir, "secrets.json")

        # Verify OAuth flow was called
        mock_exists.assert_called()
        mock_flow_from_secrets.assert_called_with(
            secrets_path, ["https://www.googleapis.com/auth/gmail.readonly"]
        )
        mock_flow_instance.run_local_server.assert_called_with(port=0)
        mock_build.assert_called_with("gmail", "v1", credentials=mock_creds_instance)

        assert gmail.service is not None


@pytest.mark.gmail
def test_gmail_init_with_existing_token(mock_config):
    """Test Gmail initialization when token already exists and is valid."""
    with (
        patch("os.path.exists") as mock_exists,
        patch("google.auth.transport.requests.Request") as mock_request,
        patch(
            "google.oauth2.credentials.Credentials.from_authorized_user_file"
        ) as mock_from_authorized_user_file,
        patch("tarxiv.alerts.build") as mock_build,
        patch("builtins.open", mock_open()),
    ):
        # Mock file existence: both secrets.json and token.json exist
        mock_exists.return_value = True

        # Mock existing valid credentials
        mock_creds_instance = MagicMock()
        mock_creds_instance.valid = True
        mock_creds_instance.to_json.return_value = '{"token": "existing_token"}'
        mock_from_authorized_user_file.return_value = mock_creds_instance

        # Mock Gmail API service
        mock_service = MagicMock()
        mock_build.return_value = mock_service

        # Mock the Request for token refresh
        mock_request_instance = MagicMock()
        mock_request.return_value = mock_request_instance

        # Create Gmail instance
        gmail = Gmail(script_name="test", reporting_mode=7)

        # Verify existing token was loaded and refreshed
        config_dir = gmail.config_dir
        token_path = os.path.join(config_dir, "token.json")

        # Verify existing token was loaded and refreshed
        mock_from_authorized_user_file.assert_called_with(
            token_path, ["https://www.googleapis.com/auth/gmail.readonly"]
        )
        mock_creds_instance.refresh.assert_called()
        mock_build.assert_called_with("gmail", "v1", credentials=mock_creds_instance)

        assert gmail.service is not None


@pytest.mark.gmail
@patch("tarxiv.alerts.Gmail.__init__", return_value=None)
def test_gmail_parse_message(mock_gmail_init, mock_config):
    """Test parsing a valid TNS email message."""
    gmail = Gmail(script_name="test", reporting_mode=7)
    gmail.config = mock_config
    gmail.logger = MagicMock()
    html_content = (
        '<html><body><a href="http://example.com/tns/2023xyz">2023xyz</a></body></html>'
    )
    encoded_content = base64.urlsafe_b64encode(html_content.encode("utf-8")).decode(
        "utf-8"
    )
    msg = {
        "payload": {
            "headers": [{"name": "From", "value": "Some Name <tns@example.com>"}],
            "body": {"data": encoded_content},
        }
    }
    alerts = gmail.parse_message(msg)
    assert alerts == ["2023xyz"]


@pytest.mark.imap
@patch("imaplib.IMAP4_SSL")
def test_imap_init_success(mock_imap, mock_config, monkeypatch):
    """Test IMAPEmail initialization success."""
    monkeypatch.setenv("TARXIV_IMAP_USERNAME", "user")
    monkeypatch.setenv("TARXIV_IMAP_PASSWORD", "password")

    mock_conn = MagicMock()
    mock_imap.return_value = mock_conn
    imap_email = IMAP(script_name="test", reporting_mode=7)
    mock_imap.assert_called_with("imap.test.com")
    mock_conn.login.assert_called_with("user", "password")
    mock_conn.select.assert_called_with("inbox")
    assert imap_email.conn is not None


@pytest.mark.imap
@patch("imaplib.IMAP4_SSL")
def test_imap_parse_message(mock_imap, mock_config):
    """Test parsing a valid TNS email from IMAP."""
    mock_conn = MagicMock()
    mock_imap.return_value = mock_conn
    imap_email = IMAP(script_name="test", reporting_mode=7)
    imap_email.config = mock_config
    html_content = (
        '<html><body><a href="http://example.com/tns/2023abc">2023abc</a></body></html>'
    )
    msg = MIMEMultipart()
    msg["From"] = "tns@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "TNS Alert"
    msg.attach(MIMEText(html_content, "html"))

    alerts = imap_email.parse_message(msg.as_bytes())
    assert alerts == ["2023abc"]


@pytest.mark.gmail
@pytest.mark.imap
@patch("tarxiv.alerts.Gmail.__init__", return_value=None)
@patch("imaplib.IMAP4_SSL")
def test_dummy_tns_email(mock_imap, _, mock_config):
    """Test parsing a dummy TNS email with both Gmail and IMAP parsers."""
    # Dummy email body (shortened to avoid overly long lines)
    email_body = (
        "The following new transient/s were reported:\n\n"
        '<a href="https://www.wis-tns.org/object/2025sae">2025sae</a>\n\n'
        "Best Regards,\n"
        "The TNS team"
    )
    html_content_gmail = f"<html><body><p>{email_body}</p></body></html>"
    encoded_content = base64.urlsafe_b64encode(
        html_content_gmail.encode("utf-8")
    ).decode("utf-8")

    # Gmail test
    gmail = Gmail(script_name="test", reporting_mode=7)
    gmail.config = mock_config
    gmail.logger = MagicMock()
    msg = {
        "payload": {
            "headers": [{"name": "From", "value": "Some Name <tns@example.com>"}],
            "body": {"data": encoded_content},
        }
    }
    alerts = gmail.parse_message(msg)
    assert alerts == ["2025sae"]

    # IMAP test
    mock_conn = MagicMock()
    mock_imap.return_value = mock_conn
    imap_email = IMAP(script_name="test", reporting_mode=7)
    imap_email.config = mock_config
    html_content_imap = f"<html><body><p>{email_body}</p></body></html>"
    msg = MIMEMultipart()
    msg["From"] = "tns@example.com"
    msg["To"] = "recipient@example.com"
    msg["Subject"] = "TNS Alert"
    msg.attach(MIMEText(html_content_imap, "html"))

    alerts = imap_email.parse_message(msg.as_bytes())
    assert alerts == ["2025sae"]
