import os
from unittest.mock import MagicMock

import pytest

from tarxiv.api import API

_TEST_JWT_SECRET = "test-jwt-secret-for-api-tests-32b"


class MockTarxivModule:
    """Mock version of TarxivModule for testing purposes."""

    def __init__(self, *args, **kwargs):
        self.module = "mock tarxiv module"
        self.config_dir = os.environ.get(
            "TARXIV_CONFIG_DIR", os.path.join(os.path.dirname(__file__), "../aux")
        )
        self.config_file = os.path.join(self.config_dir, "config.yml")
        self.config = {"log_dir": None, "api_port": 5000}
        self.logger = MagicMock()
        self.debug = False


@pytest.fixture
def mock_api(monkeypatch, tmp_path):
    monkeypatch.setenv("TARXIV_JWT_SECRET", _TEST_JWT_SECRET)
    # HFS - 2025-05-28: Fake the TarXivDB object instantiation which is needed for the API object
    # we also have to fake TarxivModule, which is parent to API and TarxivDB
    monkeypatch.setattr(
        "tarxiv.database.TarxivDB.__init__", lambda self, *args, **kwargs: None
    )
    monkeypatch.setattr(
        "tarxiv.database_user.UserDB.__init__", lambda self, *args, **kwargs: None
    )

    # JL - 2025-06-05: Mock the TarxivModule to avoid file I/O and logging setup
    # during tests. Previous incarnation of this mock class was too tightly
    # coupled to the original TarxivModule, this should be more generic.
    monkeypatch.setattr("tarxiv.utils.TarxivModule.__init__", MockTarxivModule.__init__)

    # HFS - 2025-05-28: MagicMock is a flexible fake object that can act like functions, methods,
    # or even entire objects. It records how it's used so you can assert things later
    # (e.g. mock.call_args)
    # HFS - 2025-05-28: Note we never open or do anything with the config file so we can give a path
    # to fill in the parameter so instanciation works and that's it.

    api = API("mock", str(tmp_path))
    # HFS - 2025-05-28: We now  replace the instance with a MagicMock so we don’t have to define every method
    # ourselves (e.g. get).
    api.txv_db = MagicMock()
    api.user_db = MagicMock()
    return api
