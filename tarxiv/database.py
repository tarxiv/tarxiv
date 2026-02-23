# Database utilities
from .utils import TarxivModule
from couchbase.cluster import Cluster
from couchbase.options import ClusterOptions
from couchbase.auth import PasswordAuthenticator
from couchbase.exceptions import DocumentNotFoundException
import json
import os


class TarxivDB(TarxivModule):
    """Interface for TarXiv couchbase data."""

    def __init__(self, catalog, user, script_name, reporting_mode, debug=False):
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
        options = ClusterOptions(authenticator)
        # Connect
        status = {"status": "connecting to couchbase"}
        self.logger.info(status, extra=status)
        connection_str = "couchbase://" + os.environ["TARXIV_COUCHBASE_HOST"]
        self.cluster = Cluster(connection_str, options)
        self.conn = self.cluster.bucket("tarxiv")
        status = {"status": "connection success"}
        self.logger.info(status, extra=status)

        # Set scope, each catalog will have its own scope
        self.scope = catalog

    def get_object_schema(self):
        """Read object schema from config directory and return it.

        :return: object metadata schema; dict
        """
        with open(self.schema_file) as f:
            return json.load(f)

    def query(self, query_str):
        """Run a SQL++ query against couchbase and return results.

        :param query_str: valid sql++ query string
        :return: list if query results
        """
        # Log
        status = {"status": "running sql++ query", "query_str": query_str}
        self.logger.info(status, extra=status)
        return self.cluster.query(query_str)

    def get_all_active_objects(self, active_days):
        query = (
            f"SELECT                                "
            f"  meta().id as obj_name               "
            f"FROM tarxiv.{self.scope}.objects      "
            f"WHERE                                 "
            f"  ANY `disc_date` IN `discovery_date`                                                 "
            f"   SATISFIES DATE_DIFF_STR(NOW_UTC(), `disc_date`.`value`, 'day') < {active_days} END "
            f" OR                                                                                   "
            f"  ANY `rep_date` IN `reporting_date`                                                  "
            f"   SATISFIES DATE_DIFF_STR(NOW_UTC(), `rep_date`.`value`, 'day') < {active_days} END  "
        )

        result = self.cluster.query(query)
        return [r["obj_name"] for r in result]

    def get_all_objects(self):
        query = f"SELECT meta().id as obj_name FROM tarxiv.{self.scope}.objects"
        result = self.cluster.query(query)
        return [r["obj_name"] for r in result]

    def upsert(self, object_name, payload, collection):
        """Insert document into couchbase collection. Update if already exists.

        :param object_name: name of the object to be used as a document id; str
        :param payload: document to upsert, either metadata or lightcurve; dict or list of dicts
        :param collection: couchbase collection; meta or lightcurve; str
        :return: void
        """
        coll = self.conn.scope(self.scope).collection(collection)
        coll.upsert(object_name, payload)
        status = {
            "status": "upserted",
            "obj_name": object_name,
            "collection": collection,
        }
        self.logger.info(status, extra=status)

    def get(self, object_name, collection):
        """Retrieve a document from couchbase collection based on object_id

        :param object_name: name of the object to be used as a document id; str
        :param collection: couchbase collection; meta or lightcurve; str
        :return: object document, either metadata or lightcurve; dict or list of dicts
        """
        try:
            coll = self.conn.scope(self.scope).collection(collection)
            result = coll.get(object_name).value
            status = {
                "status": "retrieved",
                "obj_name": object_name,
                "collection": collection,
            }
            self.logger.info(status, extra=status)
        except DocumentNotFoundException:
            status = {
                "status": "no_document",
                "obj_name": object_name,
                "collection": collection,
            }
            self.logger.warn(status, extra=status)
            result = None

        return result

    def cone_search(self, ra_deg, dec_deg, radius_arcsec):
        """Find objects within radius of coordinates using spherical geometry.

        :param ra_deg: Right Ascension in degrees; float
        :param dec_deg: Declination in degrees; float
        :param radius_arcsec: Search radius in arcseconds; float
        :return: List of matching objects with obj_name, ra, dec, distance_deg
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
        query = f"""
            SELECT meta().id as obj_name,
                   obj.ra_deg[0].`value` as ra,
                   obj.dec_deg[0].`value` as dec,
                   distance_deg
            FROM tarxiv.{self.scope}.objects obj
            LET distance_deg = ACOS(
                       SIN(RADIANS({dec_deg})) * SIN(RADIANS(obj.dec_deg[0].`value`)) +
                       COS(RADIANS({dec_deg})) * COS(RADIANS(obj.dec_deg[0].`value`)) *
                       COS(RADIANS({ra_deg} - obj.ra_deg[0].`value`))
                   ) * 180 / PI()
            WHERE obj.ra_deg IS NOT NULL
              AND obj.dec_deg IS NOT NULL
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

        result = self.cluster.query(query)
        return list(result)

    def close(self):
        """Close connection to couchbase

        :return:
        """
        self.cluster.close()
