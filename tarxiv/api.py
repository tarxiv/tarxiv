import os
import json
import secrets
from typing import cast

from flask import Flask, Blueprint, request, make_response, redirect, session
import cherrypy
from paste.translogger import TransLogger

from .utils import TarxivModule
from .database import TarxivDB
from .auth import sign_token, PROVIDERS, validate_token, TokenStatus, verify_token
from .database_user import (
    UserDB,
    DataLayerError,
    DuplicateValueError,
    AccessDeniedError,
)
from . import dto
from .openapi import build_openapi_spec


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
        self.txv_db = TarxivDB("api", script_name, reporting_mode, debug)
        self.user_db = UserDB(
            script_name="user_db",
            reporting_mode=reporting_mode,
            debug=debug,
        )

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

    def _require_authenticated_user_id(self, token: str | None) -> str:
        validation = self.validate_token_request(token)
        if not validation["is_valid"]:
            if validation["status"] == TokenStatus.EXPIRED:
                raise PermissionError("Session expired — please log in again.")
            raise PermissionError("Invalid or missing token.")

        payload = verify_token(token)
        sub = payload.get("sub")
        if not isinstance(sub, str) or not sub:
            raise PermissionError("Invalid or missing token.")
        return sub

    def routes(self):
        # Basic index route for testing server is running
        @self.app.route("/", methods=["GET"])
        def index():
            return server_response({"status": "TarXiv API is running"}, 200)

        @self.app.route("/openapi.json", methods=["GET"])
        def openapi_json():
            return server_response(build_openapi_spec(), 200)

        @self.app.route("/docs", methods=["GET"])
        def swagger_docs():
            html_content = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>TarXiv API Docs</title>
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css" />
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
  <script>
    window.onload = function() {
      SwaggerUIBundle({
        url: '/openapi.json',
        dom_id: '#swagger-ui',
        presets: [SwaggerUIBundle.presets.apis],
        layout: 'BaseLayout'
      });
    };
  </script>
</body>
</html>
"""
            response = make_response(html_content)
            response.mimetype = "text/html"
            response.headers["Content-Type"] = "text/html; charset=utf-8"
            return response

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
                login_result = PROVIDERS[provider].complete_login(code)
            except Exception as exc:
                self.logger.error(
                    {"oauth_error": str(exc)}, extra={"oauth_error": str(exc)}
                )
                return server_response({"error": "Authentication failed"}, 502)

            dashboard_url = os.environ.get("TARXIV_DASHBOARD_URL", "/")
            provider_profile = cast(dto.ProviderProfile, login_result.get("profile"))
            provider_profile_json = cast(
                dict | None, login_result.get("provider_profile_json")
            )
            sub = cast(str, login_result.get("sub"))
            provider_name = cast(str, login_result.get("provider"))

            if not provider_profile or not sub or not provider_name:
                self.logger.error(
                    {
                        "oauth_error": "Provider did not return expected login payload",
                        "provider": provider,
                        "login_result": str(login_result),
                    },
                    extra={
                        "oauth_error": "Provider did not return expected login payload",
                        "provider": provider,
                    },
                )
                return server_response({"error": "Authentication failed"}, 502)

            try:
                user_dto = self.user_db.get_or_create_user_from_identity(
                    provider=provider_name,
                    profile=provider_profile,
                    provider_profile_json=provider_profile_json,
                )
            except DataLayerError:
                log = {
                    "dashboard_url": dashboard_url,
                    "status": "user sync failed",
                    "provider": provider_name,
                    "provider_user_id": sub,
                }
                self.logger.info(log, extra=log)
                return redirect(f"{dashboard_url.rstrip('/')}")

            token_profile = user_dto.model_dump(mode="json", exclude_none=True)

            token = sign_token(
                sub=str(user_dto.id),
                provider=provider_name,
                profile=token_profile,
            )
            status = {
                "status": "authentication successful, redirecting to dashboard with token",
                "dashboard_url": dashboard_url,
                "token": token,
            }
            self.logger.info(status, extra=status)
            return redirect(f"{dashboard_url.rstrip('/')}/?token={token}")

        @self.app.route("/user", methods=["GET"])
        def get_user_profile():
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                user = self.user_db.get_user(user_id)
                if user is None:
                    return server_response({"error": "User not found"}, 404)
                return server_response(user.model_dump(mode="json"), 200)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/user", methods=["PATCH"])
        def update_user_profile():
            token = request.headers.get("Authorization")
            request_json = request.get_json(silent=True) or {}
            try:
                user_id = self._require_authenticated_user_id(token)
                profile_update = dto.UserProfileUpdate.model_validate(request_json)
                user = self.user_db.update_user_profile(user_id, profile_update)
                if user is None:
                    return server_response({"error": "User not found"}, 404)
                return server_response(user.model_dump(mode="json"), 200)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DuplicateValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 409)
            except ValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 400)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/users/search", methods=["GET"])
        def search_users():
            token = request.headers.get("Authorization")
            query = request.args.get("q", "")
            try:
                self._require_authenticated_user_id(token)
                users = self.user_db.search_users(query)
                return server_response(
                    [user.model_dump(mode="json") for user in users], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/user/teams", methods=["GET"])
        def list_user_teams():
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                memberships = self.user_db.list_user_teams(user_id)
                return server_response(
                    [item.model_dump(mode="json") for item in memberships], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams", methods=["POST"])
        def create_team():
            token = request.headers.get("Authorization")
            request_json = request.get_json(silent=True) or {}
            try:
                user_id = self._require_authenticated_user_id(token)
                team = dto.TeamCreate.model_validate(request_json)
                created_team = self.user_db.create_team(user_id, team)
                return server_response(created_team.model_dump(mode="json"), 201)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except ValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 400)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams/search", methods=["GET"])
        def search_teams():
            token = request.headers.get("Authorization")
            query = request.args.get("q", "")
            try:
                user_id = self._require_authenticated_user_id(token)
                teams = self.user_db.search_teams(user_id, query)
                return server_response(
                    [team.model_dump(mode="json") for team in teams], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams/<string:team_id>/join", methods=["POST"])
        def join_team(team_id):
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                membership = self.user_db.join_team(team_id, user_id)
                return server_response(membership.model_dump(mode="json"), 201)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/user/teams/<string:team_id>", methods=["DELETE"])
        def leave_team(team_id):
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                removed = self.user_db.leave_team(team_id, user_id)
                if not removed:
                    return server_response({"error": "Team membership not found"}, 404)
                return server_response({"status": "left", "team_id": team_id}, 200)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams/<string:team_id>", methods=["PATCH"])
        def update_team(team_id):
            token = request.headers.get("Authorization")
            request_json = request.get_json(silent=True) or {}
            try:
                user_id = self._require_authenticated_user_id(token)
                team_update = dto.TeamUpdate.model_validate(request_json)
                team = self.user_db.update_team(team_id, user_id, team_update)
                if team is None:
                    return server_response({"error": "Team not found"}, 404)
                return server_response(team.model_dump(mode="json"), 200)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DuplicateValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 409)
            except AccessDeniedError as exc:
                return server_response({"error": str(exc), "type": "access"}, 403)
            except ValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 400)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams/<string:team_id>", methods=["DELETE"])
        def delete_team(team_id):
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                removed = self.user_db.delete_team(team_id, user_id)
                if not removed:
                    return server_response({"error": "Team not found"}, 404)
                return server_response({"status": "deleted", "team_id": team_id}, 200)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except AccessDeniedError as exc:
                return server_response({"error": str(exc), "type": "access"}, 403)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams/<string:team_id>/members", methods=["GET"])
        def list_team_members(team_id):
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                members = self.user_db.list_team_members(team_id, user_id)
                return server_response(
                    [member.model_dump(mode="json") for member in members], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except AccessDeniedError as exc:
                return server_response({"error": str(exc), "type": "access"}, 403)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/teams/<string:team_id>/members", methods=["POST"])
        def add_team_member(team_id):
            token = request.headers.get("Authorization")
            request_json = request.get_json(silent=True) or {}
            try:
                user_id = self._require_authenticated_user_id(token)
                membership = dto.TeamMembershipCreate.model_validate(request_json)
                created_membership = self.user_db.add_user_to_team(
                    team_id, user_id, membership
                )
                return server_response(created_membership.model_dump(mode="json"), 201)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DuplicateValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 409)
            except ValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 400)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/tags", methods=["GET"])
        def list_tags():
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                tags = self.user_db.list_tags(user_id)
                return server_response(
                    [tag.model_dump(mode="json") for tag in tags], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                self.logger.exception(
                    "Failed to list tags for authenticated user.",
                    extra={"route": "/tags", "user_id": token},
                )
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/tags", methods=["POST"])
        def create_tag():
            token = request.headers.get("Authorization")
            request_json = request.get_json(silent=True) or {}
            try:
                user_id = self._require_authenticated_user_id(token)
                tag = dto.TagCreate.model_validate(request_json)
                created_tag = self.user_db.create_tag(user_id, tag)
                return server_response(created_tag.model_dump(mode="json"), 201)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except ValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 400)
            except DataLayerError as exc:
                self.logger.exception(
                    "Failed to create tag.",
                    extra={
                        "route": "/tags",
                        "user_id": token,
                        "request_json": request_json,
                    },
                )
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/objects/<string:object_id>/tags", methods=["GET"])
        def list_object_tags(object_id):
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                tags = self.user_db.list_object_tags_for_user(object_id, user_id)
                return server_response(
                    [tag.model_dump(mode="json") for tag in tags], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                self.logger.exception(
                    "Failed to list object tags.",
                    extra={
                        "route": "/objects/<object_id>/tags",
                        "object_id": object_id,
                        "user_id": token,
                    },
                )
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/tags/<string:tag_id>/objects", methods=["GET"])
        def list_objects_for_tag(tag_id):
            token = request.headers.get("Authorization")
            limit = request.args.get("limit", default=100, type=int)
            offset = request.args.get("offset", default=0, type=int)
            try:
                user_id = self._require_authenticated_user_id(token)
                objects = self.user_db.list_objects_for_tag(
                    tag_id, user_id, limit=limit, offset=offset
                )
                return server_response(
                    [item.model_dump(mode="json") for item in objects], 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route("/objects/<string:object_id>/tags", methods=["POST"])
        def assign_object_tag(object_id):
            token = request.headers.get("Authorization")
            request_json = request.get_json(silent=True) or {}
            try:
                user_id = self._require_authenticated_user_id(token)
                assignment = dto.ObjectTagAssignmentCreate.model_validate(request_json)
                created_assignment = self.user_db.assign_tag_to_object(
                    object_id, user_id, assignment
                )
                return server_response(created_assignment.model_dump(mode="json"), 201)
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except ValueError as exc:
                return server_response({"error": str(exc), "type": "validation"}, 400)
            except DataLayerError as exc:
                self.logger.exception(
                    "Failed to assign object tag.",
                    extra={
                        "route": "/objects/<object_id>/tags",
                        "object_id": object_id,
                        "user_id": token,
                        "request_json": request_json,
                    },
                )
                return server_response({"error": str(exc), "type": "server"}, 500)

        @self.app.route(
            "/objects/<string:object_id>/tags/<string:assignment_id>",
            methods=["DELETE"],
        )
        def remove_object_tag(object_id, assignment_id):
            token = request.headers.get("Authorization")
            try:
                user_id = self._require_authenticated_user_id(token)
                removed = self.user_db.remove_object_tag_assignment(
                    assignment_id, user_id
                )
                if not removed:
                    return server_response({"error": "Tag assignment not found"}, 404)
                return server_response(
                    {"status": "deleted", "object_id": object_id}, 200
                )
            except PermissionError as exc:
                return server_response({"error": str(exc), "type": "token"}, 401)
            except DataLayerError as exc:
                self.logger.exception(
                    "Failed to delete object tag.",
                    extra={
                        "route": "/objects/<object_id>/tags/<assignment_id>",
                        "object_id": object_id,
                        "assignment_id": assignment_id,
                        "user_id": token,
                    },
                )
                return server_response({"error": str(exc), "type": "server"}, 500)

        # HFS - 2025-05-28: These self.app.route things are Flask decorators which become
        # endpoints for the API
        @self.app.route("/get_object_meta/<string:source_id>", methods=["POST"])
        def get_object_meta(source_id):
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "meta",
                "query_ip": request.remote_addr,
                "token": token,
                "source_id": source_id,
            }
            try:
                # No token required
                """
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                """
                # Find object info
                result = self.txv_db.get_source_meta(source_id)

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

        @self.app.route("/get_object_lc/<string:catalog>_<string:tarxiv_id>", methods=["POST"])
        def get_object_lc(tarxiv_id):
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "lightcurve",
                "query_ip": request.remote_addr,
                "token": token,
                "tarxiv_id": tarxiv_id,
            }
            try:
                # No token required
                """
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                """
                # Find object info
                result = self.txv_db.get(tarxiv_id, scope="objects", collection="lightcurves")
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
                # No token required
                """
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                """
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
            request_json = request.get_json() or {}
            token = request.headers.get("Authorization")
            # Start log
            log = {
                "query_type": "tns_alerts",
                "query_ip": request.remote_addr,
                "token": token,
                "n_rows": request_json.get("n_rows"),
                "offset": request_json.get("offset"),
                "tag_ids": request_json.get("tag_ids", []),
            }
            try:
                # Return error if bad token
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                if not isinstance(request_json.get("n_rows"), int) or not isinstance(
                    request_json.get("offset"), int
                ):
                    raise ValueError("n_rows/offset must be an integer")
                if not isinstance(request_json.get("tag_ids", []), list):
                    raise ValueError("tag_ids must be a list")

                user_id = self._require_authenticated_user_id(token)
                tag_ids = request_json.get("tag_ids", [])
                tagged_object_ids: list[str] | None = None
                if tag_ids:
                    tagged_object_ids = self.user_db.list_tagged_object_ids_for_user(
                        user_id, tag_ids
                    )
                    if not tagged_object_ids:
                        result = []
                        status_code = 200
                        log["status"] = "Success"
                        self.logger.info(log, extra=log)
                        return server_response(result, status_code)

                object_filter = ""
                if tagged_object_ids is not None:
                    escaped_ids = [
                        object_id.replace("\\", "\\\\").replace('"', '\\"')
                        for object_id in tagged_object_ids
                    ]
                    object_list = ", ".join(
                        f'"{object_id}"' for object_id in escaped_ids
                    )
                    object_filter = f" AND META().id IN [{object_list}]"

                query = f"""SELECT
                              meta.discovery_date,
                              meta.tns.object_id,
                              meta.tns.object_type,
                              meta.ra,
                              meta.dec,
                              meta.tns.redshift,
                              meta.tns.reporting_group,
                              meta.tns.discovery_data_source AS discovery_source
                            FROM tarxiv.objects.meta
                            WHERE meta.source = 'tns' 
                            ORDER BY meta.discovery_date DESC
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
                    "SELECT object_id "
                    "FROM tarxiv.tns.objects obj"
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
                result = [r["object_id"] for r in result]
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
                # No token required
                """
                validation = self.validate_token_request(token)
                if not validation["is_valid"]:
                    if validation["status"] == "expired":
                        raise PermissionError("Session expired — please log in again.")
                    else:
                        raise PermissionError("Invalid or missing token.")
                """
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
        condition_str = f"ANY {field[0]} IN {field} SATISFIES "
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
        predicate = f"{field_name[0]}.{search_field} {operator} {value_str} "
        return predicate


def server_response(content, status_code):
    response = make_response(json.dumps(content))
    response.mimetype = "application/json"
    response.headers["Content-Type"] = "application/json; charset=utf-8"
    response.status_code = status_code
    return response
