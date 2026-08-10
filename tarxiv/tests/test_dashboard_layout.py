"""Tests for the app shell and page-layout construction.

Dash validates component props in ``Component.__init__``, so simply building a
layout catches invalid props -- for example a Mantine style prop such as
``visibleFrom`` passed to an ``html.*`` component, which raises at construction
and takes the whole dashboard down on first page load.

The shell also owns the ids that the callbacks in ``callbacks/style_callbacks.py``
bind to. A renamed or dropped id there is a runtime error ("A nonexistent object
was used in an Output"), not a cosmetic problem, so those ids are asserted
explicitly.
"""

import importlib
from unittest.mock import MagicMock

import dash
import flask
import pytest

from tarxiv.tests.test_dashboard_lightcurve import collect_component_ids

# Ids the shell must provide because callbacks target them.
# style_callbacks.py: theme toggle, plot repaint, nav refresh, global search, burger.
# cookie_callbacks.py: consent/settings stores.
SHELL_CALLBACK_IDS = {
    "app-shell",
    "topbar-nav",
    "mobile-nav-content",
    "color-scheme-toggle",
    "theme-icon",
    "burger",
    "global-search-input",
    "global-search-keyboard",
    "url",
    "active-settings-store",
    "local-settings-store",
    "cookie-consent-store",
    "page-content",
    "dummy-output",
}

# Pages built here. Every one reads the request (for the auth token) and/or
# current_app, so they all need a request context. The lightcurve page has its
# own dedicated tests in test_dashboard_lightcurve.py.
PAGES = ["home", "alerts", "tagged", "cone"]


@pytest.fixture
def main_layout():
    import tarxiv.dashboard.layouts.main_layout as module

    return module


def _build_shell(main_layout):
    """Build the shell inside a request context, as a real page load would."""
    app = flask.Flask(__name__)
    app.config["TXV_LOGGER"] = MagicMock()
    with app.test_request_context("/"):
        return main_layout.create_layout()


def test_create_layout_builds(main_layout):
    """The app shell must construct without raising.

    Regression: ``html.Div(id="topbar-nav", visibleFrom="sm")`` raised a
    TypeError because ``visibleFrom`` is a Mantine style prop that Dash's
    ``html.*`` components reject. Nothing exercised the shell, so it only
    surfaced when the dashboard was actually served.
    """
    assert _build_shell(main_layout) is not None


def test_create_layout_builds_without_request_context(main_layout):
    """The shell must build with no request context.

    ``app.layout`` is assigned the callable and re-evaluated per page load;
    ``create_layout`` guards on ``has_request_context`` for the auth lookup.
    """
    assert main_layout.create_layout() is not None


def test_shell_contains_callback_target_ids(main_layout):
    """Every id the callbacks bind to must exist in the shell."""
    ids = collect_component_ids(_build_shell(main_layout))

    missing = SHELL_CALLBACK_IDS - ids
    assert not missing, f"shell is missing callback target ids: {sorted(missing)}"


@pytest.fixture
def page_module(request, monkeypatch):
    """Import a page module with page/callback registration neutralised."""
    monkeypatch.setattr(dash, "register_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(dash, "callback", lambda *args, **kwargs: lambda f: f)
    monkeypatch.setattr(dash, "clientside_callback", lambda *args, **kwargs: None)

    module = importlib.import_module(f"tarxiv.dashboard.pages.{request.param}")
    return importlib.reload(module)


@pytest.mark.parametrize("page_module", PAGES, indirect=True)
def test_page_layouts_build(page_module, monkeypatch):
    """Every page layout must build for an anonymous user.

    These all render the restyled shared cards, so this covers the same
    construction-time prop errors across everything the redesign touched.
    """
    if hasattr(page_module, "get_jwt_from_request"):
        monkeypatch.setattr(page_module, "get_jwt_from_request", lambda *a, **k: None)
    if hasattr(page_module, "get_authenticated_user"):
        monkeypatch.setattr(page_module, "get_authenticated_user", lambda *a, **k: None)

    app = flask.Flask(__name__)
    app.config["TXV_LOGGER"] = MagicMock()
    with app.test_request_context("/"):
        assert page_module.layout() is not None
