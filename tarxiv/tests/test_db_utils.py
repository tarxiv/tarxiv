"""Tests for the scripts/db_utils dump/load helpers and the --legacy flag.

The ``--legacy`` flag targets the old TNS scope. ``scripts`` is not an
importable package, so the module is loaded directly from its file path.
``TarxivDB`` is patched out so no couchbase connection is made; the tests assert
the helpers read/write the correct scope/collections.
"""

import datetime
import gzip
import importlib.util
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from couchbase.exceptions import UnAmbiguousTimeoutException

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
    src.write_text(json.dumps({"2018mqw": {"meta": {"m": 1}, "lc": [{"mjd": 1.0}]}}))

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


@pytest.fixture
def no_sleep(db_utils, monkeypatch):
    monkeypatch.setattr(db_utils.time, "sleep", lambda s: None)


def test_dump_retries_transient_timeouts(db_utils, fake_db, no_sleep, tmp_path):
    fake_db.query.return_value = [{"id": "2023ldd"}]
    fake_db.get.side_effect = [UnAmbiguousTimeoutException(), {"m": 1}, [{"mjd": 1.0}]]
    out = tmp_path / "dump.json"

    assert db_utils.dump_database_to_json(str(out), layout="old") == 1

    assert json.loads(out.read_text()) == {
        "2023ldd": {"meta": {"m": 1}, "lc": [{"mjd": 1.0}]}
    }


def test_dump_streams_valid_json_that_loads_back(db_utils, fake_db, tmp_path):
    ids = ["a", "b", "c"]
    fake_db.query.return_value = [{"id": i} for i in ids]
    fake_db.get.side_effect = lambda obj, scope, collection: {"id": obj}
    out = tmp_path / "dump.json"

    db_utils.dump_database_to_json(str(out), layout="new")
    db_utils.load_database_from_json(str(out), layout="new")

    assert list(json.loads(out.read_text())) == ids
    assert {c.args[0] for c in fake_db.upsert.call_args_list} == set(ids)


class _ScanRes:
    def __init__(self, doc_id, doc):
        self.id = doc_id
        self.content_as = {bytes: json.dumps(doc).encode()}


def _fake_bucket(fake_db, data):
    """Point ``fake_db.conn`` at ``data``: {(scope, collection): scan_fn or {id: doc}}."""
    scopes = {}
    for scope, coll in data:
        scopes.setdefault(scope, []).append(SimpleNamespace(name=coll))
    fake_db.conn.collections().get_all_scopes.return_value = [
        SimpleNamespace(name=s, collections=c) for s, c in scopes.items()
    ]

    def scan(scope, coll):
        src = data[(scope, coll)]
        if callable(src):
            return src()
        return [_ScanRes(k, v) for k, v in src.items()]

    fake_db.conn.scope.side_effect = lambda s: MagicMock(
        collection=lambda c: MagicMock(scan=lambda *a: scan(s, c))
    )


def test_list_collections_skips_system_scope(db_utils, fake_db):
    _fake_bucket(
        fake_db,
        {
            ("_system", "_mobile"): {},
            ("misc", "idx"): {},
            ("xmatch", "hits"): {},
            ("objects", "meta"): {},
        },
    )

    assert db_utils.list_collections(fake_db) == [
        ("misc", "idx"),
        ("xmatch", "hits"),
        ("objects", "meta"),
    ]
    assert db_utils.list_collections(fake_db, ["misc", "objects.m*"]) == [
        ("misc", "idx"),
        ("objects", "meta"),
    ]


def test_backup_round_trips_every_collection(db_utils, fake_db, tmp_path):
    _fake_bucket(
        fake_db,
        {
            ("misc", "idx"): {"2026": 42},  # binary counter, not a JSON object
            ("xmatch", "hits"): {"h1": {"a": 1}},
            ("objects", "meta"): {"TXV-1": {"m": 1}, "TXV-2": {"m": 2}},
        },
    )

    dest, failed = db_utils.backup_couchbase(str(tmp_path))

    assert failed == []
    assert os.listdir(tmp_path) == [os.path.basename(dest)]
    assert dest.endswith(".jsonl.gz")
    with gzip.open(dest, "rt") as f:
        assert len(f.readlines()) == 4

    count = db_utils.load_collections(dest, scope_map={"misc": "misc_rt"})

    assert count == 4
    upserts = {
        (c.args[0], json.dumps(c.args[1]), c.kwargs["scope"], c.kwargs["collection"])
        for c in fake_db.upsert.call_args_list
    }
    assert upserts == {
        ("2026", "42", "misc_rt", "idx"),
        ("h1", '{"a": 1}', "xmatch", "hits"),
        ("TXV-1", '{"m": 1}', "objects", "meta"),
        ("TXV-2", '{"m": 2}', "objects", "meta"),
    }


def test_dump_retries_scan_that_times_out_midway(db_utils, fake_db, no_sleep, tmp_path):
    attempts = []

    def flaky():
        attempts.append(1)
        yield _ScanRes("a", {"n": 1})
        if len(attempts) == 1:
            raise UnAmbiguousTimeoutException()
        yield _ScanRes("b", {"n": 2})

    _fake_bucket(fake_db, {("objects", "meta"): flaky})
    out = tmp_path / "dump.jsonl.gz"

    counts, failed = db_utils.dump_collections(str(out), [("objects", "meta")], fake_db)

    assert (counts, failed) == ({"objects.meta": 2}, [])
    with gzip.open(out, "rt") as f:
        assert [json.loads(line)["id"] for line in f] == ["a", "b"]  # no duplicates


def test_backup_reports_collection_that_keeps_timing_out(
    db_utils, fake_db, no_sleep, tmp_path
):
    def always_times_out():
        raise UnAmbiguousTimeoutException()

    _fake_bucket(
        fake_db,
        {("misc", "idx"): {"2026": 1}, ("xmatch", "hits"): always_times_out},
    )

    dest, failed = db_utils.backup_couchbase(str(tmp_path))

    assert failed == ["xmatch.hits"]
    with gzip.open(dest, "rt") as f:
        assert [json.loads(line)["scope"] for line in f] == ["misc"]


def test_main_backup_exits_nonzero_on_failed_collection(db_utils, monkeypatch):
    monkeypatch.setattr(
        db_utils, "backup_couchbase", lambda *a, **k: ("x.jsonl.gz", ["xmatch.hits"])
    )

    with pytest.raises(SystemExit) as exc:
        db_utils.main(["--backup"])

    assert "xmatch.hits" in str(exc.value.code)


def test_gfs_rotate_handles_jsonl_gz(db_utils, tmp_path):
    today = datetime.date(2026, 9, 29)
    names = {
        "recent": "couchbase-tarxiv-20260928-030000.jsonl.gz",
        "week_newest": "couchbase-tarxiv-20260806-030000.jsonl.gz",
        "week_dup": "couchbase-tarxiv-20260805-030000.jsonl.gz",
        "ancient": "couchbase-tarxiv-20240101-030000.jsonl.gz",
        "partial": "couchbase-tarxiv-20240101-030000.jsonl.gz.partial",
    }
    for name in names.values():
        (tmp_path / name).touch()

    db_utils._gfs_rotate(str(tmp_path), "couchbase-tarxiv", today=today)

    assert sorted(os.listdir(tmp_path)) == sorted([
        names["recent"],
        names["week_newest"],
        names["partial"],
    ])
