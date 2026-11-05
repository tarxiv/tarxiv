"""Serve the real Dash dashboard against a fake API, for browser tests.

Run as ``python browser_app.py PORT``. It runs in its own interpreter on
purpose: other dashboard tests reload page modules with ``dash.callback``
stubbed out, and a Dash app built in that process would have no callbacks.

All HTTP the dashboard makes goes through ``requests.Session.request``, so one
patch there stands in for the API. Couchbase and file logging are stubbed the
same way the unit tests stub them.
"""

import json
import sys
from urllib.parse import urlparse

import requests

import tarxiv.database
import tarxiv.utils
from tarxiv.tests.conftest import MockTarxivModule

ME = "00000000-0000-0000-0000-000000000001"
OTHER = "00000000-0000-0000-0000-000000000002"
TEAM = "00000000-0000-0000-0000-0000000000aa"
SOURCE_ID = "2018mqu"
TARXIV_ID = "TXV-2018-000001"


def _comment(cid, author, body, parent=None, deleted=False, team=True, **extra):
    return {
        "id": cid,
        "source_id": SOURCE_ID,
        "parent_id": parent,
        "author_id": author,
        "author_name": {ME: "me", OTHER: "other"}.get(author),
        "author_picture_url": None,
        "owner_type": "team" if team else "user",
        "owner_id": TEAM if team else ME,
        "owner_name": "hubble" if team else "me",
        "body": "" if deleted else body,
        "deleted": deleted,
        "created_at": "2026-11-05T10:00:00+00:00",
        "updated_at": "2026-11-05T10:00:00+00:00",
        **extra,
    }


# One of every rendering state: own/other, team/personal, reply, edited,
# tombstone, deleted author.
COMMENTS = [
    _comment("c1", OTHER, "Looks like a Ia."),
    _comment("c2", ME, "Agreed.\nSecond line.", parent="c1"),
    _comment("c3", ME, "Private note", team=False),
    _comment("c4", OTHER, "", deleted=True),
    _comment("c5", ME, "Reply to a tombstone", parent="c4"),
    _comment("c6", None, "Author left", updated_at="2026-11-05T11:00:00+00:00"),
]

ROUTES = {
    ("POST", f"/get_object_meta/{SOURCE_ID}"): {
        "tarxiv_id": TARXIV_ID,
        "source": "tns",
        "source_id": SOURCE_ID,
        "ra_deg": 189.62,
        "dec_deg": 39.0,
        "ra_hms": "12:38:28.80",
        "dec_dms": "+39:00:00.0",
        "discovery_date": "2018-12-01",
        "data_sources": {},
    },
    ("POST", f"/get_object_lc/{TARXIV_ID}"): [
        {
            "mjd": 58450.0 + i,
            "mag": 18.0 + i / 10,
            "mag_err": 0.05,
            "limit": 20.0,
            "fwhm": 1.5,
            "filter": "g",
            "detection": 1,
            "camera": None,
            "survey": "ztf",
        }
        for i in range(5)
    ],
    ("GET", "/user"): {"id": ME, "username": "me"},
    ("GET", "/user/teams"): [
        {"team_id": TEAM, "user_id": ME, "role": "owner", "team_name": "hubble"}
    ],
    ("GET", "/tags"): [],
    ("GET", f"/objects/{SOURCE_ID}/tags"): [],
    ("GET", f"/objects/{SOURCE_ID}/comments"): COMMENTS,
}


def fake_request(self, method, url, *args, **kwargs):
    body = ROUTES.get((method.upper(), urlparse(url).path))
    response = requests.Response()
    response.status_code = 404 if body is None else 200
    response._content = json.dumps(
        {"error": "not faked"} if body is None else body
    ).encode()
    response.headers["Content-Type"] = "application/json"
    response.url = url
    return response


def main(port: int) -> None:
    requests.Session.request = fake_request
    tarxiv.utils.TarxivModule.__init__ = MockTarxivModule.__init__
    tarxiv.database.TarxivDB.__init__ = lambda self, *a, **k: None

    import tarxiv.dashboard.app as app_module

    app_module.generate_css = lambda: None
    app = app_module.TarxivDashboard("browser-test", 0).app
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main(int(sys.argv[1]))
