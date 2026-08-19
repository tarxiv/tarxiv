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


def test_build_cone_query_string(cone_module):
    query = cone_module.build_cone_query_string(315.40375, 68.1633333333, 30.0)

    assert query == "?ra=315.403750&dec=68.163333&radius=30"


def test_cone_query_string_round_trips(cone_module):
    query = cone_module.build_cone_query_string(315.40375, -68.1633333333, 5.5)
    ra, dec, radius = cone_module.parse_cone_search_string(query)

    assert ra == pytest.approx(315.40375, abs=1e-6)
    assert dec == pytest.approx(-68.1633333333, abs=1e-6)
    assert radius == pytest.approx(5.5)


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"ra": "", "dec": "", "radius": ""},
        {"unrelated": "value"},
    ],
)
def test_parse_cone_query_params_absent(cone_module, params):
    assert cone_module.parse_cone_query_params(params) is None


@pytest.mark.parametrize("search", ["", None])
def test_parse_cone_search_string_empty(cone_module, search):
    assert cone_module.parse_cone_search_string(search) is None


def test_parse_cone_search_string_without_leading_question_mark(cone_module):
    assert cone_module.parse_cone_search_string("ra=10&dec=20&radius=5") == (
        10.0,
        20.0,
        5.0,
    )


@pytest.mark.parametrize(
    "params",
    [
        {"ra": "10", "dec": "20"},  # missing radius
        {"ra": "10", "radius": "5"},  # missing dec
        {"dec": "20", "radius": "5"},  # missing ra
    ],
)
def test_parse_cone_query_params_incomplete(cone_module, params):
    with pytest.raises(ValueError, match="Incomplete"):
        cone_module.parse_cone_query_params(params)


@pytest.mark.parametrize(
    "params",
    [
        {"ra": "abc", "dec": "20", "radius": "5"},
        {"ra": "10", "dec": "not_a_number", "radius": "5"},
        {"ra": "10", "dec": "20", "radius": "wide"},
    ],
)
def test_parse_cone_query_params_non_numeric(cone_module, params):
    with pytest.raises(ValueError, match="must all be numbers"):
        cone_module.parse_cone_query_params(params)


@pytest.mark.parametrize(
    ("params", "match"),
    [
        ({"ra": "361", "dec": "20", "radius": "5"}, "RA must be"),
        ({"ra": "-1", "dec": "20", "radius": "5"}, "RA must be"),
        ({"ra": "10", "dec": "91", "radius": "5"}, "Dec must be"),
        ({"ra": "10", "dec": "-91", "radius": "5"}, "Dec must be"),
        ({"ra": "10", "dec": "20", "radius": "0"}, "Radius must be"),
        ({"ra": "10", "dec": "20", "radius": "-5"}, "Radius must be"),
    ],
)
def test_parse_cone_query_params_out_of_range(cone_module, params, match):
    with pytest.raises(ValueError, match=match):
        cone_module.parse_cone_query_params(params)


def test_parse_cone_query_params_accepts_boundaries(cone_module):
    assert cone_module.parse_cone_query_params({
        "ra": "0",
        "dec": "-90",
        "radius": "0.001",
    }) == (0.0, -90.0, 0.001)
    assert cone_module.parse_cone_query_params({
        "ra": "360",
        "dec": "90",
        "radius": "1",
    }) == (360.0, 90.0, 1.0)


def test_parse_cone_query_params_accepts_numeric_values(cone_module):
    """layout() passes floats straight through when Dash has already coerced."""
    assert cone_module.parse_cone_query_params({
        "ra": 10.0,
        "dec": 20.0,
        "radius": 5.0,
    }) == (10.0, 20.0, 5.0)
