"""HFS - This was written with GPT 4o"""
import pytest
import tempfile
import shutil
import os
import json
from tarxiv.database import TarxivDB

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
        f.write("log_dir: null\ndatabase:\n  host: localhost\n  user: user\n  pass: pass\n")

    yield temp_dir

    # Clean up temp directory
    shutil.rmtree(temp_dir)

def test_get_object_schema_reads_json_correctly(config_dir_with_schema, monkeypatch):
    # Patch __init__ of TarxivDB to skip actual couchbase connection
    monkeypatch.setattr(TarxivDB, "__init__", lambda self, *args, **kwargs: setattr(self, "schema_file", os.path.join(config_dir_with_schema, "schema.json")))

    db = TarxivDB(config_dir_with_schema)
    schema = db.get_object_schema()
    assert isinstance(schema, dict)
    assert "test_field" in schema
    assert schema["test_field"]["type"] == "string"
