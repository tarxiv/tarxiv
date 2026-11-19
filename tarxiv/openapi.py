from . import dto


def build_openapi_spec() -> dict:
    ref_template = "#/components/schemas/{model}"
    bearer_auth = [{"BearerAuth": []}]
    comment_ref = {"$ref": "#/components/schemas/Comment"}

    def json_body(schema: dict) -> dict:
        return {"application/json": {"schema": schema}}

    def path_param(name: str, fmt: str | None = None) -> dict:
        schema = {"type": "string", **({"format": fmt} if fmt else {})}
        return {"name": name, "in": "path", "required": True, "schema": schema}

    source_id_param = path_param("source_id")
    comment_id_param = path_param("comment_id", "uuid")

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "TarXiv API",
            "version": "0.0.9",
            "description": (
                "API for TarXiv object lookup, alerts, search, authentication, "
                "user profiles, teams, and object tagging."
            ),
        },
        "components": {
            "securitySchemes": {
                "BearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                }
            },
            "schemas": {
                "ErrorResponse": {
                    "type": "object",
                    "properties": {
                        "error": {"type": "string"},
                        "type": {"type": "string"},
                    },
                    "required": ["error"],
                },
                "User": dto.User.model_json_schema(ref_template=ref_template),
                "UserSummary": dto.UserSummary.model_json_schema(
                    ref_template=ref_template
                ),
                "UserProfileUpdate": dto.UserProfileUpdate.model_json_schema(
                    ref_template=ref_template
                ),
                "Team": dto.Team.model_json_schema(ref_template=ref_template),
                "TeamSummary": dto.TeamSummary.model_json_schema(
                    ref_template=ref_template
                ),
                "TeamCreate": dto.TeamCreate.model_json_schema(
                    ref_template=ref_template
                ),
                "TeamUpdate": dto.TeamUpdate.model_json_schema(
                    ref_template=ref_template
                ),
                "TeamMembership": dto.TeamMembership.model_json_schema(
                    ref_template=ref_template
                ),
                "TeamMembershipCreate": dto.TeamMembershipCreate.model_json_schema(
                    ref_template=ref_template
                ),
                "TeamMemberView": dto.TeamMemberView.model_json_schema(
                    ref_template=ref_template
                ),
                "Tag": dto.Tag.model_json_schema(ref_template=ref_template),
                "TagCreate": dto.TagCreate.model_json_schema(ref_template=ref_template),
                "ObjectTagAssignmentCreate": (
                    dto.ObjectTagAssignmentCreate.model_json_schema(
                        ref_template=ref_template
                    )
                ),
                "ObjectTagAssignmentView": dto.ObjectTagAssignmentView.model_json_schema(
                    ref_template=ref_template
                ),
                "Comment": dto.Comment.model_json_schema(ref_template=ref_template),
                "CommentCreate": dto.CommentCreate.model_json_schema(
                    ref_template=ref_template
                ),
                "CommentUpdate": dto.CommentUpdate.model_json_schema(
                    ref_template=ref_template
                ),
                "CommentCountsRequest": dto.CommentCountsRequest.model_json_schema(
                    ref_template=ref_template
                ),
                "TaggedObject": dto.TaggedObject.model_json_schema(
                    ref_template=ref_template
                ),
                "MetadataResponseModel": dto.MetadataResponseModel.model_json_schema(
                    ref_template=ref_template
                ),
                "LightcurveResponseSingle": dto.LightcurveResponseSingle.model_json_schema(
                    ref_template=ref_template
                ),
                "ConeSearchResponseSingle": (
                    dto.ConeSearchResponseSingle.model_json_schema(
                        ref_template=ref_template
                    )
                ),
            },
        },
        "paths": {
            "/": {
                "get": {
                    "summary": "API health check",
                    "responses": {
                        "200": {
                            "description": "Service is running",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {"status": {"type": "string"}},
                                    }
                                }
                            },
                        }
                    },
                }
            },
            "/auth/{provider}/login": {
                "get": {
                    "summary": "Start OAuth login flow",
                    "parameters": [
                        {
                            "name": "provider",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "string",
                                "enum": ["orcid"],
                            },
                            "description": (
                                "Authentication provider. TarXiv currently supports "
                                "`orcid`; additional providers may be added later."
                            ),
                        }
                    ],
                    "responses": {
                        "302": {
                            "description": "Redirect to the provider authorization page"
                        },
                        "404": {"description": "Unknown provider"},
                        "500": {"description": "Provider configuration error"},
                    },
                }
            },
            "/auth/{provider}/callback": {
                "get": {
                    "summary": "Complete OAuth login flow",
                    "parameters": [
                        {
                            "name": "provider",
                            "in": "path",
                            "required": True,
                            "schema": {
                                "type": "string",
                                "enum": ["orcid"],
                            },
                            "description": (
                                "Authentication provider. TarXiv currently supports "
                                "`orcid`; additional providers may be added later."
                            ),
                        },
                        {
                            "name": "state",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "code",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        },
                    ],
                    "responses": {
                        "302": {
                            "description": "Redirect back to the dashboard with a token"
                        },
                        "400": {"description": "Invalid callback request"},
                        "404": {"description": "Unknown provider"},
                        "502": {"description": "Authentication failed"},
                    },
                }
            },
            "/user": {
                "get": {
                    "summary": "Get authenticated user profile",
                    "security": bearer_auth,
                    "responses": {
                        "200": {
                            "description": "Authenticated user profile",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                },
                "patch": {
                    "summary": "Update authenticated user profile",
                    "security": bearer_auth,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/UserProfileUpdate"
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Updated user profile",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/User"}
                                }
                            },
                        },
                        "400": {"description": "Validation error"},
                        "409": {"description": "Unique field conflict"},
                        "401": {"description": "Unauthorized"},
                    },
                },
            },
            "/users/search": {
                "get": {
                    "summary": "Search users by username, name, or email",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Matching users",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/UserSummary"
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/user/teams": {
                "get": {
                    "summary": "List authenticated user team memberships",
                    "security": bearer_auth,
                    "responses": {
                        "200": {
                            "description": "Team memberships",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/TeamMembership"
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/user/teams/{team_id}": {
                "delete": {
                    "summary": "Leave a team",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "team_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Left team successfully"},
                        "401": {"description": "Unauthorized"},
                        "404": {"description": "Membership not found"},
                    },
                }
            },
            "/teams": {
                "post": {
                    "summary": "Create a team",
                    "security": bearer_auth,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TeamCreate"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created team",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Team"}
                                }
                            },
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/teams/search": {
                "get": {
                    "summary": "Search teams by name or description",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "q",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Matching teams",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/TeamSummary"
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/teams/{team_id}": {
                "patch": {
                    "summary": "Update a team (owner only)",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "team_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TeamUpdate"}
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Updated team",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Team"}
                                }
                            },
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                        "403": {"description": "Not the team owner"},
                        "404": {"description": "Team not found"},
                        "409": {"description": "Team name already taken"},
                    },
                },
                "delete": {
                    "summary": "Delete a team (owner only)",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "team_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {"description": "Team deleted"},
                        "401": {"description": "Unauthorized"},
                        "403": {"description": "Not the team owner"},
                        "404": {"description": "Team not found"},
                    },
                },
            },
            "/teams/{team_id}/join": {
                "post": {
                    "summary": "Join a team directly",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "team_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "201": {
                            "description": "Joined team membership",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/TeamMembership"
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/teams/{team_id}/members": {
                "get": {
                    "summary": "List members of a team",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "team_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Team members",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/TeamMemberView"
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                        "403": {"description": "Not a member of the team"},
                    },
                },
                "post": {
                    "summary": "Add or update a team member",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "team_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/TeamMembershipCreate"
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Updated team membership",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/TeamMembership"
                                    }
                                }
                            },
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                    },
                },
            },
            "/tags": {
                "get": {
                    "summary": "List tags available to the authenticated user",
                    "security": bearer_auth,
                    "responses": {
                        "200": {
                            "description": "Tag list",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"$ref": "#/components/schemas/Tag"},
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                },
                "post": {
                    "summary": "Create a tag",
                    "security": bearer_auth,
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/TagCreate"}
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created tag",
                            "content": {
                                "application/json": {
                                    "schema": {"$ref": "#/components/schemas/Tag"}
                                }
                            },
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                    },
                },
            },
            "/tags/{tag_id}/objects": {
                "get": {
                    "summary": "List objects associated with a tag",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "tag_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                        },
                        {
                            "name": "offset",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Tagged objects",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/TaggedObject"
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/objects/{object_id}/tags": {
                "get": {
                    "summary": "List tag assignments visible on an object",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "object_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Object tag assignments",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/ObjectTagAssignmentView"
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                    },
                },
                "post": {
                    "summary": "Assign a tag to an object",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "object_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "$ref": "#/components/schemas/ObjectTagAssignmentCreate"
                                }
                            }
                        },
                    },
                    "responses": {
                        "201": {
                            "description": "Created object tag assignment",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/ObjectTagAssignmentView"
                                    }
                                }
                            },
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                    },
                },
            },
            "/objects/{object_id}/tags/{assignment_id}": {
                "delete": {
                    "summary": "Delete an object tag assignment",
                    "security": bearer_auth,
                    "parameters": [
                        {
                            "name": "object_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        },
                        {
                            "name": "assignment_id",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string", "format": "uuid"},
                        },
                    ],
                    "responses": {
                        "200": {
                            "description": "Deleted assignment",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "status": {"type": "string"},
                                            "object_id": {"type": "string"},
                                        },
                                    }
                                }
                            },
                        },
                        "401": {"description": "Unauthorized"},
                        "404": {"description": "Assignment not found"},
                    },
                }
            },
            "/objects/{source_id}/comments": {
                "get": {
                    "summary": "List comments visible on an object (flat, oldest first)",
                    "security": bearer_auth,
                    "parameters": [source_id_param],
                    "responses": {
                        "200": {
                            "description": "Comments; replies carry parent_id",
                            "content": json_body({
                                "type": "array",
                                "items": comment_ref,
                            }),
                        },
                        "401": {"description": "Unauthorized"},
                    },
                },
                "post": {
                    "summary": "Comment on an object, or reply to a comment",
                    "security": bearer_auth,
                    "parameters": [source_id_param],
                    "requestBody": {
                        "required": True,
                        "content": json_body({
                            "$ref": "#/components/schemas/CommentCreate"
                        }),
                    },
                    "responses": {
                        "201": {
                            "description": "Created comment",
                            "content": json_body(comment_ref),
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                        "403": {"description": "Not a member of the owner team"},
                        "404": {"description": "Parent comment not found"},
                    },
                },
            },
            "/comments/{comment_id}": {
                "patch": {
                    "summary": "Edit a comment (author only)",
                    "security": bearer_auth,
                    "parameters": [comment_id_param],
                    "requestBody": {
                        "required": True,
                        "content": json_body({
                            "$ref": "#/components/schemas/CommentUpdate"
                        }),
                    },
                    "responses": {
                        "200": {
                            "description": "Edited comment",
                            "content": json_body(comment_ref),
                        },
                        "400": {"description": "Validation error"},
                        "401": {"description": "Unauthorized"},
                        "403": {"description": "Not the author"},
                        "404": {"description": "Comment not found"},
                    },
                },
                "delete": {
                    "summary": "Delete a comment (author or team owner)",
                    "security": bearer_auth,
                    "parameters": [comment_id_param],
                    "responses": {
                        "200": {"description": "Deleted (or tombstoned)"},
                        "401": {"description": "Unauthorized"},
                        "403": {"description": "Not the author or team owner"},
                        "404": {"description": "Comment not found"},
                    },
                },
            },
            "/comments/counts": {
                "post": {
                    "summary": "Count visible comments per object",
                    "security": bearer_auth,
                    "requestBody": {
                        "required": True,
                        "content": json_body({
                            "$ref": "#/components/schemas/CommentCountsRequest"
                        }),
                    },
                    "responses": {
                        "200": {
                            "description": "Map of source_id to count; zeros omitted",
                            "content": json_body({
                                "type": "object",
                                "additionalProperties": {"type": "integer"},
                            }),
                        },
                        "401": {"description": "Unauthorized"},
                    },
                }
            },
            "/get_object_meta/{obj_name}": {
                "post": {
                    "summary": "Get object metadata",
                    "parameters": [
                        {
                            "name": "obj_name",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Object metadata",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "$ref": "#/components/schemas/MetadataResponseModel"
                                    }
                                }
                            },
                        },
                        "404": {"description": "Object not found"},
                    },
                }
            },
            "/get_object_lc/{obj_name}": {
                "post": {
                    "summary": "Get object lightcurve",
                    "parameters": [
                        {
                            "name": "obj_name",
                            "in": "path",
                            "required": True,
                            "schema": {"type": "string"},
                        }
                    ],
                    "responses": {
                        "200": {
                            "description": "Object lightcurve points",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/LightcurveResponseSingle"
                                        },
                                    }
                                }
                            },
                        },
                        "404": {"description": "Object not found"},
                    },
                }
            },
            "/tns_alerts": {
                "post": {
                    "summary": "List recent TNS alerts",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "n_rows": {"type": "integer"},
                                        "offset": {"type": "integer"},
                                    },
                                    "required": ["n_rows", "offset"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Alerts page",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "object"},
                                    }
                                }
                            },
                        },
                        "400": {"description": "Invalid paging parameters"},
                    },
                }
            },
            "/search_objects": {
                "post": {
                    "summary": "Search objects by metadata conditions",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {"search": {"type": "object"}},
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Matching object IDs",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {"type": "string"},
                                    }
                                }
                            },
                        },
                    },
                }
            },
            "/cone_search": {
                "post": {
                    "summary": "Cone search around sky coordinates",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "ra": {"type": "number"},
                                        "dec": {"type": "number"},
                                        "radius": {"type": "number"},
                                    },
                                    "required": ["ra", "dec", "radius"],
                                }
                            }
                        },
                    },
                    "responses": {
                        "200": {
                            "description": "Cone search results",
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "array",
                                        "items": {
                                            "$ref": "#/components/schemas/ConeSearchResponseSingle"
                                        },
                                    }
                                }
                            },
                        },
                    },
                }
            },
        },
    }
