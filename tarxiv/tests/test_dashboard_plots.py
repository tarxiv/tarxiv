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
from tarxiv.dashboard.styles import BAND_COLORS


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


def _two_band_points():
    return [
        {
            "mjd": 58243.1,
            "mag": 18.87,
            "mag_err": 0.012,
            "filter": "g",
            "survey": "ztf",
            "detection": 1,
        },
        {
            "mjd": 58244.2,
            "limit": 20.1,
            "filter": "o",
            "survey": "atlas",
            "detection": 0,
        },
    ]


def test_traces_are_named_by_survey_and_band():
    fig = create_lightcurve_plot(_two_band_points(), "2018mqw", "tarxiv_light")

    names = [trace.name for trace in fig.data]
    assert "ZTF g" in names


def test_detection_trace_styling_and_hover():
    fig = create_lightcurve_plot(_two_band_points(), "2018mqw", "tarxiv_light")

    detection = next(t for t in fig.data if t.name == "ZTF g")
    # Symbol encodes the survey (ZTF -> circle), colour encodes the band.
    assert detection.marker.symbol == "circle"
    assert detection.marker.color == BAND_COLORS["g"][0]
    # Error bars are hairlines with no caps.
    assert detection.error_y.width == 0
    assert detection.error_y.thickness == 1.2
    # Uncertainty is surfaced on hover via customdata.
    assert "customdata" in detection.hovertemplate


def test_dark_scheme_uses_dark_band_colours():
    points = [
        {
            "mjd": 58243.1,
            "mag": 18.0,
            "mag_err": 0.01,
            "filter": "o",
            "survey": "atlas",
            "detection": 1,
        }
    ]

    fig = create_lightcurve_plot(points, "2018mqw", "tarxiv_dark")

    assert fig.data[0].marker.color == BAND_COLORS["o"][1]


def test_limit_traces_are_hollow_and_absent_from_legend():
    fig = create_lightcurve_plot(_two_band_points(), "2018mqw", "tarxiv_light")

    limit = next(t for t in fig.data if "limit" in (t.name or ""))
    assert limit.marker.symbol == "triangle-down-open"
    assert limit.showlegend is False


def test_axis_formatting_for_mjd_and_magnitude():
    fig = create_lightcurve_plot(_two_band_points(), "2018mqw", "tarxiv_light")

    # MJDs are large integers; ".2f" ticks read as noise.
    assert fig.layout.xaxis.tickformat == "d"
    assert fig.layout.yaxis.autorange == "reversed"
    # The card header carries the title, so the figure must not repeat it.
    assert fig.layout.title.text is None
