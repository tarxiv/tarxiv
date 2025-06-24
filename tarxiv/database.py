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

    def __init__(self, catalog, user, *args, **kwargs):
        """Read in object schema and connect to couchbase."""
        super().__init__("couchbase", *args, **kwargs)
        # Set schema file
        self.schema_file = os.path.join(self.config_dir, "schema.json")

        # Get user (defines permissions)
        if user == "api":
            username = os.environ["TARXIV_COUCHBASE_API_USER"]
            password = os.environ["TARXIV_COUCHBASE_API_PASS"]
        elif user == "pipeline":
            username = os.environ["TARXIV_COUCHBASE_PIPELINE_USER"]
            password = os.environ["TARXIV_COUCHBASE_PIPELINE_PASS"]
        else:
            raise ValueError("user must be 'api' or 'pipeline'")
        # Authenticate
        authenticator = PasswordAuthenticator(username, password)
        options = ClusterOptions(authenticator)
        # Connect
        self.logger.info({"status": "connecting to couchbase"})
        connection_str = "couchbase://" + self.config["database"]["host"]
        self.cluster = Cluster(connection_str, options)
        self.conn = self.cluster.bucket("tarxiv")
        self.logger.info({"status": "connection success"})

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
        self.logger.info({"status": "running sql++ query", "query_str": query_str})
        return self.cluster.query(query_str)

    def get_all_active_objects(self, active_days):
        query = f"SELECT                                " \
                f"  meta().id as obj_name               " \
                f"FROM tarxiv.{self.scope}.objects      " \
                f"WHERE                                 " \
                f" ANY `disc_date` IN `discovery_date`  "\
                f"  SATISFIES DATE_DIFF_STR(NOW_UTC(), `disc_date`.`value`, 'day') < {active_days} END"
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
        self.logger.info({
            "status": "upserted",
            "object_name": object_name,
            "collection": collection,
        })

    def get(self, object_name, collection):
        """Retrieve a document from couchbase collection based on object_id

        :param object_name: name of the object to be used as a document id; str
        :param collection: couchbase collection; meta or lightcurve; str
        :return: object document, either metadata or lightcurve; dict or list of dicts
        """
        try:
            coll = self.conn.scope(self.scope).collection(collection)
            result = coll.get(object_name).value
            self.logger.info({
                "status": "retrieved",
                "object_name": object_name,
                "collection": collection,
            })
        except DocumentNotFoundException:
            self.logger.warn({
                "status": "no_document",
                "object_name": object_name,
                "collection": collection,
            })
            result = None
        return result

    def close(self):
        """Close connection to couchbase

        :return:
        """
        self.cluster.close()
