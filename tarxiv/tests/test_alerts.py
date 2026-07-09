from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from unittest.mock import MagicMock, patch

import pytest

from tarxiv.alerts import IMAP


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
    return mock_config_data


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


@pytest.mark.imap
@patch("imaplib.IMAP4_SSL")
def test_dummy_tns_email(mock_imap, mock_config):
    """Test parsing a dummy TNS email with both Gmail and IMAP parsers."""
    # Dummy email body (shortened to avoid overly long lines)
    email_body = (
        "The following new transient/s were reported:\n\n"
        '<a href="https://www.wis-tns.org/object/2025sae">2025sae</a>\n\n'
        "Best Regards,\n"
        "The TNS team"
    )

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
