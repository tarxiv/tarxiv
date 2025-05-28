from tarxiv.database import TarxivDB
from tarxiv.utils import TarxivModule
from flask import Flask, Blueprint, request, make_response
from paste.translogger import TransLogger
import cherrypy
import json


class API(TarxivModule):
    """API module for server requests to the tarxiv database."""

    def __init__(self, *args, **kwargs):
        super().__init__("api", *args, **kwargs)

        # Get couchbase connection
        self.txv_db = TarxivDB(*args, **kwargs)

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
        self.logger.info({"status": "setting up flask application"})
        self.app = Flask(__name__)
        # Register routes
        self.routes()
        self.app.register_blueprint(Blueprint("main", __name__))

    def start_server(self):
        # Log
        self.logger.info({"status": "starting WSGI server"})
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

    def check_token(self, token):
        # TODO: implement actual authentication
        return token == "TOKEN"

    def routes(self):
        # HFS - 2025-05-28: These self.app.route things are Flask decoratoes which become
        # endpoints for the API
        @self.app.route("/get_object_meta/<string:obj_name>", methods=["POST"])
        def get_object_meta(obj_name):
            # Get request json
            request_json = request.get_json()
            token = request_json["token"]
            # Start log
            log = {
                "query_type": "meta",
                "query_ip": request.remote_addr,
                "token": token,
                "obj_name": obj_name,
            }

            try:
                # Return error if bad token
                if self.check_token(token) is False:
                    raise PermissionError("bad token")
                # Find object info
                result = self.txv_db.get(obj_name, "tns_objects")
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
            finally:
                self.logger.info(log)

            return server_response(result, status_code)

        @self.app.route("/get_object_lc/<string:obj_name>", methods=["POST"])
        def get_object_lc(obj_name):
            # Get request json
            request_json = request.get_json()
            token = request_json["token"]
            # Start log
            log = {
                "query_type": "lightcurve",
                "query_ip": request.remote_addr,
                "token": token,
                "obj_name": obj_name,
            }
            try:
                # Return error if bad token
                if self.check_token(token) is False:
                    raise PermissionError("bad token")
                # Find object info
                result = self.txv_db.get(obj_name, "tns_lightcurves")
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
            finally:
                self.logger.info(log)

            return server_response(result, status_code)

        @self.app.route("/search_objects", methods=["POST"])
        def search_objects():
            # Get request json
            request_json = request.get_json()
            token = request_json["token"]
            search = request_json["search"]
            # Start log
            log = {
                "query_type": "search",
                "query_ip": request.remote_addr,
                "token": token,
                "search": search,
            }
            try:
                # Return error if bad token
                if self.check_token(token) is False:
                    raise PermissionError("bad token")
                # Build query
                query_str = (
                    "SELECT meta().id AS `obj_name` "
                    "FROM tarxiv._default.tns_objects "
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
            finally:
                self.logger.info(log)

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
                    raise ValueError(
                        f"search field contains invalid characters {item}"
                    )
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
