import datetime

from authlib.jose.rfc7519.jwt import find_encode_key
from tarxiv.database import TarxivDB
from tarxiv.utils import TarxivModule
from flask import Flask, Blueprint, request, make_response
from paste.translogger import TransLogger

import cherrypy
import json


class API(TarxivModule):
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
            "MANGROVE": 8
        }

        # Now build a dictionary of valid values
        self.valid_fields = {
            "filter": self.txv_db.valid_filters(),
            "object_type": self.txv_db.valid_object_types(),
            "reporting_group": self.txv_db.valid_groups(),

        }
        self.valid_operators = ['<', '>', '=', '<=', '>=', "IN"]


        # Build application
        self.app = Flask(__name__)
        self.app.register_blueprint(Blueprint('main', __name__))

        # Enable WSGI access logging via Paste
        app_logged = TransLogger(self.app)

        # Mount the WSGI callable object (app) on the root directory
        cherrypy.tree.graft(app_logged, '/')

        # Set the configuration of the web server
        cherrypy.config.update({
            'engine.autoreload.on': True,
            'log.screen': True,
            'server.socket_port': self.config['api_port'],
            'server.socket_host': '0.0.0.0'
        })

        # Start the CherryPy WSGI web server
        cherrypy.engine.start()
        cherrypy.engine.block()

    def check_token(self, token):
        return token == 'TOKEN'

    def routes(self):
        @self.app.route('/get_object_meta/<string:obj_name>', methods=['POST'])
        def get_object_meta(obj_name):
            # Get request json
            request_json = request.get_json()
            token = request_json['token']
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
            except PermissionError as e:
                result = {"error": str(e), "type": "token"}
                status_code = 401
            except LookupError as e:
                result = {"error": str(e), "type": "lookup"}
                status_code = 404
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
            finally:
                return server_response(result, status_code)

        @self.app.route('/get_object_lc/<string:obj_name>', methods=['POST'])
        def get_object_lc(obj_name):

            # Get request json
            request_json = request.get_json()
            token = request_json['token']
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
            except PermissionError as e:
                result = {"error": str(e)}
                status_code = 401
            except LookupError as e:
                result = {"error": str(e)}
                status_code = 404
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500
            finally:
                return server_response(result, status_code)

        @self.app.route('/search_objects', methods=['POST'])
        def search_objects():
            # Get request json
            request_json = request.get_json()
            token = request_json['token']
            try:
                # Return error if bad token
                if self.check_token(token) is False:
                    raise PermissionError("bad token")
                # Build query
                query_str = ("SELECT * "
                             "FROM the tarxiv._default.tns_objects "
                             "WHERE 1=1 ")

                # Add restrictions from search fields, then append search params to query
                condition_list = []
                for field in request_json['search_fields']:
                    pass


            except PermissionError as e:
                result = {"error": str(e)}
                status_code = 401
            except LookupError as e:
                result = {"error": str(e)}
                status_code = 404
            except Exception as e:
                result = {"error": str(e), "type": "server"}
                status_code = 500

    def build_condition(self, query_json):
        field_name = query_json["field"]
        # Start condition_string
        condition_str = f"ANY `{field_name[0]}` IN `{field_name}` SATISFIES "
        predicates = []
        # Each query has a number of parameters (usually just value, but peak mag can search on filter/mjd also)
        for param in query_json['search']:
            # First check value fields
            if "value" in param.keys():
                prd_str = self.build_predicate(field_name, "value", param["operator"], param["value"])
            elif "filter" in param.keys():
                prd_str = self.build_predicate(field_name, "filter", param["operator"], param["filter"])
            elif "mjd" in param.keys():
                prd_str = self.build_predicate(field_name, "mjd", param["operator"], param["mjd"])
            else:
                raise ValueError(f"bad search option {param}")
            # Add predicate to condition
            predicates.append(prd_str)

        return condition_str + "AND ".join(predicates) + "END "

    def build_predicate(self, field_name, operator, operator_value, value):

        return ""


def server_response(content, status_code):
    response = make_response(json.dumps(content))
    response.mimetype = 'application/json'
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.status_code = status_code
    return response





