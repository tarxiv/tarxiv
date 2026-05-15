"""HFS - created with help from GPT 4o"""

import uuid

import pytest
from unittest.mock import MagicMock

import tarxiv.dto as tarxiv_dto
from tarxiv.api import API
from tarxiv.auth.token_utils import sign_token
import os

_TEST_JWT_SECRET = "test-jwt-secret-for-api-tests-32b"


class MockTarxivModule:
    """Mock version of TarxivModule for testing purposes."""

    def __init__(self, *args, **kwargs):
        self.module = "mock tarxiv module"
        self.config_dir = os.environ.get(
            "TARXIV_CONFIG_DIR", os.path.join(os.path.dirname(__file__), "../aux")
        )
        self.config_file = os.path.join(self.config_dir, "config.yml")
        self.config = {"log_dir": None, "api_port": 5000}
        self.logger = MagicMock()
        self.debug = False


@pytest.fixture
def mock_api(monkeypatch, tmp_path):
    monkeypatch.setenv("TARXIV_JWT_SECRET", _TEST_JWT_SECRET)
    # HFS - 2025-05-28: Fake the TarXivDB object instantiation which is needed for the API object
    # we also have to fake TarxivModule, which is parent to API and TarxivDB
    monkeypatch.setattr(
        "tarxiv.database.TarxivDB.__init__", lambda self, *args, **kwargs: None
    )
    monkeypatch.setattr(
        "tarxiv.database_user.UserDB.__init__", lambda self, *args, **kwargs: None
    )

    # JL - 2025-06-05: Mock the TarxivModule to avoid file I/O and logging setup
    # during tests. Previous incarnation of this mock class was too tightly
    # coupled to the original TarxivModule, this should be more generic.
    monkeypatch.setattr("tarxiv.utils.TarxivModule.__init__", MockTarxivModule.__init__)

    # HFS - 2025-05-28: MagicMock is a flexible fake object that can act like functions, methods,
    # or even entire objects. It records how it's used so you can assert things later
    # (e.g. mock.call_args)
    # HFS - 2025-05-28: Note we never open or do anything with the config file so we can give a path
    # to fill in the parameter so instanciation works and that's it.

    api = API("mock", str(tmp_path))
    # HFS - 2025-05-28: We now  replace the instance with a MagicMock so we don’t have to define every method
    # ourselves (e.g. get).
    api.txv_db = MagicMock()
    api.user_db = MagicMock()
    return api


@pytest.fixture
def authenticated_user():
    return tarxiv_dto.User.model_validate({
        "id": uuid.uuid4(),
        "username": "ada",
        "email": "ada@example.com",
        "forename": "Ada",
        "surname": "Lovelace",
    })


@pytest.fixture
def auth_token(authenticated_user):
    return sign_token(
        str(authenticated_user.id),
        "orcid",
        authenticated_user.model_dump(mode="json", exclude_none=True),
    )


def test_get_object_meta_success(mock_api):
    # HFS - 2025-05-28: The .app stuff comes from Flask and it returns a client object
    # that can do .post .get .put etc.. and send requests through
    # Flask routes that Kyle defined in the API class
    # the client objetc can also return response objects like
    # .status_code, .json
    # TL;DR: .app.test_client() is a fake browaser hitting
    # the self.app.route functions in API object
    client = mock_api.app.test_client()
    mock_api.txv_db.get.return_value = {"foo": "bar"}
    token = sign_token("test-user", "orcid", {})

    response = client.post(
        "/get_object_meta/test_obj", json={}, headers={"Authorization": token}
    )
    assert response.status_code == 200
    assert response.json == {"foo": "bar"}


def test_get_object_meta_bad_token(mock_api):
    client = mock_api.app.test_client()
    response = client.post(
        "/get_object_meta/test_obj", json={}, headers={"Authorization": "WRONG"}
    )
    assert response.status_code == 401
    assert response.json["error"] == "Invalid or missing token."


def test_get_object_meta_missing_obj(mock_api):
    client = mock_api.app.test_client()
    mock_api.txv_db.get.return_value = None
    token = sign_token("test-user", "orcid", {})
    response = client.post(
        "/get_object_meta/test_obj", json={}, headers={"Authorization": token}
    )
    assert response.status_code == 404
    assert response.json["error"] == "no such object"


def test_openapi_json_served(mock_api):
    client = mock_api.app.test_client()

    response = client.get("/openapi.json")

    assert response.status_code == 200
    # This is we get back valid semver
    assert len(response.json["openapi"].split(".")) == 3
    assert response.json["info"]["title"] == "TarXiv API"
    assert "/tags" in response.json["paths"]
    assert "/users/search" in response.json["paths"]
    assert "/teams/search" in response.json["paths"]
    assert "/teams/{team_id}/join" in response.json["paths"]
    assert "/user/teams/{team_id}" in response.json["paths"]
    assert "/tags/{tag_id}/objects" in response.json["paths"]
    assert "/auth/{provider}/login" in response.json["paths"]
    assert "/auth/{provider}/callback" in response.json["paths"]
    assert "/docs" not in response.json["paths"]


def test_swagger_docs_page_served(mock_api):
    client = mock_api.app.test_client()

    response = client.get("/docs")

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert "SwaggerUIBundle" in response.text
    assert "/openapi.json" in response.text


def test_get_user_profile_success(mock_api, authenticated_user, auth_token):
    client = mock_api.app.test_client()
    mock_api.user_db.get_user.return_value = authenticated_user

    response = client.get("/user", headers={"Authorization": auth_token})

    assert response.status_code == 200
    assert response.json["id"] == str(authenticated_user.id)
    mock_api.user_db.get_user.assert_called_once_with(str(authenticated_user.id))


def test_patch_user_profile_success(mock_api, authenticated_user, auth_token):
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


def test_join_team_success(mock_api, auth_token):
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
    client = mock_api.app.test_client()
    mock_api.user_db.remove_object_tag_assignment.return_value = True

    response = client.delete(
        f"/objects/2024abc/tags/{uuid.uuid4()}",
        headers={"Authorization": auth_token},
    )

    assert response.status_code == 200
    assert response.json["status"] == "deleted"
