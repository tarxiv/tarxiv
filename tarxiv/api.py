import os
import json
import secrets

from flask import Flask, Blueprint, request, make_response, redirect, session
import cherrypy
from paste.translogger import TransLogger

from .utils import TarxivModule
from .database import TarxivDB
from .auth import sign_token, PROVIDERS, validate_token, TokenStatus


# Temporary fixture used by the /get_object_meta_dummy endpoint. This mirrors
# the forthcoming source-keyed metadata schema (see docs/dev-notes/new_sample.json)
# so the dashboard object page can be exercised before the real endpoint emits it.
# TODO: remove once /get_object_meta returns the new schema.
DUMMY_OBJECT_META = {
    "tarxiv_id": "TXV-2026-08656c6c6f",
    "source": "TNS",
    "ra": "03:06:55.682",
    "dec": "-11:58:55.51",
    "data_sources": {
        "tns": {
            "identifier": "2025abov",
            "ra_deg": 46.7317828801,
            "dec_deg": -11.982086061,
            "object_type": "SN Ia",
            "discovery_date": "2025-10-25 13:01:50.016",
            "reporting_group": "GOTO",
            "discovery_data_source": "GOTO",
            "redshift": 0.01346,
        },
        "asas_sn": {
            "identifier": "661432068951",
            "ra_deg": 46.733154,
            "dec_deg": 11.983448,
            "latest_nondetection": [
                {
                    "value": 19.08,
                    "filter": "g",
                    "date": "2025-12-08 01:48:35.990",
                    "mag_rate": None,
                }
            ],
            "latest_detection": [
                {
                    "value": 16.831,
                    "filter": "g",
                    "date": "2025-12-23 02:39:35.068",
                    "mag_rate": -0.089595,
                }
            ],
            "peak_mag": [
                {
                    "value": 14.983,
                    "filter": "g",
                    "date": "2025-11-11 05:28:31.274",
                    "mag_rate": None,
                }
            ],
        },
        "sherlock": {
            "mag": 13.938,
            "mag_err": 0.0,
            "mag_filter": "r",
            "association_type": "SN",
            "best_distance": 57.628,
            "best_distance_flag": "sz",
            "best_distance_source": "LASr 100 Mpc Galaxy Catalogue v1.0",
            "catalogue_object_id": "MCG-02-08-052",
            "catalogue_object_type": "galaxy",
            "catalogue_table_name": "LASR/2MASS/PS1/DESI",
            "classificationReliability": 2,
            "dec_deg": -11.98342816,
            "east_separation_arcsec": 4.885,
            "north_separation_arcsec": -4.874,
            "physical_separation_kpc": 1.852,
            "ra_deg": 46.733144064,
            "separation_arcsec": 6.806,
            "redshift": 0.013319,
        },
        "ztf": {
            "identifier": "ZTF25acbsugc",
            "ra_deg": 46.7317439,
            "dec_deg": -11.982109,
            "peak_mag": [
                {
                    "value": 15.945535,
                    "filter": "R",
                    "date": "2025-12-06 07:16:53.000",
                    "mag_rate": None,
                },
                {
                    "value": 17.02721,
                    "filter": "g",
                    "date": "2025-12-06 05:36:02.002",
                    "mag_rate": None,
                },
            ],
            "latest_detection": [
                {
                    "value": 16.901502999999998,
                    "filter": "R",
                    "date": "2025-12-22 03:59:29.003",
                    "mag_rate": -0.057192,
                },
                {
                    "value": 17.859348,
                    "filter": "g",
                    "date": "2025-12-22 05:04:52.997",
                    "mag_rate": -0.053274,
                },
            ],
        },
    },
}


class API(TarxivModule):
    """API module for server requests to the tarxiv database."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="api",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        self.logger.info(
            {"status": "initializing API module"},
            extra={"status": "initializing API module"},
        )
        # Get couchbase connection
        self.txv_db = TarxivDB("tns", "api", script_name, reporting_mode, debug)

        # Survey name/alias map (could write better, but fuck it)
        self.survey_source_map = {
            "TNS": 0,
            "ATLAS": 2,
            "ZTF": 3,
            "ASAS-SN": 5,
            "SHERLOCK": 7,
            "MANGROVE": 8,
        }

        # Now build a dictionary of valid values
        self.valid_operators = ["<", ">", "=", "<=", ">=", "IN", "LIKE"]

        # Build application
        status = {"status": "setting up flask application"}
        self.logger.info(status, extra=status)
        self.app = Flask(__name__)
        self.app.secret_key = os.environ.get(
            "TARXIV_API_SECRET_KEY"
        ) or secrets.token_hex(32)
        # Register routes
        self.routes()
        self.app.register_blueprint(Blueprint("main", __name__))

    def start_server(self):
        # Log
        status = {"status": "starting WSGI server"}
        self.logger.info(status, extra=status)
        # Enable WSGI access logging via Paste
        app_logged = TransLogger(self.app)
        # Mount the WSGI callable object (app) on the root directory
        cherrypy.tree.graft(app_logged, "/")
        # Set the configuration of the web server
        cherrypy.config.update({
            "engine.autoreload.on": True,
            "log.screen": True,
            "server.socket_port": self.config["api_port"],
            "server.socket_host": "0.0.0.0",
        })
        # Start the CherryPy WSGI web server
        cherrypy.engine.start()
        cherrypy.engine.block()

    def validate_token_request(self, token: str) -> dict:
        """Validate a JWT and return structured status for error handling."""
        result = validate_token(token)
        return {
            "is_valid": result["status"] == TokenStatus.VALID,
            "status": result["status"],
            "profile": result["profile"],
            "error": result["error"],
        }

    def routes(self):
        # Basic index route for testing server is running
        @self.app.route("/", methods=["GET"])
        def index():
            return server_response({"status": "TarXiv API is running"}, 200)

        @self.app.route("/auth/<string:provider>/login", methods=["GET"])
        def auth_login(provider):
            status = {"status": f"login attempt for provider {provider}"}
            self.logger.info(status, extra=status)
            if provider not in PROVIDERS:
                return server_response({"error": f"Unknown provider: {provider}"}, 404)
            state = secrets.token_urlsafe(16)
            session["oauth_state"] = state
            session["oauth_provider"] = provider
            try:
                auth_url = PROVIDERS[provider].build_authorize_url(state)
            except RuntimeError as exc:
                return server_response({"error": str(exc)}, 500)
            status = {
                "status": f"redirecting to {provider} for authentication",
                "auth_url": auth_url,
            }
            self.logger.info(status, extra=status)
            return redirect(auth_url)

        @self.app.route("/auth/<string:provider>/callback", methods=["GET"])
        def auth_callback(provider):
            status = {"status": f"handling callback from provider {provider}"}
            self.logger.info(status, extra=status)

            if provider not in PROVIDERS:
                return server_response({"error": f"Unknown provider: {provider}"}, 404)

            state = request.args.get("state")
            code = request.args.get("code")

            status = {"status": f"received callback with state {state} and code {code}"}
            self.logger.info(status, extra=status)

            if not code:
                return server_response({"error": "Missing authorization code"}, 400)
            expected_state = session.pop("oauth_state", None)
            if expected_state and state != expected_state:
                return server_response({"error": "Invalid OAuth state"}, 400)

            status = {
                "status": f"completing login for provider {provider} with code {code}"
            }
            self.logger.info(status, extra=status)

            try:
                result = PROVIDERS[provider].complete_login(code)
            except Exception as exc:
                self.logger.error(
                    {"oauth_error": str(exc)}, extra={"oauth_error": str(exc)}
                )
                return server_response({"error": "Authentication failed"}, 502)
            token = sign_token(
                sub=result["sub"],
                provider=result["provider"],
                profile=result["profile"],
            )
            dashboard_url = os.environ.get("TARXIV_DASHBOARD_URL", "/")
            status = {
                "status": "authentication successful, redirecting to dashboard with token",
                "dashboard_url": dashboard_url,
                "token": token,
            }
            self.logger.info(status, extra=status)
            return redirect(f"{dashboard_url.rstrip('/')}/?token={token}")

        # HFS - 2025-05-28: These self.app.route things are Flask decorators which become
        # endpoints for the API
        @self.app.route("/get_object_meta/<string:obj_name>", methods=["POST"])
        def get_object_meta(obj_name):
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "meta",
                "query_ip": request.remote_addr,
                "token": token,
                "obj_name": obj_name,
            }

            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                # Find object info
                result = self.txv_db.get(obj_name, "objects")
                # Return nothing if bad request
                if result is None:
                    raise LookupError("no such object")
                # Normal return
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
                log["status"] = "LookupError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"

            self.logger.info(log, extra=log)
            return server_response(result, status_code)

        @self.app.route("/get_object_meta_dummy/<string:obj_name>", methods=["POST"])
        def get_object_meta_dummy(obj_name):
            """Return a static new-schema metadata document for testing.

            Mirrors get_object_meta's auth handling but serves DUMMY_OBJECT_META
            instead of querying the database, so the dashboard object page can be
            exercised before the real endpoint emits the source-keyed schema.
            """
            token = request.headers.get("Authorization")
            log = {
                "query_type": "meta_dummy",
                "query_ip": request.remote_addr,
                "token": token,
                "obj_name": obj_name,
            }
            try:
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                # Echo the requested object id so the page reflects the search.
                result = {**DUMMY_OBJECT_META, "tarxiv_id": obj_name}
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"

            self.logger.info(log, extra=log)
            return server_response(result, status_code)

        @self.app.route("/get_object_lc/<string:obj_name>", methods=["POST"])
        def get_object_lc(obj_name):
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "lightcurve",
                "query_ip": request.remote_addr,
                "token": token,
                "obj_name": obj_name,
            }
            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                # Find object info
                result = self.txv_db.get(obj_name, "lightcurves")
                # Return nothing if bad request
                if result is None:
                    raise LookupError("no such object")
                # Normal return
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
                log["status"] = "LookupError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"

            self.logger.info(log, extra=log)
            return server_response(result, status_code)

        @self.app.route("/citations", methods=["POST"])
        def citations():
            request_json = request.get_json()
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "tns_alerts",
                "query_ip": request.remote_addr,
                "token": token,
                "sources": request_json["sources"],
            }
            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")

                # Get all relevant citations
                citations = []
                for source in request_json["sources"]:
                    with open(
                        os.path.join(self.config_dir, "citations", f"{source}.bib"),
                        mode="r",
                    ) as f:
                        citations.append(f.read())

                # Return as one big printable string
                citation_str = "\n".join(citations)
                result = {"citations": citation_str}

                # Normal return
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
                log["status"] = "LookupError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"

            self.logger.info(log, extra=log)
            return server_response(result, status_code)

        @self.app.route("/tns_alerts", methods=["POST"])
        def tns_alerts():
            request_json = request.get_json()
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "tns_alerts",
                "query_ip": request.remote_addr,
                "token": token,
                "n_rows": request_json["n_rows"],
                "offset": request_json["offset"],
            }
            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                if not isinstance(request_json["n_rows"], int) or not isinstance(
                    request_json["offset"], int
                ):
                    raise ValueError("n_rows/offset must be an integer")

                query = f"""SELECT
                              `objects`.`internal`.`insert_date` AS date_received,
                              META().id AS obj_name,
                              `objects`.`object_type`[0].`value` AS object_type,
                              `objects`.`ra_hms`[0].`value` AS ra,
                              `objects`.`dec_dms`[0].`value` AS dec,
                              `objects`.`discovery_data_source`[0].`value` AS discovery_source,
                              `objects`.`reporting_group`[0].`value` AS reporting_group,
                              IFMISSING(`objects`.`redshift`[0].`value`, "") AS redshift
                            FROM tarxiv.tns.objects
                            WHERE `objects`.`internal`.`insert_date` IS NOT MISSING
                            ORDER BY `objects`.`internal`.`insert_date` DESC
                            LIMIT {request_json["n_rows"]} OFFSET {request_json["offset"]}"""
                result = list(self.txv_db.query(query))

                # Normal return
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
                log["status"] = "LookupError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"

            self.logger.info(log, extra=log)
            return server_response(result, status_code)

        @self.app.route("/search_objects", methods=["POST"])
        def search_objects():
            # Get request json
            request_json = request.get_json()
            self.logger.info(f"search_objects request: {request_json}")
            token = request.headers.get("Authorization")
            search = request_json.get("search", {})
            # Start log
            log = {
                "query_type": "search",
                "query_ip": request.remote_addr,
                "token": token,
                "search": search,
            }
            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    raise PermissionError("bad token")
                # Build query
                query_str = (
                    "SELECT meta().id AS `obj_name` "
                    "FROM tarxiv.tns.objects "
                    "WHERE 1=1 AND "
                )
                # Add restrictions from search fields, then append search params to query
                condition_list = []
                for field, condition in search.items():
                    condition_str = self.build_condition(field, condition)
                    condition_list.append(condition_str)
                # Append full condition string to query string
                full_condition_string = " AND ".join(condition_list)
                query_str += full_condition_string
                # Return results
                result = self.txv_db.query(query_str)
                result = [r["obj_name"] for r in result]
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
                log["status"] = "LookupError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"

            self.logger.info(log, extra=log)
            return server_response(result, status_code)

        @self.app.route("/cone_search", methods=["POST"])
        def cone_search():
            request_json = request.get_json()
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "cone_search",
                "query_ip": request.remote_addr,
                "token": token,
                "request": request_json,
            }
            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                # Extract parameters
                ra = request_json["ra"]
                dec = request_json["dec"]
                radius = request_json["radius"]
                # Perform cone search
                # self.logger.info(
                #     f"Performing cone search ra: {ra}, dec: {dec}, radius: {radius}"
                # )
                result = self.txv_db.cone_search(ra, dec, radius)
                # self.logger.info(f"Cone search result: {result}")
                # Normal return
                status_code = 200
                log["status"] = "Success"
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
                log["status"] = "PermissionError"
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
                log["status"] = "LookupError"
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
                log["status"] = "ServerError"
            self.logger.info(log, extra=log)
            return server_response(result, status_code)

    def build_condition(self, field, condition):
        # Start condition_string
        condition_str = f"ANY `{field[0]}` IN `{field}` SATISFIES "
        predicates = []
        # Each query has a number of parameters (usually just value, but peak mag can search on filter/mjd also)
        for param in condition:
            # First check value fields
            if "value" in param.keys():
                prd_str = self.build_predicate(
                    field, "value", param["operator"], param["value"]
                )
            elif "filter" in param.keys():
                prd_str = self.build_predicate(
                    field, "filter", param["operator"], param["filter"]
                )
            elif "mjd" in param.keys():
                prd_str = self.build_predicate(
                    field, "mjd", param["operator"], param["mjd"]
                )
            else:
                raise ValueError(f"bad search option {param}")
            # Add predicate to condition
            predicates.append(prd_str)

        return condition_str + "AND ".join(predicates) + "END "

    def build_predicate(self, field_name, search_field, operator, search_value):
        # Check valid operators
        if operator not in self.valid_operators:
            raise ValueError(f"bad operator {operator}")
        # Simple check against SQL injection, allow max two words in query string, semicolons or comment str
        if isinstance(search_value, str):
            if any(char in search_value for char in [";", "/*", "*/", "--"]):
                raise ValueError(
                    f"search field contains invalid characters {search_value}"
                )
        if isinstance(search_value, list):
            for item in search_value:
                if any(char in str(item) for char in [";", "/*", "*/", "--"]):
                    raise ValueError(f"search field contains invalid characters {item}")
        # Format predicate search value
        if isinstance(search_value, int) or isinstance(search_value, float):
            value_str = str(search_value)
        elif isinstance(search_value, str):
            value_str = f"'{search_value}'"
        elif isinstance(search_value, list):
            value_str = str(search_value)
        else:
            raise ValueError(f"bad search value {search_value}")
        # Build predicate
        predicate = f"`{field_name[0]}`.`{search_field}` {operator} {value_str} "
        return predicate


def server_response(content, status_code):
    response = make_response(json.dumps(content))
    response.mimetype = "application/json"
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.status_code = status_code
    return response
