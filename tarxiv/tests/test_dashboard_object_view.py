"""Tests for the object-page builders and the lightcurve series styling.

``build_key_facts`` has to cope with several quirks of the stored metadata --
the host arriving under ``hostname``, peak magnitudes living in a plural
``peak_mags`` list with the value under the key ``limit``, and detection counts
existing only in the photometry -- so those are covered explicitly here.
"""

from dash.development.base_component import Component

from tarxiv.dashboard.components.object_view import (
    EM_DASH,
    build_key_facts,
    build_photometry_table,
)
from tarxiv.dashboard.styles import BAND_COLORS, resolve_filter_style


def _facts_by_label(meta, lc_data=None) -> dict:
    return {fact["label"]: fact for fact in build_key_facts(meta, lc_data)}


# --------------------------------------------------------------------------
# build_key_facts
# --------------------------------------------------------------------------


def test_key_facts_returns_six_facts_for_empty_metadata():
    facts = build_key_facts({}, None)

    assert len(facts) == 6
    assert all(fact["value"] == EM_DASH for fact in facts)


def test_key_facts_reads_host_from_tns_hostname_key():
    """The TNS ingest writes the host under "hostname", not "host_name"."""
    meta = {"data_sources": {"tns": {"hostname": "M101"}}}

    assert _facts_by_label(meta)["Host"]["value"] == "M101"


def test_key_facts_falls_back_to_sherlock_catalogue_object():
    meta = {"data_sources": {"sherlock": {"catalogue_object_id": "NGC 5457"}}}

    assert _facts_by_label(meta)["Host"]["value"] == "NGC 5457"


def test_key_facts_prefers_tns_redshift_over_sherlock():
    meta = {
        "data_sources": {
            "tns": {"redshift": 0.000804},
            "sherlock": {"redshift": 0.5},
        }
    }

    assert _facts_by_label(meta)["Redshift"]["value"] == "0.000804"


def test_key_facts_uses_sherlock_redshift_when_tns_missing():
    meta = {"data_sources": {"tns": {}, "sherlock": {"redshift": 0.021}}}

    assert _facts_by_label(meta)["Redshift"]["value"] == "0.021"


def test_key_facts_peak_magnitude_reads_value_under_limit_key():
    """summarize_lc_mags stores the peak magnitude under "limit"."""
    meta = {
        "data_sources": {
            "ztf": {"peak_mags": [{"filter": "g", "limit": 11.58, "date": "60090.21"}]}
        }
    }

    peak = _facts_by_label(meta)["Peak mag"]
    assert peak["value"] == "11.6"
    assert peak["unit"] == "g"


def test_key_facts_peak_magnitude_takes_brightest_across_sources():
    meta = {
        "data_sources": {
            "ztf": {"peak_mags": [{"filter": "g", "limit": 11.58}]},
            "atlas": {"peak_mags": [{"filter": "o", "limit": 10.94}]},
        }
    }

    peak = _facts_by_label(meta)["Peak mag"]
    # Brightest == numerically smallest magnitude.
    assert peak["value"] == "10.9"
    assert peak["unit"] == "o"


def test_key_facts_peak_magnitude_ignores_unparseable_entries():
    meta = {
        "data_sources": {
            "ztf": {"peak_mags": [{"filter": "g", "limit": None}, "junk"]},
        }
    }

    assert _facts_by_label(meta)["Peak mag"]["value"] == EM_DASH


def test_key_facts_discovery_date_trimmed_and_carries_reporting_group():
    meta = {
        "discovery_date": "2023-05-19T17:27:15",
        "data_sources": {"tns": {"reporting_group": "Itagaki"}},
    }

    discovered = _facts_by_label(meta)["Discovered"]
    assert discovered["value"] == "2023-05-19"
    assert discovered["unit"] == "Itagaki"


def test_key_facts_numeric_distance_gets_mpc_unit():
    meta = {"data_sources": {"sherlock": {"best_distance": 6.8512}}}

    distance = _facts_by_label(meta)["Distance"]
    assert distance["value"] == "6.85"
    assert distance["unit"] == "Mpc"


def test_key_facts_string_distance_passes_through_without_unit():
    meta = {"data_sources": {"sherlock": {"best_distance": "unknown"}}}

    distance = _facts_by_label(meta)["Distance"]
    assert distance["value"] == "unknown"
    assert distance["unit"] is None


def test_key_facts_counts_detections_and_lists_surveys():
    lc_data = [
        {"detection": 1, "survey": "ztf"},
        {"detection": 1, "survey": "atlas"},
        {"detection": 0, "survey": "atlas"},  # non-detection, not counted
        {"detection": -1, "survey": "ztf"},  # bad quality, not counted
    ]

    detections = _facts_by_label({}, lc_data)["Detections"]
    assert detections["value"] == "2"
    assert detections["unit"] == "ATLAS + ZTF"


# --------------------------------------------------------------------------
# build_photometry_table
# --------------------------------------------------------------------------


def _table_text(component) -> str:
    """Flatten a component tree into a string of its text content."""
    if isinstance(component, str):
        return component
    if isinstance(component, (int, float)):
        return str(component)
    if isinstance(component, (list, tuple)):
        return " ".join(_table_text(child) for child in component)
    if isinstance(component, Component):
        return _table_text(getattr(component, "children", None) or [])
    return ""


def test_photometry_table_empty_state():
    table = build_photometry_table([], "light")

    assert "No photometry available" in _table_text(table)


def test_photometry_table_renders_detections_and_limits():
    points = [
        {
            "mjd": 60090.2,
            "mag": 11.58,
            "mag_err": 0.02,
            "filter": "g",
            "survey": "ztf",
            "detection": 1,
        },
        {
            "mjd": 60082.9,
            "limit": 19.24,
            "filter": "o",
            "survey": "atlas",
            "detection": 0,
        },
    ]

    text = _table_text(build_photometry_table(points, "light"))

    assert "ZTF g" in text
    assert "11.58" in text
    # Non-detections are rendered as upper limits with no uncertainty.
    assert "> 19.24" in text
    assert "limit" in text


def test_photometry_table_sorts_by_epoch_and_drops_bad_quality():
    points = [
        {"mjd": 60100.0, "mag": 15.0, "filter": "r", "survey": "ztf", "detection": 1},
        {"mjd": 60000.0, "mag": 14.0, "filter": "r", "survey": "ztf", "detection": 1},
        {"mjd": 60050.0, "mag": 99.0, "filter": "r", "survey": "ztf", "detection": -1},
        {"mjd": None, "mag": 13.0, "filter": "r", "survey": "ztf", "detection": 1},
    ]

    text = _table_text(build_photometry_table(points, "light"))

    assert text.index("60000.00") < text.index("60100.00")
    # detection == -1 and missing MJD are both excluded.
    assert "60050.00" not in text
    assert "99.00" not in text


# --------------------------------------------------------------------------
# resolve_filter_style
# --------------------------------------------------------------------------


def test_filter_style_core_bands_use_validated_colours():
    assert resolve_filter_style("ztf", "g")["light"] == BAND_COLORS["g"][0]
    assert resolve_filter_style("atlas", "o")["dark"] == BAND_COLORS["o"][1]


def test_filter_style_symbol_tracks_band_for_cvd_safety():
    """Bands g and r differ in shape as well as hue.

    Green/red sits in the 6-8 CVD separation band, which is only legal with a
    secondary encoding, so symbol has to move with the band.
    """
    assert (
        resolve_filter_style("ztf", "g")["symbol"]
        != resolve_filter_style("ztf", "r")["symbol"]
    )


def test_filter_style_same_band_matches_across_surveys():
    """The same bandpass renders identically whichever survey reported it."""
    assert resolve_filter_style("ztf", "g") == resolve_filter_style("asas-sn", "g")


def test_filter_style_normalises_ztf_capital_r():
    assert resolve_filter_style("ztf", "R")["light"] == BAND_COLORS["r"][0]


def test_filter_style_unknown_band_folds_to_neutral():
    style = resolve_filter_style("mystery-survey", "q")

    assert style["light"] == BAND_COLORS["Unknown"][0]
    assert style["symbol"] == "x"


def test_filter_style_handles_missing_values():
    style = resolve_filter_style(None, None)

    assert style["light"] == BAND_COLORS["Unknown"][0]
    assert style["dark"] == BAND_COLORS["Unknown"][1]
