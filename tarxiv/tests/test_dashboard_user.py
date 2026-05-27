import importlib
from types import SimpleNamespace
from unittest.mock import MagicMock

import dash
import dash_mantine_components as dmc
import pytest


@pytest.fixture
def user_module(monkeypatch):
    monkeypatch.setattr(dash, "register_page", lambda *args, **kwargs: None)
    import tarxiv.dashboard.pages.user as user

    return importlib.reload(user)


@pytest.fixture
def team_memberships():
    return [
        {
            "team_id": "team-owner",
            "team_name": "Owners",
            "team_description": "Owner-managed team",
            "role": "owner",
        },
        {
            "team_id": "team-member",
            "team_name": "Members",
            "team_description": "Regular membership",
            "role": "member",
        },
    ]


def flatten_children(component):
    if component is None:
        return []

    children = getattr(component, "children", None)
    if children is None:
        return [component]
    if isinstance(children, (list, tuple)):
        items = [component]
        for child in children:
            items.extend(flatten_children(child))
        return items
    return [component, *flatten_children(children)]


def find_components(component, component_type):
    return [
        item for item in flatten_children(component) if isinstance(item, component_type)
    ]


def banner_title(component):
    return getattr(component, "title", None)


def test_team_membership_block_shows_manage_members_for_owner(
    user_module, team_memberships
):
    block = user_module.team_membership_block(team_memberships)

    buttons = find_components(block, dmc.Button)
    labels = [button.children for button in buttons]

    assert "Manage Members" in labels
    assert labels.count("Manage Members") == 1


def test_team_membership_block_hides_manage_members_for_non_admin(user_module):
    block = user_module.team_membership_block([
        {
            "team_id": "team-member",
            "team_name": "Members",
            "team_description": "Regular membership",
            "role": "member",
        }
    ])

    buttons = find_components(block, dmc.Button)
    labels = [button.children for button in buttons]

    assert "Manage Members" not in labels


def test_team_membership_block_renders_member_manager_when_open(
    user_module, team_memberships
):
    block = user_module.team_membership_block(
        team_memberships,
        manager_open_states={"team-owner": True},
        member_search_results={
            "team-owner": [
                {
                    "id": "user-1",
                    "username": "ada",
                    "email": "ada@example.com",
                }
            ]
        },
        team_members={
            "team-owner": [{"user_id": "user-9", "username": "owner", "role": "owner"}]
        },
    )

    buttons = find_components(block, dmc.Button)
    labels = [button.children for button in buttons]
    texts = [getattr(t, "children", None) for t in find_components(block, dmc.Text)]

    assert "Hide Member Manager" in labels
    assert "Add to team" in labels
    # The current-members list is rendered with the owner's username.
    assert "Current members" in texts
    assert "owner" in texts


def test_team_member_list_block_empty_and_loading(user_module):
    loading = user_module.team_member_list_block(None)
    assert "Loading" in loading.children

    empty = user_module.team_member_list_block([])
    assert "no members" in empty.children.lower()


def test_generate_username_uses_name_and_is_unique_ish(user_module):
    name = user_module.generate_username("Ada", "Lovelace")
    assert name.startswith("adalovelace")
    assert name != "adalovelace"  # has a numeric suffix

    fallback = user_module.generate_username("", "")
    assert fallback.startswith("tarxiv")


def test_tag_block_shows_empty_state(user_module):
    block = user_module.tag_block([])
    texts = [getattr(t, "children", "") for t in find_components(block, dmc.Text)]
    assert any("don't have any tags" in str(text) for text in texts)


def test_tag_create_form_uses_color_input(user_module):
    form = user_module.render_tag_create_form([])
    color_inputs = find_components(form, dmc.ColorInput)
    assert len(color_inputs) == 1
    assert color_inputs[0].id == "new-tag-color"


def test_toggle_team_member_manager_updates_open_state(
    user_module, team_memberships, monkeypatch
):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"team_id": "team-owner"})
    )
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = [
        {"user_id": "user-1", "username": "ada", "role": "owner"}
    ]
    fetch_api_data = MagicMock(return_value=response)
    monkeypatch.setattr(user_module, "fetch_api_data", fetch_api_data)

    panel, open_state, members = user_module.toggle_team_member_manager(
        [1], team_memberships, {}, {}, {}
    )

    assert open_state == {"team-owner": True}
    assert members["team-owner"][0]["username"] == "ada"
    assert fetch_api_data.call_args.args[0] == "teams/team-owner/members"
    buttons = find_components(panel, dmc.Button)
    assert "Hide Member Manager" in [button.children for button in buttons]


def test_search_team_members_requires_query(user_module, monkeypatch):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"team_id": "team-owner"})
    )

    panel, results, banner = user_module.search_team_members(
        [1],
        [{"team_id": "team-owner"}],
        ["   "],
        [],
        {"team-owner": True},
        {},
        {},
    )

    assert panel is dash.no_update
    assert results is dash.no_update
    assert banner_title(banner) == "Enter a user search query."


def test_search_team_members_updates_results(
    user_module, team_memberships, monkeypatch
):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"team_id": "team-owner"})
    )
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    response = MagicMock()
    response.status_code = 200
    response.json.return_value = [
        {
            "id": "user-1",
            "username": "ada",
            "email": "ada@example.com",
            "forename": "Ada",
            "surname": "Lovelace",
        }
    ]
    fetch_api_data = MagicMock(return_value=response)
    monkeypatch.setattr(user_module, "fetch_api_data", fetch_api_data)

    panel, results, banner = user_module.search_team_members(
        [1],
        [{"team_id": "team-owner"}],
        ["ada lovelace"],
        team_memberships,
        {"team-owner": True},
        {},
        {},
    )

    assert results == {
        "team-owner": [
            {
                "id": "user-1",
                "username": "ada",
                "email": "ada@example.com",
                "forename": "Ada",
                "surname": "Lovelace",
            }
        ]
    }
    assert banner.__class__.__name__ == "Div"
    fetch_api_data.assert_called_once()
    assert fetch_api_data.call_args.args[0] == "users/search?q=ada%20lovelace"

    buttons = find_components(panel, dmc.Button)
    assert "Add to team" in [button.children for button in buttons]


def test_add_team_member_success(user_module, monkeypatch):
    monkeypatch.setattr(
        dash,
        "ctx",
        SimpleNamespace(triggered_id={"team_id": "team-owner", "user_id": "user-1"}),
    )
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    response = MagicMock()
    response.status_code = 201
    response.json.return_value = {"status": "ok"}
    post_api_data = MagicMock(return_value=response)
    monkeypatch.setattr(user_module, "post_api_data", post_api_data)

    members_response = MagicMock()
    members_response.status_code = 200
    members_response.json.return_value = [
        {"user_id": "user-1", "username": "ada", "role": "member"}
    ]
    fetch_api_data = MagicMock(return_value=members_response)
    monkeypatch.setattr(user_module, "fetch_api_data", fetch_api_data)

    search_results = {
        "team-owner": [{"id": "user-1", "username": "ada", "email": "ada@example.com"}]
    }
    banner, panel, members, updated_results = user_module.add_team_member(
        [1], [], {"team-owner": True}, search_results, {}
    )

    assert banner_title(banner) == "Ada added to the team."
    # Added user is dropped from the search results for that team.
    assert updated_results["team-owner"] == []
    # Member list refreshed from the backend.
    assert members["team-owner"][0]["username"] == "ada"
    post_api_data.assert_called_once_with(
        "teams/team-owner/members",
        "token",
        {"user_id": "user-1", "role": "member"},
        user_module.current_app.config["TXV_LOGGER"],
    )


def test_add_team_member_returns_error_banner(user_module, monkeypatch):
    monkeypatch.setattr(
        dash,
        "ctx",
        SimpleNamespace(triggered_id={"team_id": "team-owner", "user_id": "user-1"}),
    )
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    response = MagicMock()
    response.status_code = 400
    response.json.return_value = {"error": "Already on the team."}
    monkeypatch.setattr(user_module, "post_api_data", MagicMock(return_value=response))

    banner, panel, members, updated_results = user_module.add_team_member(
        [1], [], {}, {}, {}
    )

    assert banner_title(banner) == "Already on the team."
    assert panel is dash.no_update
