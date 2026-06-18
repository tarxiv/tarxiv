"""Tests for the lightcurve plot, including the greyed-out empty state.

Newer records often carry no lightcurve photometry. Instead of a blank frame,
``create_lightcurve_plot`` must return a themed placeholder figure with a
"no data" message so the empty state is obvious.
"""

import pytest

from tarxiv.dashboard.components.plots import (
    create_lightcurve_plot,
    empty_lightcurve_plot,
)
from tarxiv.dashboard.components.theme_manager import register_tarxiv_templates


@pytest.fixture(autouse=True)
def _templates():
    # apply_theme() looks up the tarxiv_light/tarxiv_dark plotly templates, which
    # the app registers at startup; do the same so the figure can be themed.
    register_tarxiv_templates()


def _annotation_texts(fig) -> list:
    return [a.text for a in fig.layout.annotations]


def test_empty_state_returned_for_no_data():
    fig = create_lightcurve_plot([], "2018mqw", "tarxiv_light")

    # No data -> no traces, but a centred "no data" message.
    assert fig is not None
    assert len(fig.data) == 0
    assert "No lightcurve data available" in _annotation_texts(fig)
    # Axes hidden + a translucent grey overlay convey the greyed-out look.
    assert fig.layout.xaxis.visible is False
    assert fig.layout.yaxis.visible is False
    assert len(fig.layout.shapes) == 1


def test_empty_state_returned_for_none_data():
    fig = create_lightcurve_plot(None, "2018mqw", "tarxiv_light")

    assert len(fig.data) == 0
    assert "No lightcurve data available" in _annotation_texts(fig)


def test_empty_state_when_points_are_not_plottable():
    # Points exist but none are plottable (missing mjd / not a detection).
    points = [
        {"filter": "r", "survey": "ztf", "mjd": None, "mag": 18.0, "detection": 1},
        {"filter": "g", "survey": "ztf", "detection": 1, "mag": None},
    ]

    fig = create_lightcurve_plot(points, "2018mqw", "tarxiv_light")

    assert len(fig.data) == 0
    assert "No lightcurve data available" in _annotation_texts(fig)


def test_real_data_produces_traces_and_no_empty_message():
    points = [
        {
            "mjd": 58243.1,
            "mag": 18.87,
            "mag_err": 0.012,
            "filter": "r",
            "survey": "ztf",
            "detection": 1,
        },
        {
            "mjd": 58244.2,
            "mag": 18.5,
            "mag_err": 0.02,
            "filter": "r",
            "survey": "ztf",
            "detection": 1,
        },
    ]

    fig = create_lightcurve_plot(points, "2018mqw", "tarxiv_light")

    assert len(fig.data) >= 1
    assert "No lightcurve data available" not in _annotation_texts(fig)


def test_empty_lightcurve_plot_custom_message():
    fig = empty_lightcurve_plot("2018mqw", "tarxiv_dark", message="Nothing here")

    assert "Nothing here" in _annotation_texts(fig)
