"""
Example python script showing how to export the entire database to a JSON file.

Used initially to create a small example database for testing purposes.
"""

import json
import os
import argparse

from tarxiv.database import TarxivDB


def dump_database_to_json(filename=None, limit=None):
    """Export the database to a JSON file, optionally only the first ``limit`` objects."""
    if not filename:
        filename = os.environ.get("DATABASE_EXPORT_FILENAME", "database_export.json")

    # Create database connection
    db = TarxivDB("pipeline", "utils-dump", 1)

    # get objects and create dictionaries to export to JSON
    obj_list = db.get_all_objects()
    if limit:
        obj_list = obj_list[:limit]
    database_json = {}
    for obj in obj_list:
        meta = db.get(obj, scope="objects", collection="meta")
        lc = db.get(obj, scope="objects", collection="lightcurves")
        database_json[obj] = {"meta": meta, "lc": lc}

    # write to JSON file
    with open(filename, mode="w") as f:
        json.dump(database_json, f)


def load_database_from_json(filename=None):
    """Load the entire database from a JSON file."""
    if not filename:
        filename = os.environ.get("DATABASE_EXPORT_FILENAME", "database_export.json")

    # Create database connection
    db = TarxivDB("pipeline", "utils-load", 1)

    # read from JSON file
    with open(filename, mode="r") as f:
        database_json = json.load(f)

    # insert objects into database
    for obj, data in database_json.items():
        db.upsert(obj, data["meta"], scope="objects", collection="meta")
        db.upsert(obj, data["lc"], scope="objects", collection="lightcurves")


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
args = argparser.parse_args()


def main():
    if args.load:
        load_database_from_json(args.filename)
    elif args.dump:
        dump_database_to_json(args.filename, args.limit)
    else:
        print("Please specify either --dump or --load.")


if __name__ == "__main__":
    main()
