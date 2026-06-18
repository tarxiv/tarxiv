import importlib

import dash
import pytest


@pytest.fixture
def cone_module(monkeypatch):
    monkeypatch.setattr(dash, "register_page", lambda *args, **kwargs: None)
    import tarxiv.dashboard.pages.cone as cone

    return importlib.reload(cone)


@pytest.mark.parametrize(
    ("ra_hms", "dec_dms"),
    [
        ("21 01 36.90", "+68 09 48.0"),
        ("21:01:36.90", "+68:09:48.0"),
    ],
)
def test_parse_hms_dms_coordinates_sexagesimal(cone_module, ra_hms, dec_dms):
    ra, dec = cone_module.parse_hms_dms_coordinates(ra_hms, dec_dms)

    assert ra == pytest.approx(315.40375, abs=1e-6)
    assert dec == pytest.approx(68.1633333333, abs=1e-6)


def test_parse_hms_dms_coordinates_invalid_ra(cone_module):
    with pytest.raises(ValueError):
        cone_module.parse_hms_dms_coordinates("not_ra", "+68:09:48.0")


def test_parse_hms_dms_coordinates_invalid_dec(cone_module):
    with pytest.raises(ValueError):
        cone_module.parse_hms_dms_coordinates("21:01:36.90", "not_dec")


def test_parse_hms_dms_coordinates_blank_ra(cone_module):
    with pytest.raises(ValueError):
        cone_module.parse_hms_dms_coordinates("   ", "+68:09:48.0")


def test_parse_hms_dms_coordinates_blank_dec(cone_module):
    with pytest.raises(ValueError):
        cone_module.parse_hms_dms_coordinates("21:01:36.90", "   ")


@pytest.mark.parametrize(
    "combined",
    [
        "21:01:36.90 +68:09:48.0",
        "21:01:36.90, +68:09:48.0",
        "  21:01:36.90   +68:09:48.0  ",
    ],
)
def test_parse_combined_coordinates(cone_module, combined):
    ra, dec = cone_module.parse_combined_coordinates(combined)

    assert ra == pytest.approx(315.40375, abs=1e-6)
    assert dec == pytest.approx(68.1633333333, abs=1e-6)


def test_parse_combined_coordinates_blank(cone_module):
    with pytest.raises(ValueError):
        cone_module.parse_combined_coordinates("   ")


@pytest.mark.parametrize(
    "combined",
    [
        "21:01:36.90",  # only one token (missing dec)
        "21 01 36.90 +68 09 48.0",  # space-separated values are ambiguous
        "not coordinates at all",
    ],
)
def test_parse_combined_coordinates_invalid(cone_module, combined):
    with pytest.raises(ValueError):
        cone_module.parse_combined_coordinates(combined)
