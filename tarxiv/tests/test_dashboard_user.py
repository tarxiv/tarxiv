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


def test_team_membership_block_manage_button_opens_modal(user_module, team_memberships):
    # The card no longer renders an inline manager; the "Manage Members" button
    # just opens the singleton modal (keyed by team so the open callback knows
    # which team to load).
    block = user_module.team_membership_block(team_memberships)

    manage_buttons = [
        button
        for button in find_components(block, dmc.Button)
        if isinstance(button.id, dict) and button.id.get("type") == "open-team-manage"
    ]
    assert len(manage_buttons) == 1
    assert manage_buttons[0].id["team_id"] == "team-owner"
    assert manage_buttons[0].children == "Manage Members"


def test_team_member_list_block_empty_and_loading(user_module):
    loading = user_module.team_member_list_block(None)
    assert "Loading" in loading.children

    empty = user_module.team_member_list_block([])
    assert "no members" in empty.children.lower()


def test_member_search_results_disable_existing_members(user_module):
    users = [
        {"id": "user-1", "username": "already", "email": "a@example.com"},
        {"id": "user-2", "username": "newbie", "email": "b@example.com"},
    ]
    block = user_module.team_member_search_results_block(users, member_ids=["user-1"])
    button_user_ids = {
        button.id["user_id"]
        for button in find_components(block, dmc.Button)
        if isinstance(button.id, dict)
        and button.id.get("type") == "add-team-member-button"
    }
    badge_texts = [badge.children for badge in find_components(block, dmc.Badge)]

    # Existing member gets a badge, not an add button; only the newbie is addable.
    assert "user-2" in button_user_ids
    assert "user-1" not in button_user_ids
    assert "Already a member" in badge_texts


def test_add_team_member_rejects_existing_member(user_module, monkeypatch):
    # The add button is keyed only by user_id; the team comes from the target store.
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"user_id": "user-1"})
    )
    post_api_data = MagicMock()
    monkeypatch.setattr(user_module, "post_api_data", post_api_data)

    target = {"team_id": "team-owner", "team_name": "Owners"}
    members = [{"user_id": "user-1", "username": "already"}]
    # Returns (members_store, list_children, results_store, results_children, message).
    result = user_module.add_team_member([1], target, [], members)

    assert banner_title(result[4]) == "That user is already a member of the team."
    # The client guard must short-circuit before calling the API.
    post_api_data.assert_not_called()
    assert result[0] is dash.no_update


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


def test_tag_block_groups_team_tags_by_team(user_module):
    tags = [
        {"id": "t1", "name": "alpha", "owner_type": "user", "owner_id": "u1"},
        {
            "id": "t2",
            "name": "beta",
            "owner_type": "team",
            "owner_id": "team-a",
            "owner_name": "Alpha Team",
        },
        {
            "id": "t3",
            "name": "gamma",
            "owner_type": "team",
            "owner_id": "team-b",
            "owner_name": "Beta Team",
        },
    ]
    block = user_module.tag_block(tags)
    section_titles = [
        getattr(t, "children", "")
        for t in find_components(block, dmc.Text)
        if getattr(t, "fw", None) == 600
    ]
    assert "Personal tags" in section_titles
    assert "Alpha Team (team)" in section_titles
    assert "Beta Team (team)" in section_titles


def test_tag_create_form_uses_color_input(user_module):
    form = user_module.render_tag_create_form([])
    color_inputs = find_components(form, dmc.ColorInput)
    assert len(color_inputs) == 1
    assert color_inputs[0].id == "new-tag-color"


def test_open_team_manage_modal_loads_members(
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

    # Returns: (target, team_name, members_store, list_children, results_store,
    #           results_children, search_input_value, message, opened).
    result = user_module.open_team_manage_modal([1], team_memberships)

    target, members_store, opened = result[0], result[2], result[8]
    assert target == {"team_id": "team-owner", "team_name": "Owners"}
    assert members_store[0]["username"] == "ada"
    assert opened is True
    # Member list is loaded from the backend on open.
    assert fetch_api_data.call_args.args[0] == "teams/team-owner/members"


def test_search_team_members_requires_query(user_module):
    # Blank query -> no API call, just a warning message in the modal.
    # Returns (results_store, results_children, message).
    results_store, results_children, message = user_module.search_team_members(
        1, "   ", []
    )

    assert results_store is dash.no_update
    assert results_children is dash.no_update
    assert banner_title(message) == "Enter a user search query."


def test_search_team_members_updates_results(user_module, monkeypatch):
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    found_users = [
        {
            "id": "user-1",
            "username": "ada",
            "email": "ada@example.com",
            "forename": "Ada",
            "surname": "Lovelace",
        }
    ]
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = found_users
    fetch_api_data = MagicMock(return_value=response)
    monkeypatch.setattr(user_module, "fetch_api_data", fetch_api_data)

    # members State is empty here, so the result is addable.
    results_store, results_children, message = user_module.search_team_members(
        1, "ada lovelace", []
    )

    assert results_store == found_users
    assert message.__class__.__name__ == "Div"
    fetch_api_data.assert_called_once()
    assert fetch_api_data.call_args.args[0] == "users/search?q=ada%20lovelace"

    buttons = find_components(results_children, dmc.Button)
    assert "Add to team" in [button.children for button in buttons]


def test_add_team_member_success(user_module, monkeypatch):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"user_id": "user-1"})
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

    target = {"team_id": "team-owner", "team_name": "Owners"}
    search_results = [{"id": "user-1", "username": "ada", "email": "ada@example.com"}]
    # Returns (members_store, list_children, results_store, results_children, message).
    members, _list, updated_results, _results_children, message = (
        user_module.add_team_member([1], target, search_results, [])
    )

    assert banner_title(message) == "Ada added to the team."
    # Added user is dropped from the search results.
    assert updated_results == []
    # Member list refreshed from the backend.
    assert members[0]["username"] == "ada"
    post_api_data.assert_called_once_with(
        "teams/team-owner/members",
        "token",
        {"user_id": "user-1", "role": "member"},
        user_module.current_app.config["TXV_LOGGER"],
    )


def test_add_team_member_returns_error_message(user_module, monkeypatch):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"user_id": "user-1"})
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

    target = {"team_id": "team-owner", "team_name": "Owners"}
    result = user_module.add_team_member([1], target, [], [])

    # On error, only the message slot is set; stores/children stay untouched.
    assert banner_title(result[4]) == "Already on the team."
    assert result[0] is dash.no_update


def test_team_card_shows_edit_delete_for_owner_only(user_module, team_memberships):
    block = user_module.team_membership_block(team_memberships)
    labels = [button.children for button in find_components(block, dmc.Button)]
    # Two owner-only actions appear once each (only team-owner is an owner).
    assert labels.count("Edit") == 1
    assert labels.count("Delete") == 1


def test_is_team_owner(user_module):
    assert user_module.is_team_owner({"role": "owner"}) is True
    assert user_module.is_team_owner({"role": "admin"}) is False
    assert user_module.is_team_owner({"role": "member"}) is False


def test_open_team_edit_modal_prefills(user_module, team_memberships, monkeypatch):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"team_id": "team-owner"})
    )

    name, description, target, message, opened = user_module.open_team_edit_modal(
        [1], team_memberships
    )

    assert name == "Owners"
    assert description == "Owner-managed team"
    assert target == {"team_id": "team-owner"}
    assert opened is True


def test_save_team_edit_success(user_module, monkeypatch):
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    patch_response = MagicMock()
    patch_response.status_code = 200
    patch_api_data = MagicMock(return_value=patch_response)
    monkeypatch.setattr(user_module, "patch_api_data", patch_api_data)

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = []
    monkeypatch.setattr(
        user_module, "fetch_api_data", MagicMock(return_value=list_response)
    )

    result = user_module.save_team_edit(
        1, "Renamed", "New description", {"team_id": "team-owner"}
    )
    banner = result[4]
    opened = result[6]

    assert banner_title(banner) == "Team updated."
    assert opened is False
    assert patch_api_data.call_args.args[0] == "teams/team-owner"


def test_save_team_edit_duplicate_keeps_modal_open(user_module, monkeypatch):
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    patch_response = MagicMock()
    patch_response.status_code = 409
    patch_response.json.return_value = {
        "error": "A team with that name already exists."
    }
    monkeypatch.setattr(
        user_module, "patch_api_data", MagicMock(return_value=patch_response)
    )

    result = user_module.save_team_edit(1, "Taken", "desc", {"team_id": "team-owner"})

    # Panels are not refreshed and the modal stays open (no_update) on error.
    assert result[0] is dash.no_update
    assert result[6] is dash.no_update
    assert banner_title(result[5]) == "A team with that name already exists."


def test_open_team_delete_modal_sets_target(user_module, team_memberships, monkeypatch):
    monkeypatch.setattr(
        dash, "ctx", SimpleNamespace(triggered_id={"team_id": "team-owner"})
    )

    target, body, message, opened = user_module.open_team_delete_modal(
        [1], team_memberships
    )

    assert target == {"team_id": "team-owner"}
    assert opened is True
    body_text = [getattr(t, "children", "") for t in find_components(body, dmc.Text)]
    assert any("Owners" in str(text) for text in body_text)


def test_confirm_team_delete_success(user_module, monkeypatch):
    monkeypatch.setattr(
        user_module, "current_app", SimpleNamespace(config={"TXV_LOGGER": MagicMock()})
    )
    monkeypatch.setattr(user_module, "request", object())
    monkeypatch.setattr(user_module, "get_jwt_from_request", lambda _request: "token")

    delete_response = MagicMock()
    delete_response.status_code = 200
    delete_api_data = MagicMock(return_value=delete_response)
    monkeypatch.setattr(user_module, "delete_api_data", delete_api_data)

    list_response = MagicMock()
    list_response.status_code = 200
    list_response.json.return_value = []
    monkeypatch.setattr(
        user_module, "fetch_api_data", MagicMock(return_value=list_response)
    )

    result = user_module.confirm_team_delete(1, {"team_id": "team-owner"})

    assert banner_title(result[4]) == "Team deleted."
    assert result[6] is False
    assert delete_api_data.call_args.args[0] == "teams/team-owner"
