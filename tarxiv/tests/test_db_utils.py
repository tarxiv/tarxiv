"""Tests for the scripts/db_utils dump/load helpers and the --legacy flag.

The ``--legacy`` flag targets the old TNS scope. ``scripts`` is not an
importable package, so the module is loaded directly from its file path.
``TarxivDB`` is patched out so no couchbase connection is made; the tests assert
the helpers read/write the correct scope/collections.
"""

import importlib.util
import json
import os
from unittest.mock import MagicMock

import pytest

_DB_UTILS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "scripts", "db_utils.py"
)


@pytest.fixture
def db_utils(monkeypatch):
    spec = importlib.util.spec_from_file_location("db_utils_under_test", _DB_UTILS_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def fake_db(db_utils, monkeypatch):
    db = MagicMock()
    monkeypatch.setattr(db_utils, "TarxivDB", lambda *a, **k: db)
    return db


def test_layouts_cover_old_and_new(db_utils):
    assert db_utils.SCHEMA_LAYOUTS["new"] == {
        "scope": "objects",
        "meta": "meta",
        "lc": "lightcurves",
    }
    assert db_utils.SCHEMA_LAYOUTS["old"] == {
        "scope": "tns",
        "meta": "objects",
        "lc": "lightcurves",
    }


def test_dump_new_layout_reads_objects_scope(db_utils, fake_db, tmp_path):
    fake_db.query.return_value = [{"id": "TXV-2018-000003"}]
    fake_db.get.side_effect = lambda obj, scope, collection: {
        "scope": scope,
        "collection": collection,
    }
    out = tmp_path / "dump.json"

    db_utils.dump_database_to_json(str(out), layout="new")

    statement = fake_db.query.call_args.args[0]
    assert "tarxiv.objects.meta" in statement
    # meta + lc fetched from the new scope/collections.
    scopes_collections = {
        (c.kwargs["scope"], c.kwargs["collection"]) for c in fake_db.get.call_args_list
    }
    assert scopes_collections == {("objects", "meta"), ("objects", "lightcurves")}


def test_dump_legacy_layout_reads_tns_scope(db_utils, fake_db, tmp_path):
    fake_db.query.return_value = [{"id": "2018mqw"}]
    fake_db.get.return_value = {"some": "doc"}
    out = tmp_path / "dump.json"

    db_utils.dump_database_to_json(str(out), layout="old")

    statement = fake_db.query.call_args.args[0]
    assert "tarxiv.tns.objects" in statement
    scopes_collections = {
        (c.kwargs["scope"], c.kwargs["collection"]) for c in fake_db.get.call_args_list
    }
    assert scopes_collections == {("tns", "objects"), ("tns", "lightcurves")}

    # The dumped file is keyed by object id and holds meta + lc.
    written = json.loads(out.read_text())
    assert "2018mqw" in written
    assert set(written["2018mqw"]) == {"meta", "lc"}


def test_load_legacy_layout_writes_tns_scope(db_utils, fake_db, tmp_path):
    src = tmp_path / "dump.json"
    src.write_text(
        json.dumps({"2018mqw": {"meta": {"m": 1}, "lc": [{"mjd": 1.0}]}})
    )

    db_utils.load_database_from_json(str(src), layout="old")

    upserts = {
        (c.kwargs["scope"], c.kwargs["collection"])
        for c in fake_db.upsert.call_args_list
    }
    assert upserts == {("tns", "objects"), ("tns", "lightcurves")}


def test_load_new_layout_writes_objects_scope(db_utils, fake_db, tmp_path):
    src = tmp_path / "dump.json"
    src.write_text(
        json.dumps({"TXV-2018-000003": {"meta": {"m": 1}, "lc": [{"mjd": 1.0}]}})
    )

    db_utils.load_database_from_json(str(src), layout="new")

    upserts = {
        (c.kwargs["scope"], c.kwargs["collection"])
        for c in fake_db.upsert.call_args_list
    }
    assert upserts == {("objects", "meta"), ("objects", "lightcurves")}


def test_main_legacy_flag_selects_old_layout(db_utils, monkeypatch, tmp_path):
    captured = {}

    def fake_dump(filename, limit, layout):
        captured["layout"] = layout

    monkeypatch.setattr(db_utils, "dump_database_to_json", fake_dump)

    db_utils.main(["--dump", "--legacy", "--filename", str(tmp_path / "x.json")])

    assert captured["layout"] == "old"
