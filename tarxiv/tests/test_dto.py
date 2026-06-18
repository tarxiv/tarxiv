"""Tests for the consolidated data-transfer models in ``tarxiv.dto``.

These guard the metadata schema the dashboard relies on. In particular they
pin the behaviour behind the "coordinates unavailable" bug: the object page
reads the top-level sexagesimal coordinates off the *dumped* model, so those
fields must be declared on ``MetadataResponseModel`` (otherwise pydantic drops
them and the copyable RA/Dec header renders empty).
"""

import json
import os

from tarxiv.dto import (
    ConeSearchResponseModel,
    LightcurveResponseModel,
    MetadataResponseModel,
)

# The current new-schema sample the database emits.
SAMPLE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "..",
    "docs",
    "dev-notes",
    "new-sample-2.json",
)


def _load_sample() -> dict:
    with open(SAMPLE_PATH) as f:
        return json.load(f)


def test_metadata_model_parses_new_schema_sample():
    sample = _load_sample()

    meta = MetadataResponseModel.model_validate(sample)

    assert meta.tarxiv_id == "TXV-2018-000003"
    assert meta.source == "tns"
    assert meta.source_id == "2018mqw"
    # Both decimal and sexagesimal coordinates survive parsing.
    assert meta.ra_deg == sample["ra_deg"]
    assert meta.ra_hms == sample["ra_hms"]
    assert meta.dec_dms == sample["dec_dms"]
    # Source-keyed payloads are kept permissively.
    assert "tns" in meta.data_sources
    assert "sherlock" in meta.data_sources
    assert meta.data_sources["tns"]["object_id"] == "2018mqw"


def test_metadata_model_dump_preserves_coordinate_fields():
    """Dumping the model must preserve the top-level coordinate fields.

    The object page builds its copyable coordinate header from the dumped model.
    If ``ra_hms``/``dec_dms`` were not declared on the model they would be
    silently dropped here, which is exactly what broke the header.
    """
    meta = MetadataResponseModel.model_validate(_load_sample())

    dumped = meta.model_dump()

    assert dumped["ra_hms"] == "12:38:29.211744"
    assert dumped["dec_dms"] == "+39:00:11.0061"
    assert dumped["ra_deg"] is not None
    assert dumped["dec_deg"] is not None


def test_metadata_model_tolerates_missing_optional_fields():
    # A bare document (only the required id) must still validate.
    meta = MetadataResponseModel.model_validate({"tarxiv_id": "TXV-0000-000000"})
    assert meta.data_sources == {}
    assert meta.ra_hms is None


def test_cone_search_model_parses_db_row_shape():
    rows = [
        {"obj_name": "2018mqw", "ra": 189.62, "dec": 39.0, "distance_deg": 0.0001},
    ]

    parsed = ConeSearchResponseModel.validate_python(rows)

    assert parsed[0].obj_name == "2018mqw"
    assert parsed[0].dec == 39.0


def test_lightcurve_model_parses_point():
    points = [
        {
            "mjd": 58243.1,
            "mag": 18.87,
            "mag_err": 0.012,
            "limit": None,
            "fwhm": None,
            "filter": "r",
            "detection": 1,
            "camera": "main",
            "survey": "ztf",
        }
    ]

    parsed = LightcurveResponseModel.validate_python(points)

    assert parsed[0].filter == "r"
    assert parsed[0].camera == "main"
