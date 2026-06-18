"""HFS - This was written with GPT 4o"""

import pytest
import tempfile
import shutil
import os
import json
from unittest.mock import MagicMock

from tarxiv.database import TarxivDB
from tarxiv.dto import ConeSearchResponseModel


@pytest.fixture
def config_dir_with_schema():
    # Create a temporary config directory with a dummy schema.json
    temp_dir = tempfile.mkdtemp()
    schema_path = os.path.join(temp_dir, "schema.json")
    config_path = os.path.join(temp_dir, "config.yml")

    sample_schema = {"test_field": {"type": "string", "description": "A test field"}}
    # sample_config = {"log_dir": None, "database": {"host": "localhost", "user": "user", "pass": "pass"}}

    with open(schema_path, "w") as f:
        json.dump(sample_schema, f)
    with open(config_path, "w") as f:
        f.write(
            "log_dir: null\ndatabase:\n  host: localhost\n  user: user\n  pass: pass\n"
        )

    yield temp_dir

    # Clean up temp directory
    shutil.rmtree(temp_dir)


def test_get_object_schema_reads_json_correctly(config_dir_with_schema, monkeypatch):
    # Patch __init__ of TarxivDB to skip actual couchbase connection
    monkeypatch.setattr(
        TarxivDB,
        "__init__",
        lambda self, *args, **kwargs: setattr(
            self, "schema_file", os.path.join(config_dir_with_schema, "schema.json")
        ),
    )

    db = TarxivDB(config_dir_with_schema)
    schema = db.get_object_schema()
    assert isinstance(schema, dict)
    assert "test_field" in schema
    assert schema["test_field"]["type"] == "string"


@pytest.fixture
def cone_db(monkeypatch):
    """A TarxivDB whose couchbase cluster/logging are stubbed out.

    Lets us drive ``cone_search`` and inspect the SQL++ it builds without a real
    couchbase connection.
    """
    monkeypatch.setattr(TarxivDB, "__init__", lambda self, *args, **kwargs: None)
    db = TarxivDB()
    db.cluster = MagicMock()
    db.logger = MagicMock()
    return db


def test_cone_search_returns_cluster_results(cone_db):
    # The method should return the (listified) cluster query results.
    cone_db.cluster.query.return_value = iter([
        {"obj_name": "2018mqw", "ra": 189.62, "dec": 39.0, "distance_deg": 0.0001},
    ])

    results = cone_db.cone_search(189.62, 39.0, 5.0)

    assert results == [
        {"obj_name": "2018mqw", "ra": 189.62, "dec": 39.0, "distance_deg": 0.0001},
    ]


def test_cone_search_query_aliases_match_response_model(cone_db):
    """Cone-search SELECT must alias to the dashboard's expected fields.

    Regression: the query must alias to obj_name/ra/dec/distance_deg, reading
    from the new top-level coordinate columns. Previously it selected
    ``tarxiv_id``/``ra_deg``/``dec_deg`` verbatim, so ``ConeSearchResponseModel``
    rejected every row and the cone-search page reported zero results.
    """
    cone_db.cluster.query.return_value = iter([])

    cone_db.cone_search(10.0, -20.0, 30.0)

    statement = cone_db.cluster.query.call_args.args[0]
    assert "meta.source_id AS obj_name" in statement
    assert "meta.ra_deg AS ra" in statement
    assert "meta.dec_deg AS `dec`" in statement
    assert "distance_deg" in statement
    # Radius is converted from arcsec to degrees for the WHERE clause.
    assert f"<= {30.0 / 3600.0}" in statement


def test_cone_search_row_validates_against_response_model():
    """A row shaped the way the fixed query emits must satisfy the DTO."""
    row = {"obj_name": "2018mqw", "ra": 189.62, "dec": 39.0, "distance_deg": 0.00012}

    parsed = ConeSearchResponseModel.validate_python([row])

    assert parsed[0].obj_name == "2018mqw"
    assert parsed[0].ra == pytest.approx(189.62)
