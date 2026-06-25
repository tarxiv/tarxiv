"""API route tests. (Originally drafted with help from GPT-4o.)

These are *route-layer* tests, not database tests. The ``mock_api`` fixture
(in ``conftest.py``) builds a real ``API`` Flask app but replaces ``api.user_db``
and ``api.txv_db`` with ``MagicMock``s. So a test exercises everything the HTTP
layer does -- auth/token checking, JSON request parsing, DTO validation,
response serialization, and the mapping of data-layer exceptions to HTTP status
codes -- while the data layer itself is faked. The real ``user_db`` behaviour is
covered separately by ``test_database_user_integration.py``.

Because ``user_db`` is a mock, calling e.g. ``user_db.create_team(...)`` returns a
bare ``MagicMock`` by default, which the route could not serialize. Each test
therefore stubs the seam:

* ``user_db.<method>.return_value = <DTO>`` -- pretend the data layer succeeded
  and returned this object, so we can assert the route serializes it correctly
  and returns the right success status.
* ``user_db.<method>.side_effect = <SomeError>`` -- pretend the data layer
  raised, so we can assert the route translates that error into the right HTTP
  status (e.g. ``DuplicateValueError`` -> 409, ``AccessDeniedError`` -> 403).

``user_db.<method>.call_args`` / ``assert_called_once_with(...)`` are then used to
check the route forwarded the right (parsed) arguments to the data layer.
"""

import uuid

import pytest

import tarxiv.dto as tarxiv_dto
from tarxiv.auth.token_utils import sign_token


@pytest.fixture
def authenticated_user():
    # A representative persisted user; tests use its id to build a matching token.
    return tarxiv_dto.User.model_validate({
        "id": uuid.uuid4(),
        "username": "ada",
        "email": "ada@example.com",
        "forename": "Ada",
        "surname": "Lovelace",
    })


@pytest.fixture
def auth_token(authenticated_user):
    # A validly signed JWT for that user, so requests carrying it pass the API's
    # auth check (`_require_authenticated_user_id`) and reach the route body.
    return sign_token(
        str(authenticated_user.id),
        "orcid",
        authenticated_user.model_dump(mode="json", exclude_none=True),
    )


def test_get_object_meta_success(mock_api):
    # `app.test_client()` is a fake browser that drives the real Flask routes and
    # returns response objects (`.status_code`, `.json`). Here we stub the object
    # store to "find" a document and assert the route returns it verbatim.
    client = mock_api.app.test_client()
    mock_api.txv_db.get.return_value = {"foo": "bar"}
    token = sign_token("test-user", "orcid", {})

    response = client.post(
        "/get_object_meta/test_obj", json={}, headers={"Authorization": token}
    )
    assert response.status_code == 200
    assert response.json == {"foo": "bar"}


def test_get_object_meta_bad_token(mock_api):
    # No valid token -> the auth check rejects the request before any DB call.
    client = mock_api.app.test_client()
    response = client.post(
        "/get_object_meta/test_obj", json={}, headers={"Authorization": "WRONG"}
    )
    assert response.status_code == 401
    assert response.json["error"] == "Invalid or missing token."


def test_get_object_meta_missing_obj(mock_api):
    # Data layer returns None (no such object) -> route should map that to 404.
    client = mock_api.app.test_client()
    mock_api.txv_db.get.return_value = None
    token = sign_token("test-user", "orcid", {})
    response = client.post(
        "/get_object_meta/test_obj", json={}, headers={"Authorization": token}
    )
    assert response.status_code == 404
    assert response.json["error"] == "no such object"


def test_get_user_profile_success(mock_api, authenticated_user, auth_token):
    # Stub the lookup to return our user, then assert the route serializes it and
    # that it passed the token's `sub` (the user id) through to `get_user`.
    client = mock_api.app.test_client()
    mock_api.user_db.get_user.return_value = authenticated_user

    response = client.get("/user", headers={"Authorization": auth_token})

    assert response.status_code == 200
    assert response.json["id"] == str(authenticated_user.id)
    mock_api.user_db.get_user.assert_called_once_with(str(authenticated_user.id))


def test_patch_user_profile_success(mock_api, authenticated_user, auth_token):
    # Stub the update to echo back a modified user. Beyond the 200/serialization
    # check, we inspect `call_args` to confirm the route parsed the JSON body into
    # a `UserProfileUpdate` DTO (not a raw dict) before handing it to the data layer.
    client = mock_api.app.test_client()
    updated_user = authenticated_user.model_copy(update={"bio": "First programmer."})
    mock_api.user_db.update_user_profile.return_value = updated_user

    response = client.patch(
        "/user",
        json={"bio": "First programmer."},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json["bio"] == "First programmer."
    update_arg = mock_api.user_db.update_user_profile.call_args.args[1]
    assert isinstance(update_arg, tarxiv_dto.UserProfileUpdate)
    assert update_arg.bio == "First programmer."


def test_patch_user_profile_duplicate_username(mock_api, auth_token):
    # Simulate the data layer hitting the unique-username constraint; the route
    # must translate that domain error into a 409 Conflict.
    client = mock_api.app.test_client()
    from tarxiv.database_user import DuplicateValueError

    mock_api.user_db.update_user_profile.side_effect = DuplicateValueError(
        "Username is already taken."
    )

    response = client.patch(
        "/user",
        json={"username": "ada"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 409
    assert response.json["error"] == "Username is already taken."


def test_list_user_teams_success(mock_api, auth_token):
    # Stub a one-team membership list and assert it is serialized to JSON.
    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_api.user_db.list_user_teams.return_value = [
        tarxiv_dto.TeamMembership.model_validate({
            "team_id": team_id,
            "user_id": user_id,
            "role": "owner",
        })
    ]

    response = client.get("/user/teams", headers={"Authorization": auth_token})

    assert response.status_code == 200
    assert response.json[0]["team_id"] == str(team_id)


def test_create_team_success(mock_api, auth_token):
    # 201 + serialization, and confirm the JSON body was parsed into a TeamCreate DTO.
    client = mock_api.app.test_client()
    created_team = tarxiv_dto.Team.model_validate({
        "id": uuid.uuid4(),
        "name": "transients",
        "description": "A team",
    })
    mock_api.user_db.create_team.return_value = created_team

    response = client.post(
        "/teams",
        json={"name": "transients", "description": "A team"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 201
    assert response.json["name"] == "transients"
    create_arg = mock_api.user_db.create_team.call_args.args[1]
    assert isinstance(create_arg, tarxiv_dto.TeamCreate)


def test_search_users_success(mock_api, auth_token):
    # Assert the `q` query-string param is forwarded to `search_users` and results
    # are serialized.
    client = mock_api.app.test_client()
    mock_api.user_db.search_users.return_value = [
        tarxiv_dto.UserSummary.model_validate({
            "id": uuid.uuid4(),
            "username": "ada",
            "email": "ada@example.com",
        })
    ]

    response = client.get("/users/search?q=ada", headers={"Authorization": auth_token})

    assert response.status_code == 200
    assert response.json[0]["username"] == "ada"
    mock_api.user_db.search_users.assert_called_once_with("ada")


def test_search_teams_success(mock_api, auth_token):
    # Team search results (including the `is_member` flag) are serialized as JSON.
    client = mock_api.app.test_client()
    mock_api.user_db.search_teams.return_value = [
        tarxiv_dto.TeamSummary.model_validate({
            "id": uuid.uuid4(),
            "name": "team-alpha",
            "description": "Transient classifiers",
            "is_member": False,
        })
    ]

    response = client.get(
        "/teams/search?q=alpha", headers={"Authorization": auth_token}
    )

    assert response.status_code == 200
    assert response.json[0]["name"] == "team-alpha"


def test_add_team_member_success(mock_api, auth_token):
    # Happy path: data layer returns the new membership, route returns 201.
    client = mock_api.app.test_client()
    membership = tarxiv_dto.TeamMembership.model_validate({
        "team_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "role": "member",
    })
    mock_api.user_db.add_user_to_team.return_value = membership

    response = client.post(
        f"/teams/{membership.team_id}/members",
        json={"user_id": str(membership.user_id), "role": "member"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 201
    assert response.json["user_id"] == str(membership.user_id)


def test_add_team_member_duplicate_returns_conflict(mock_api, auth_token):
    # The data layer rejects re-adding an existing member (the demotion bug guard);
    # the route must surface that as 409, not a 500.
    from tarxiv.database_user import DuplicateValueError

    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.add_user_to_team.side_effect = DuplicateValueError(
        "This user is already a member of the team."
    )

    response = client.post(
        f"/teams/{team_id}/members",
        json={"user_id": str(uuid.uuid4()), "role": "member"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 409
    assert response.json["type"] == "validation"


def test_list_team_members_success(mock_api, auth_token):
    # Member list (with joined user fields) is serialized as JSON.
    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    user_id = uuid.uuid4()
    mock_api.user_db.list_team_members.return_value = [
        tarxiv_dto.TeamMemberView.model_validate({
            "team_id": team_id,
            "user_id": user_id,
            "role": "owner",
            "username": "ada",
            "email": "ada@example.com",
        })
    ]

    response = client.get(
        f"/teams/{team_id}/members", headers={"Authorization": auth_token}
    )

    assert response.status_code == 200
    assert response.json[0]["username"] == "ada"
    assert response.json[0]["role"] == "owner"


def test_list_team_members_forbidden_for_non_member(mock_api, auth_token):
    # Non-members are blocked in the data layer; the route maps that to 403.
    from tarxiv.database_user import AccessDeniedError

    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.list_team_members.side_effect = AccessDeniedError(
        "You are not a member of the requested team."
    )

    response = client.get(
        f"/teams/{team_id}/members", headers={"Authorization": auth_token}
    )

    assert response.status_code == 403
    assert response.json["type"] == "access"


def test_update_team_success(mock_api, auth_token):
    # 200 + serialization, and confirm the body parsed into a TeamUpdate DTO
    # (call_args.args[2] because update_team(team_id, acting_user_id, team_update)).
    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.update_team.return_value = tarxiv_dto.Team.model_validate({
        "id": team_id,
        "name": "renamed",
        "description": "new desc",
    })

    response = client.patch(
        f"/teams/{team_id}",
        json={"name": "renamed", "description": "new desc"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json["name"] == "renamed"
    update_arg = mock_api.user_db.update_team.call_args.args[2]
    assert isinstance(update_arg, tarxiv_dto.TeamUpdate)


def test_update_team_duplicate_name(mock_api, auth_token):
    # Renaming to an existing team name -> unique-constraint error -> 409.
    from tarxiv.database_user import DuplicateValueError

    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.update_team.side_effect = DuplicateValueError(
        "A team with that name already exists."
    )

    response = client.patch(
        f"/teams/{team_id}",
        json={"name": "taken"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 409
    assert response.json["type"] == "validation"


def test_update_team_forbidden_for_non_owner(mock_api, auth_token):
    # Editing is owner-only; a non-owner attempt raises AccessDeniedError -> 403.
    from tarxiv.database_user import AccessDeniedError

    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.update_team.side_effect = AccessDeniedError(
        "Only the team owner can perform this action."
    )

    response = client.patch(
        f"/teams/{team_id}",
        json={"name": "whatever"},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 403
    assert response.json["type"] == "access"


def test_delete_team_success(mock_api, auth_token):
    # delete_team returns True (a row was deleted) -> 200 with a "deleted" status.
    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.delete_team.return_value = True

    response = client.delete(f"/teams/{team_id}", headers={"Authorization": auth_token})

    assert response.status_code == 200
    assert response.json["status"] == "deleted"


def test_delete_team_not_found(mock_api, auth_token):
    # delete_team returns False (nothing matched) -> route maps that to 404.
    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.delete_team.return_value = False

    response = client.delete(f"/teams/{team_id}", headers={"Authorization": auth_token})

    assert response.status_code == 404


def test_delete_team_forbidden_for_non_owner(mock_api, auth_token):
    # Deleting is owner-only; a non-owner attempt raises AccessDeniedError -> 403.
    from tarxiv.database_user import AccessDeniedError

    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.delete_team.side_effect = AccessDeniedError(
        "Only the team owner can perform this action."
    )

    response = client.delete(f"/teams/{team_id}", headers={"Authorization": auth_token})

    assert response.status_code == 403
    assert response.json["type"] == "access"


def test_join_team_success(mock_api, auth_token):
    # Self-join returns the new membership -> 201.
    client = mock_api.app.test_client()
    membership = tarxiv_dto.TeamMembership.model_validate({
        "team_id": uuid.uuid4(),
        "user_id": uuid.uuid4(),
        "role": "member",
        "team_name": "team-alpha",
    })
    mock_api.user_db.join_team.return_value = membership

    response = client.post(
        f"/teams/{membership.team_id}/join",
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 201
    assert response.json["role"] == "member"


def test_leave_team_success(mock_api, auth_token):
    # leave_team returns True (membership removed) -> 200 with the team id echoed back.
    client = mock_api.app.test_client()
    team_id = uuid.uuid4()
    mock_api.user_db.leave_team.return_value = True

    response = client.delete(
        f"/user/teams/{team_id}",
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json["status"] == "left"
    assert response.json["team_id"] == str(team_id)


def test_list_tags_success(mock_api, auth_token):
    # The authenticated user's visible tags are serialized as JSON.
    client = mock_api.app.test_client()
    mock_api.user_db.list_tags.return_value = [
        tarxiv_dto.Tag.model_validate({
            "id": uuid.uuid4(),
            "name": "interesting",
            "owner_type": "user",
            "owner_id": uuid.uuid4(),
        })
    ]

    response = client.get("/tags", headers={"Authorization": auth_token})

    assert response.status_code == 200
    assert response.json[0]["name"] == "interesting"


def test_list_objects_for_tag_success(mock_api, auth_token):
    # Objects carrying a given tag are serialized; limit/offset come from the query string.
    client = mock_api.app.test_client()
    tag_id = uuid.uuid4()
    mock_api.user_db.list_objects_for_tag.return_value = [
        tarxiv_dto.TaggedObject(object_id="2024abc")
    ]

    response = client.get(
        f"/tags/{tag_id}/objects?limit=10&offset=0",
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json[0]["object_id"] == "2024abc"


def test_assign_object_tag_success(mock_api, auth_token):
    # Assigning a tag to an object returns the nested assignment view (201), so we
    # also check the embedded tag serializes.
    client = mock_api.app.test_client()
    tag = tarxiv_dto.Tag.model_validate({
        "id": uuid.uuid4(),
        "name": "interesting",
        "owner_type": "user",
        "owner_id": uuid.uuid4(),
    })
    assignment = tarxiv_dto.ObjectTagAssignmentView(
        id=uuid.uuid4(),
        object_id="2024abc",
        tag=tag,
        owner_type="user",
        owner_id=uuid.uuid4(),
    )
    mock_api.user_db.assign_tag_to_object.return_value = assignment

    response = client.post(
        "/objects/2024abc/tags",
        json={"tag_id": str(tag.id)},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 201
    assert response.json["object_id"] == "2024abc"
    assert response.json["tag"]["name"] == "interesting"


def test_list_object_tags_success(mock_api, auth_token):
    # The tags visible to this user on a given object are serialized.
    client = mock_api.app.test_client()
    tag = tarxiv_dto.Tag.model_validate({
        "id": uuid.uuid4(),
        "name": "team-tag",
        "owner_type": "team",
        "owner_id": uuid.uuid4(),
    })
    mock_api.user_db.list_object_tags_for_user.return_value = [
        tarxiv_dto.ObjectTagAssignmentView(
            id=uuid.uuid4(),
            object_id="2024abc",
            tag=tag,
            owner_type="team",
            owner_id=uuid.uuid4(),
        )
    ]

    response = client.get(
        "/objects/2024abc/tags", headers={"Authorization": auth_token}
    )

    assert response.status_code == 200
    assert response.json[0]["owner_type"] == "team"


def test_delete_object_tag_success(mock_api, auth_token):
    # Removing an assignment returns True -> 200 with a "deleted" status.
    client = mock_api.app.test_client()
    mock_api.user_db.remove_object_tag_assignment.return_value = True

    response = client.delete(
        f"/objects/2024abc/tags/{uuid.uuid4()}",
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json["status"] == "deleted"


def test_tns_alerts_success(mock_api, auth_token):
    # The alerts page reads obj_name/discovery_date/object_type/ra_hms/dec_dms/...
    # so the endpoint must emit exactly those keys. We stub the data layer to
    # return one such row and assert it is serialized back.
    client = mock_api.app.test_client()
    mock_api.txv_db.query.return_value = [
        {
            "discovery_date": "2018-05-05 04:10:48.996",
            "obj_name": "2018mqw",
            "object_type": "SN",
            "ra_hms": "12:38:29.211744",
            "dec_dms": "+39:00:11.0061",
            "redshift": None,
            "reporting_group": "ZTF",
            "discovery_source": "ZTF",
        }
    ]

    response = client.post(
        "/tns_alerts",
        json={"n_rows": 25, "offset": 0},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json[0]["obj_name"] == "2018mqw"
    assert response.json[0]["ra_hms"] == "12:38:29.211744"


def test_tns_alerts_query_reads_source_keyed_schema(mock_api, auth_token):
    """Alerts query must read TNS fields from the source-keyed schema.

    Regression: under the source-keyed schema the TNS fields live under
    ``data_sources.tns``, not ``meta.tns``. The old query selected ``meta.tns.*``
    (and ``meta.tns.object_id``), so every per-source field came back missing and
    the alerts table rendered empty. Guard the new paths/aliases.
    """
    client = mock_api.app.test_client()
    mock_api.txv_db.query.return_value = []

    response = client.post(
        "/tns_alerts",
        json={"n_rows": 25, "offset": 0},
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    statement = mock_api.txv_db.query.call_args.args[0]
    assert "meta.data_sources.tns.object_type" in statement
    assert "meta.source_id AS obj_name" in statement
    # The pre-fix, wrong path must be gone.
    assert "meta.tns." not in statement


def test_tns_alerts_requires_token(mock_api):
    client = mock_api.app.test_client()
    response = client.post(
        "/tns_alerts",
        json={"n_rows": 25, "offset": 0},
        headers={"Authorization": "WRONG"},
    )
    assert response.status_code == 401


def test_tns_alerts_rejects_non_integer_paging(mock_api, auth_token):
    client = mock_api.app.test_client()
    response = client.post(
        "/tns_alerts",
        json={"n_rows": "lots", "offset": 0},
        headers={"Authorization": auth_token},
    )
    assert response.status_code == 500
    assert response.json["type"] == "server"


def test_cone_search_route_returns_results(mock_api):
    # cone_search needs no token; it forwards ra/dec/radius to the data layer and
    # returns the rows verbatim. The rows are already obj_name/ra/dec/distance_deg.
    client = mock_api.app.test_client()
    mock_api.txv_db.cone_search.return_value = [
        {"obj_name": "2018mqw", "ra": 189.62, "dec": 39.0, "distance_deg": 0.0001}
    ]

    response = client.post(
        "/cone_search", json={"ra": 189.62, "dec": 39.0, "radius": 5.0}
    )

    assert response.status_code == 200
    assert response.json[0]["obj_name"] == "2018mqw"
    mock_api.txv_db.cone_search.assert_called_once_with(189.62, 39.0, 5.0)
