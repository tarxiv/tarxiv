"""
Example python script showing how to export/import the database to/from JSON.

Used initially to create a small example database for testing purposes.

Supports two couchbase layouts via ``--legacy``:

* new (default): metadata under the ``objects`` scope (``tarxiv.objects.meta``)
* old/legacy: metadata under the ``tns`` scope (``tarxiv.tns.objects``)

so an old-schema database can be dumped and reloaded into the old scope.
"""

import json
import os
import argparse

from tarxiv.database import TarxivDB

# Couchbase scope/collection layout for each schema generation. ``meta`` is the
# collection holding object metadata; ``lc`` holds the lightcurves. The new
# schema keeps both under the ``objects`` scope; the legacy schema kept them
# under the ``tns`` scope with the metadata collection named ``objects``.
SCHEMA_LAYOUTS = {
    "new": {"scope": "objects", "meta": "meta", "lc": "lightcurves"},
    "old": {"scope": "tns", "meta": "objects", "lc": "lightcurves"},
}


def _list_object_ids(db, scope, collection):
    """Return all document ids in ``tarxiv.<scope>.<collection>``."""
    statement = f"SELECT META().id AS id FROM tarxiv.{scope}.{collection}"
    return [row["id"] for row in db.query(statement)]


def dump_database_to_json(filename=None, limit=None, layout="new"):
    """Export the database to a JSON file, optionally only the first ``limit`` objects.

    ``layout`` selects the couchbase scope/collections to read from: ``"new"``
    (the current ``objects`` scope) or ``"old"`` (the legacy ``tns`` scope).
    """
    if not filename:
        filename = os.environ.get("DATABASE_EXPORT_FILENAME", "database_export.json")

    paths = SCHEMA_LAYOUTS[layout]

    # Create database connection
    db = TarxivDB("pipeline", "utils-dump", 1)

    # get objects and create dictionaries to export to JSON
    obj_list = _list_object_ids(db, paths["scope"], paths["meta"])
    if limit:
        obj_list = obj_list[:limit]
    database_json = {}
    for obj in obj_list:
        meta = db.get(obj, scope=paths["scope"], collection=paths["meta"])
        lc = db.get(obj, scope=paths["scope"], collection=paths["lc"])
        database_json[obj] = {"meta": meta, "lc": lc}

    # write to JSON file
    with open(filename, mode="w") as f:
        json.dump(database_json, f)


def load_database_from_json(filename=None, layout="new"):
    """Load the entire database from a JSON file into the selected schema scope."""
    if not filename:
        filename = os.environ.get("DATABASE_EXPORT_FILENAME", "database_export.json")

    paths = SCHEMA_LAYOUTS[layout]

    # Create database connection
    db = TarxivDB("pipeline", "utils-load", 1)

    # read from JSON file
    with open(filename, mode="r") as f:
        database_json = json.load(f)

    # insert objects into database
    for obj, data in database_json.items():
        db.upsert(obj, data["meta"], scope=paths["scope"], collection=paths["meta"])
        db.upsert(obj, data["lc"], scope=paths["scope"], collection=paths["lc"])


def build_argparser():
    argparser = argparse.ArgumentParser(
        description="Dump or load the entire database to/from a JSON file."
    )
    argparser.add_argument(
        "--dump", "-d", action="store_true", help="Dump the database to a JSON file."
    )
    argparser.add_argument(
        "--load",
        "-l",
        action="store_true",
        help="Load the database from a JSON file instead of dumping it.",
    )
    argparser.add_argument(
        "--filename", "-f", type=str, help="The JSON file to load from or dump to."
    )
    argparser.add_argument(
        "--limit",
        "-n",
        type=int,
        default=None,
        help="Only dump the first N objects (default: all). Ignored when loading.",
    )
    argparser.add_argument(
        "--legacy",
        "--old-tns-scope",
        dest="legacy",
        action="store_true",
        help=(
            "Use the legacy TNS scope (tarxiv.tns.objects / tarxiv.tns.lightcurves) "
            "instead of the new objects scope, for both dumping and loading."
        ),
    )
    return argparser


def main(argv=None):
    args = build_argparser().parse_args(argv)
    layout = "old" if args.legacy else "new"
    if args.load:
        load_database_from_json(args.filename, layout=layout)
    elif args.dump:
        dump_database_to_json(args.filename, args.limit, layout=layout)
    else:
        print("Please specify either --dump or --load.")


if __name__ == "__main__":
    main()
