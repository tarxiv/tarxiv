# Database utilities
import traceback

from .utils import TarxivModule, int_to_alphanumeric
from datetime import timedelta

from couchbase.options import ClusterOptions, ClusterTimeoutOptions, IncrementOptions
from couchbase.exceptions import DocumentNotFoundException, SubdocPathMismatchException, PathNotFoundException, \
    AmbiguousTimeoutException
from couchbase.auth import PasswordAuthenticator
from couchbase.cluster import Cluster
import couchbase.subdocument as SD

import json
import os


class TarxivDB(TarxivModule):
    """Interface for TarXiv couchbase data."""

    def __init__(self, user, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="couchbase",
            reporting_mode=reporting_mode,
            debug=debug,
        )
        # Set schema file
        self.schema_file = os.path.join(self.config_dir, "schema.json")

        # Get user (defines permissions)
        if user == "api":
            username = os.environ["TARXIV_COUCHBASE_API_USERNAME"]
            password = os.environ["TARXIV_COUCHBASE_API_PASSWORD"]
        elif user == "pipeline":
            username = os.environ["TARXIV_COUCHBASE_PIPELINE_USERNAME"]
            password = os.environ["TARXIV_COUCHBASE_PIPELINE_PASSWORD"]
        else:
            raise ValueError("user must be 'api' or 'pipeline'")
        # Authenticate
        authenticator = PasswordAuthenticator(username, password)
        timeout_opts = ClusterTimeoutOptions(
            connect_timeout=timedelta(seconds=12), kv_timeout=timedelta(seconds=30)
        )
        options = ClusterOptions(authenticator, timeout_options=timeout_opts)
        # Connect
        status = {"status": "connecting to couchbase"}
        self.logger.info(status, extra=status)
        connection_str = "couchbase://" + os.environ["TARXIV_COUCHBASE_HOST"]
        self.cluster = Cluster(connection_str, options)
        self.cluster.wait_until_ready(timedelta(seconds=10))

        self.conn = self.cluster.bucket("tarxiv")
        status = {"status": "connection success"}
        self.logger.info(status, extra=status)


    def get_object_schema(self):
        """Read object schema from config directory and return it.

        :return: object metadata schema; dict
        """
        with open(self.schema_file) as f:
            return json.load(f)

    def query(self, statement):
        """Run a SQL++ query against couchbase and return results.

        :param statement: valid sql++ query string
        :return: list if query results
        """
        # Log
        status = {"status": "running sql++ query", "statement": statement}
        self.logger.debug(status, extra=status)
        return self.cluster.query(statement)

    def get_all_active_objects(self):
        statement = (
            f"SELECT                                                                          "
            f"  meta.tarxiv_id                                                                "
            f"FROM tarxiv.objects.meta meta                                                   "
            f"JOIN tarxiv.misc.active_settings settings USING(tarxiv_id)                      "
            f"WHERE                                                                           "
            f"   DATE_DIFF_STR(NOW_UTC(), meta.discovery_date,  'day') < settings.active_days "
        )

        result = self.cluster.query(statement)
        return [r["object_id"] for r in result]

    def get_all_objects(self):
        statement = f"SELECT META().id AS tarxiv_id FROM tarxiv.objects.meta"
        result = self.cluster.query(statement)
        return [r["tarxiv_id"] for r in result]

    def set_field(self, doc_id, key, value, scope, collection):
        # Set a specific field in a document
        coll = self.conn.scope(scope).collection(collection)
        coll.mutate_in(doc_id, [SD.upsert(key, value)])


    def upsert(self, doc_id, payload, scope, collection):
        """Insert document into couchbase collection. Update if already exists.

        :param doc_id: name of the object to be used as a document id; str
        :param payload: document to upsert, either metadata or lightcurve; dict or list of dicts
        :param collection: couchbase collection; meta or lightcurve; str
        :return: void
        """
        count = 0
        while True:
            # TRY 5x WITH TIMEOUTS
            try:
                coll = self.conn.scope(scope).collection(collection)
                coll.upsert(doc_id, payload)
                status = {
                    "status": "upserted",
                    "object_id": doc_id,
                    "collection": collection,
                }
                self.logger.info(status, extra=status)
                break
            except AmbiguousTimeoutException:
                count += 1
                if count > 5:
                    status = {
                        "status":  "repeated upsert timeouts",
                        "object_id": doc_id,
                        "collection": collection,
                    }
                    self.logger.error(status, extra=status)
                    print(traceback.format_exc())
                    break


    def lookup_in(self, object_id, sub_field, scope, collection, return_type=str):
        """
        Get a specific field value from a subdocument
        :param object_id: name of the object to be used as a document id; str
        :param sub_field: name of the field to look up; str
        :param collection: couchbase collection; meta or lightcurve; str
        :return:
        """
        try:
            coll = self.conn.scope(scope).collection(collection)
            result = coll.lookup_in(object_id,[SD.get(sub_field)]).content_as[return_type](0)
        except (DocumentNotFoundException, SubdocPathMismatchException, PathNotFoundException):
            result = None
        return result


    def get(self, doc_id, scope, collection):
        """Retrieve a document from couchbase collection based on object_id

        :param doc_id: name of the object to be used as a document id; str
        :param collection: couchbase collection; meta or lightcurve; str
        :return: object document, either metadata or lightcurve; dict or list of dicts
        """
        try:
            coll = self.conn.scope(scope).collection(collection)
            result = coll.get(doc_id).value
            status = {
                "status": "retrieved",
                "object_id": doc_id,
                "collection": collection,
            }
            self.logger.debug(status, extra=status)
        except DocumentNotFoundException:
            status = {
                "status": "no_document",
                "object_id": doc_id,
                "collection": collection,
            }
            self.logger.debug(status, extra=status)
            result = None

        return result

    def get_source_meta(self, source_id):
        try:
            statement = f"""
                SELECT 
                  tarxiv_id,
                  source,
                  source_id,
                  ra,
                  dec,
                  discovery_date,
                  update_date,
                  data_sources
                FROM tarxiv.objects.meta 
                WHERE source_id = '{source_id}'
            """
            result = list(self.cluster.query(statement))[0]["meta"]
            status = {
                "status": "retrieved",
                "source_id": source_id,
            }
            self.logger.debug(status, extra=status)
        except (IndexError, DocumentNotFoundException):
            status = {
                "status": "no_document",
                "object_id": source_id,
            }
            self.logger.debug(status, extra=status)
            result = None

        return result


    def cone_search(self, ra_deg, dec_deg, radius_arcsec):
        """Find objects within radius of coordinates using spherical geometry.

        :param ra_deg: Right Ascension in degrees; float
        :param dec_deg: Declination in degrees; float
        :param radius_arcsec: Search radius in arcseconds; float
        :return: List of matching objects with object_id, ra, dec, distance_deg
        """
        # Convert arcseconds to degrees
        radius_deg = radius_arcsec / 3600.0

        # TODO: (JL) This is a very loose first approximation, feedback would be
        # appreciated. Also not sure how efficient this is in couchbase.
        #
        # SQL++ query using haversine formula for spherical distance
        # Distance = arccos(sin(dec1)*sin(dec2) + cos(dec1)*cos(dec2)*cos(ra1-ra2))
        # Note: 'value' is a reserved keyword in SQL++ so we escape it with backticks
        # Using LET to compute distance, then filter with WHERE
        statement = f"""
            SELECT 
                meta.tarxiv_id,
                meta.source,
                meta.source_id,
                meta.discovery_date,
                meta.ra,
                meta.dec,
                distance_deg
            FROM tarxiv.objects.meta meta
            LET distance_deg = ACOS(
                       SIN(RADIANS({dec_deg})) * SIN(RADIANS(meta.dec)) +
                       COS(RADIANS({dec_deg})) * COS(RADIANS(meta.dec)) *
                       COS(RADIANS({ra_deg} - obj.ra))
                   ) * 180 / PI()
            WHERE 1=1
              AND ABS(meta.dec - {dec_deg}) <= {radius_deg}
              AND distance_deg <= {radius_deg}
            ORDER BY distance_deg
        """

        status = {
            "status": "cone_search",
            "ra": ra_deg,
            "dec": dec_deg,
            "radius_arcsec": radius_arcsec,
        }
        self.logger.info(status, extra=status)

        result = self.cluster.query(statement)
        return list(result)

    def get_txv_id(self, year, object_id=None):
        # If we have an object name, the check if there
        if object_id is not None:
            meta = self.get(object_id, scope="objects", collection='meta')
            # If the object exists, then use its txv-idx
            if meta is not None and "tarxiv_id" in meta.keys():
                return meta["tarxiv_id"]

        # Try 5x if necessary
        count = 0
        while True:
            try:
                # If we have no object name then just generate a new index
                coll = self.conn.scope("misc").collection("idx")
                new_idx = coll.binary().increment(year,
                        IncrementOptions(timeout=timedelta(seconds=30))).content
                # Full detection id will be TXV-2025-xxxxxx
                alpha_id = int_to_alphanumeric(new_idx, self.config["txv_id_len"])
                txv_id = f"TXV-{year}-{alpha_id}"
                status = {
                    "status": "new_txv_idx",
                    "tarxiv_id": txv_id,
                }
                self.logger.info(status, extra=status)
                return txv_id
            except AmbiguousTimeoutException:
                count += 1
                if count > 5:
                    status = {
                        "status":  "repeated txv idx timeouts",
                        "year": year,
                    }
                    self.logger.error(status, extra=status)
                    return None


    def close(self):
        """Close connection to couchbase

        :return:
        """
        self.cluster.close()
