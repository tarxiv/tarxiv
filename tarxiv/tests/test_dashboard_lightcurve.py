"""Tests for the lightcurve / object page layout.

Regression coverage for the object-tagging container: its callbacks
(``load_object_tagging_panel`` etc.) fire on initial page load, so the
``object-tagging-container`` component must exist in the base page layout even
when no object is shown. If it is only rendered inside the dynamic search
results, Dash raises "A nonexistent object was used in an Output" on the empty
page.
"""

import importlib
from unittest.mock import MagicMock

import dash
import flask
import pytest
from dash.development.base_component import Component


def collect_component_ids(component) -> set:
    """Recursively collect all string ids in a Dash component tree."""
    ids: set = set()
    if not isinstance(component, Component):
        return ids

    comp_id = getattr(component, "id", None)
    if isinstance(comp_id, str):
        ids.add(comp_id)

    children = getattr(component, "children", None)
    if isinstance(children, Component):
        children = [children]
    if isinstance(children, (list, tuple)):
        for child in children:
            ids |= collect_component_ids(child)
    return ids


@pytest.fixture
def lightcurve_module(monkeypatch):
    # Neutralise page/callback registration so the module can be (re)imported
    # without a running Dash app; we only exercise plain functions here.
    monkeypatch.setattr(dash, "register_page", lambda *args, **kwargs: None)
    monkeypatch.setattr(dash, "callback", lambda *args, **kwargs: lambda f: f)
    monkeypatch.setattr(dash, "clientside_callback", lambda *args, **kwargs: None)

    import tarxiv.dashboard.pages.lightcurve as lightcurve

    return importlib.reload(lightcurve)


def _render_empty_layout(lightcurve_module, monkeypatch):
    """Render the page layout for the empty (no-object) state."""
    monkeypatch.setattr(lightcurve_module, "get_jwt_from_request", lambda *a, **k: None)
    monkeypatch.setattr(
        lightcurve_module, "get_authenticated_user", lambda *a, **k: None
    )

    app = flask.Flask(__name__)
    app.config["TXV_LOGGER"] = MagicMock()
    with app.test_request_context("/lightcurve"):
        return lightcurve_module.layout()


def test_empty_layout_contains_tagging_container(lightcurve_module, monkeypatch):
    """The empty page must still include object-tagging-container in the layout.

    Otherwise the initial-call ``load_object_tagging_panel`` callback targets a
    component that is not present and Dash errors.
    """
    layout = _render_empty_layout(lightcurve_module, monkeypatch)

    ids = collect_component_ids(layout)
    assert "object-tagging-container" in ids
    # The results/citations slots and stores should be present too.
    assert "results-container" in ids
    assert "lightcurve-store" in ids


def test_empty_layout_has_single_tagging_container(lightcurve_module, monkeypatch):
    """Guard against a duplicate-id regression (base layout + results both)."""
    layout = _render_empty_layout(lightcurve_module, monkeypatch)

    container_count = _count_id(layout, "object-tagging-container")
    assert container_count == 1


def _count_id(component, target_id) -> int:
    count = 0
    if not isinstance(component, Component):
        return 0
    if getattr(component, "id", None) == target_id:
        count += 1
    children = getattr(component, "children", None)
    if isinstance(children, Component):
        children = [children]
    if isinstance(children, (list, tuple)):
        for child in children:
            count += _count_id(child, target_id)
    return count


def test_format_object_metadata_pieces():
    """Returns three render pieces and does not embed the tagging container.

    The tagging container belongs to the base layout, so it must not appear in
    any of the pieces returned here.
    """
    from tarxiv.dashboard.components.cards import format_object_metadata

    meta = {
        "tarxiv_id": "2021njo",
        "source": "TNS",
        "ra": "03:06:55.682",
        "dec": "-11:58:55.51",
        "data_sources": {"tns": {"ra_deg": 46.73, "dec_deg": -11.98}},
    }

    results_top, citations_card, full_metadata = format_object_metadata(
        "2021njo", meta, citation_str="@article{...}"
    )

    combined_ids: set = set()
    for piece in (results_top, citations_card, full_metadata):
        combined_ids |= collect_component_ids(piece)

    # The copyable coordinates header is part of the rendered output...
    assert "object-coordinates" in combined_ids
    # ...but the tagging container must not be (it belongs to the base layout).
    assert "object-tagging-container" not in combined_ids


def test_coordinates_header_omitted_without_coordinates():
    """Missing ra/dec yields a placeholder, not a copyable coordinate element."""
    from tarxiv.dashboard.components.cards import format_object_metadata

    meta = {"tarxiv_id": "x", "data_sources": {}}
    results_top, _citations, _full = format_object_metadata("x", meta)

    assert "object-coordinates" not in collect_component_ids(results_top)
