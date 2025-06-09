"""HFS - created with help from GPT 4o"""

import pytest
from unittest.mock import MagicMock
from tarxiv.api import API
import os


@pytest.fixture
def mock_api(monkeypatch, tmp_path):
    # HFS - 2025-05-28: Fake the TarXivDB object instantiation which is needed for the API object
    # we also have to fake TarxivModule, which is parent to API and TarxivDB
    monkeypatch.setattr(
        "tarxiv.database.TarxivDB.__init__", lambda self, *args, **kwargs: None
    )
    monkeypatch.setattr(
        "tarxiv.utils.TarxivModule.__init__",
        lambda self, module, config_dir, debug=False: (
            setattr(self, "module", module),
            setattr(self, "config_dir", config_dir),
            setattr(self, "config_file", os.path.join(config_dir, "config.yml")),
            setattr(self, "logger", MagicMock()),
            setattr(self, "debug", debug),
            setattr(self, "config", {"log_dir": None, "api_port": 5000}),
        ),
    )
    # HFS - 2025-05-28: MagicMock is a flexible fake object that can act like functions, methods,
    # or even entire objects. It records how it's used so you can assert things later
    # (e.g. mock.call_args)
    # HFS - 2025-05-28: Note we never open or do anything with the config file so we can give a path
    # to fill in the parameter so instanciation works and that's it.

    api = API("mock", str(tmp_path))
    # HFS - 2025-05-28: We now  replace the instance with a MagicMock so we don’t have to define every method
    # ourselves (e.g. get).
    api.txv_db = MagicMock()
    return api


def test_get_object_meta_success(mock_api):
    # HFS - 2025-05-28: The .app stuff comes from Flask and it returns a client object
    # that can do .post .get .put etc.. and send requests through
    # Flask routes that Kyle defined in the API class
    # the client objetc can also return response objects like
    # .status_code, .json
    # TL;DR: .app.test_client() is a fake browaser hitting
    # the self.app.route functions in API object
    client = mock_api.app.test_client()
    mock_api.txv_db.get.return_value = {"foo": "bar"}

    # TODO - HFS - 2025-05-28: This will fail when real authentication is implemented
    response = client.post("/get_object_meta/test_obj", json={"token": "TOKEN"})
    assert response.status_code == 200
    assert response.json == {"foo": "bar"}


def test_get_object_meta_bad_token(mock_api):
    client = mock_api.app.test_client()
    response = client.post("/get_object_meta/test_obj", json={"token": "WRONG"})
    assert response.status_code == 401
    assert response.json["error"] == "bad token"


def test_get_object_meta_missing_obj(mock_api):
    client = mock_api.app.test_client()
    mock_api.txv_db.get.return_value = None
    response = client.post("/get_object_meta/test_obj", json={"token": "TOKEN"})
    assert response.status_code == 404
    assert response.json["error"] == "no such object"
