import os
import json
import secrets

from flask import Flask, Blueprint, request, make_response, redirect, session
import cherrypy
from paste.translogger import TransLogger

from .utils import TarxivModule
from .database import TarxivDB
from .auth import sign_token, PROVIDERS, validate_token, TokenStatus


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
        cherrypy.config.update(
            {
                "engine.autoreload.on": True,
                "log.screen": True,
                "server.socket_port": self.config["api_port"],
                "server.socket_host": "0.0.0.0",
            }
        )
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
                if type(request_json["n_rows"]) != int or type(request_json["offset"]) != int:
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
                result = self.txv_db.query(query)

                if result is None:
                    raise LookupError("bad lookup")

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

        # @self.app.route("/search_objects", methods=["POST"])
        # def search_objects():
        #     # Get request json
        #     request_json = request.get_json()
        #     self.logger.info(f"search_objects request: {request_json}")
        #     token = request.headers.get("Authorization")
        #     self.logger.info(f"search_objects token: {token}")
        #     # search = request_json["search"]
        #     # resquest_json = request.
        #     # self.logger.info(f"search_objects search: {search}")
        #     self.logger.info(f"search_objects request: {request}")
        #     self.logger.info(f"search_objects request json: {request_json}")
        #     search = request_json.get("search", {})
        #     # Start log
        #     log = {
        #         "query_type": "search",
        #         "query_ip": request.remote_addr,
        #         "token": token,
        #         "search": search,
        #     }
        #     try:
        #         # Return error if bad token
        #         validation = self.validate_token_request(token)
        #         if not validation["is_valid"]:
        #             raise PermissionError("bad token")
        #         # Build query
        #         query_str = (
        #             "SELECT meta().id AS `obj_name` "
        #             "FROM tarxiv.tns.objects "
        #             "WHERE 1=1 AND "
        #         )
        #         # Add restrictions from search fields, then append search params to query
        #         condition_list = []
        #         for field, condition in search.items():
        #             condition_str = self.build_condition(field, condition)
        #             condition_list.append(condition_str)
        #         # Append full condition string to query string
        #         full_condition_string = " AND ".join(condition_list)
        #         query_str += full_condition_string
        #         # Return results
        #         result = self.txv_db.query(query_str)
        #         result = [r["obj_name"] for r in result]
        #         status_code = 200
        #         log["status"] = "Success"
        #     except PermissionError as e:
        #         result = {"error": str(e), "type": "token"}
        #         status_code = 401
        #         log["status"] = "PermissionError"
        #     except LookupError as e:
        #         result = {"error": str(e), "type": "lookup"}
        #         status_code = 404
        #         log["status"] = "LookupError"
        #     except Exception as e:
        #         result = {"error": str(e), "type": "server"}
        #         status_code = 500
        #         log["status"] = "ServerError"

        #     self.logger.info(log, extra=log)
        #     return server_response(result, status_code)

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
