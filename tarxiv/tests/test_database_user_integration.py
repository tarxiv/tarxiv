from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

from tarxiv import dto
from tarxiv.database_user import AccessDeniedError, DuplicateValueError, UserDB


@pytest.mark.slow
def test_get_or_create_user_from_identity_round_trip(monkeypatch):
    pytest.importorskip("testcontainers")

    workspace_root = Path(__file__).resolve().parents[2]
    config_dir = workspace_root / "aux"

    with PostgresContainer("postgres:15") as postgres:
        sync_url = postgres.get_connection_url()
        sqlalchemy_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        monkeypatch.setenv("TARXIV_POSTGRES_URL", sqlalchemy_url)
        monkeypatch.setenv("TARXIV_CONFIG_DIR", str(config_dir))

        from alembic.config import Config
        from alembic import command

        alembic_cfg = Config(str(workspace_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        user_db = UserDB("integration", 0, debug=False)
        profile = dto.ProviderProfile(
            provider_user_id="0000-0002-1825-0097",
            username="Ada Lovelace",
            email="ada@example.com",
            forename="Ada",
            surname="Lovelace",
        )

        created = user_db.get_or_create_user_from_identity(
            "orcid", profile, {"orcid": "0000-0002-1825-0097"}
        )
        repeated = user_db.get_or_create_user_from_identity(
            "orcid", profile, {"orcid": "0000-0002-1825-0097"}
        )
        fetched = user_db.get_user_by_external_identity("orcid", "0000-0002-1825-0097")

        assert created.id == repeated.id
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.email == "ada@example.com"
        assert fetched.forename == "Ada"


@pytest.mark.slow
def test_tag_round_trip_and_visibility(monkeypatch):
    pytest.importorskip("testcontainers")

    workspace_root = Path(__file__).resolve().parents[2]
    config_dir = workspace_root / "aux"

    with PostgresContainer("postgres:15") as postgres:
        sync_url = postgres.get_connection_url()
        sqlalchemy_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        monkeypatch.setenv("TARXIV_POSTGRES_URL", sqlalchemy_url)
        monkeypatch.setenv("TARXIV_CONFIG_DIR", str(config_dir))

        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(workspace_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        user_db = UserDB("integration", 0, debug=False)

        owner = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0001-0000-0001",
                username="owner",
                email="owner@example.com",
            ),
            {"orcid": "0000-0001-0000-0001"},
        )
        teammate = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0001-0000-0002",
                username="teammate",
                email="teammate@example.com",
            ),
            {"orcid": "0000-0001-0000-0002"},
        )
        outsider = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0001-0000-0003",
                username="outsider",
                email="outsider@example.com",
            ),
            {"orcid": "0000-0001-0000-0003"},
        )

        team = user_db.create_team(
            owner.id,
            dto.TeamCreate(name="team-alpha", description="Shared classification team"),
        )
        membership = user_db.add_user_to_team(
            team.id,
            owner.id,
            dto.TeamMembershipCreate(user_id=teammate.id, role="member"),
        )

        assert membership.team_id == team.id
        assert membership.user_id == teammate.id

        personal_tag = user_db.create_tag(
            owner.id,
            dto.TagCreate(
                name="interesting",
                description="Owner-only tag",
                color="#7c3aed",
            ),
        )
        team_tag = user_db.create_tag(
            owner.id,
            dto.TagCreate(
                name="follow-up",
                description="Team tag",
                owner_team_id=team.id,
            ),
        )

        owner_tags = user_db.list_tags(owner.id)
        teammate_tags = user_db.list_tags(teammate.id)
        outsider_tags = user_db.list_tags(outsider.id)

        assert {tag.name for tag in owner_tags} == {"interesting", "follow-up"}
        assert {tag.name for tag in teammate_tags} == {"follow-up"}
        assert outsider_tags == []

        # Tags carry their owner's display name for grouping in the UI.
        owner_tags_by_name = {tag.name: tag for tag in owner_tags}
        assert owner_tags_by_name["follow-up"].owner_type == "team"
        assert owner_tags_by_name["follow-up"].owner_name == "team-alpha"
        assert owner_tags_by_name["interesting"].owner_type == "user"
        assert owner_tags_by_name["interesting"].owner_name == "owner"

        personal_assignment = user_db.assign_tag_to_object(
            "2024abc",
            owner.id,
            dto.ObjectTagAssignmentCreate(tag_id=personal_tag.id),
        )
        team_assignment = user_db.assign_tag_to_object(
            "2024abc",
            owner.id,
            dto.ObjectTagAssignmentCreate(tag_id=team_tag.id),
        )

        assert personal_assignment.object_id == "2024abc"
        assert team_assignment.object_id == "2024abc"

        owner_object_tags = user_db.list_object_tags_for_user("2024abc", owner.id)
        teammate_object_tags = user_db.list_object_tags_for_user("2024abc", teammate.id)
        outsider_object_tags = user_db.list_object_tags_for_user("2024abc", outsider.id)

        assert {item.tag.name for item in owner_object_tags} == {
            "interesting",
            "follow-up",
        }
        assert {item.tag.name for item in teammate_object_tags} == {"follow-up"}
        assert outsider_object_tags == []

        filtered_ids = user_db.list_tagged_object_ids_for_user(
            owner.id, [personal_tag.id]
        )
        teammate_filtered_ids = user_db.list_tagged_object_ids_for_user(
            teammate.id, [team_tag.id]
        )
        outsider_filtered_ids = user_db.list_tagged_object_ids_for_user(
            outsider.id, [team_tag.id]
        )

        assert filtered_ids == ["2024abc"]
        assert teammate_filtered_ids == ["2024abc"]
        assert outsider_filtered_ids == []


@pytest.mark.slow
def test_team_search_join_leave_and_username_uniqueness(monkeypatch):
    pytest.importorskip("testcontainers")

    workspace_root = Path(__file__).resolve().parents[2]
    config_dir = workspace_root / "aux"

    with PostgresContainer("postgres:15") as postgres:
        sync_url = postgres.get_connection_url()
        sqlalchemy_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        monkeypatch.setenv("TARXIV_POSTGRES_URL", sqlalchemy_url)
        monkeypatch.setenv("TARXIV_CONFIG_DIR", str(config_dir))

        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(workspace_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        user_db = UserDB("integration", 0, debug=False)

        owner = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0001-1000-0001",
                username="owner_a",
                email="owner_a@example.com",
            ),
            {"orcid": "0000-0001-1000-0001"},
        )
        joiner = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0001-1000-0002",
                username="joiner_b",
                email="joiner_b@example.com",
                forename="Joiner",
                surname="Example",
            ),
            {"orcid": "0000-0001-1000-0002"},
        )

        user_search_results = user_db.search_users("joiner")
        assert [user.username for user in user_search_results] == ["joiner_b"]

        created_team = user_db.create_team(
            owner.id,
            dto.TeamCreate(name="spectroscopy-team", description="Follow-up work"),
        )

        team_search_results = user_db.search_teams(joiner.id, "spectro")
        assert [team.name for team in team_search_results] == ["spectroscopy-team"]
        assert team_search_results[0].is_member is False

        joined_membership = user_db.join_team(created_team.id, joiner.id)
        assert joined_membership.team_id == created_team.id
        assert joined_membership.user_id == joiner.id

        team_search_results_after_join = user_db.search_teams(joiner.id, "spectro")
        assert team_search_results_after_join[0].is_member is True

        leave_result = user_db.leave_team(created_team.id, joiner.id)
        assert leave_result is True

        team_search_results_after_leave = user_db.search_teams(joiner.id, "spectro")
        assert team_search_results_after_leave[0].is_member is False

        with pytest.raises(DuplicateValueError, match="Username is already taken"):
            user_db.update_user_profile(
                joiner.id,
                dto.UserProfileUpdate(username="owner_a"),
            )


@pytest.mark.slow
def test_list_team_members_visibility(monkeypatch):
    pytest.importorskip("testcontainers")

    workspace_root = Path(__file__).resolve().parents[2]
    config_dir = workspace_root / "aux"

    with PostgresContainer("postgres:15") as postgres:
        sync_url = postgres.get_connection_url()
        sqlalchemy_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        monkeypatch.setenv("TARXIV_POSTGRES_URL", sqlalchemy_url)
        monkeypatch.setenv("TARXIV_CONFIG_DIR", str(config_dir))

        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(workspace_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        user_db = UserDB("integration", 0, debug=False)

        owner = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0002-0000-0001",
                username="owner",
                email="owner@example.com",
                forename="Olive",
                surname="Owner",
            ),
            {"orcid": "0000-0002-0000-0001"},
        )
        teammate = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0002-0000-0002",
                username="teammate",
                email="teammate@example.com",
            ),
            {"orcid": "0000-0002-0000-0002"},
        )
        outsider = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0002-0000-0003",
                username="outsider",
                email="outsider@example.com",
            ),
            {"orcid": "0000-0002-0000-0003"},
        )

        team = user_db.create_team(
            owner.id,
            dto.TeamCreate(name="team-members", description="Membership listing team"),
        )
        user_db.add_user_to_team(
            team.id,
            owner.id,
            dto.TeamMembershipCreate(user_id=teammate.id, role="member"),
        )

        # A member can list the team's members (owner + teammate).
        members = user_db.list_team_members(team.id, owner.id)
        members_by_user = {str(member.user_id): member for member in members}
        assert str(owner.id) in members_by_user
        assert str(teammate.id) in members_by_user
        assert members_by_user[str(owner.id)].role == "owner"
        assert members_by_user[str(owner.id)].username == "owner"

        # The teammate can also list members.
        teammate_view = user_db.list_team_members(team.id, teammate.id)
        assert len(teammate_view) == 2

        # An outsider is denied.
        with pytest.raises(AccessDeniedError):
            user_db.list_team_members(team.id, outsider.id)


@pytest.mark.slow
def test_update_and_delete_team(monkeypatch):
    pytest.importorskip("testcontainers")

    workspace_root = Path(__file__).resolve().parents[2]
    config_dir = workspace_root / "aux"

    with PostgresContainer("postgres:15") as postgres:
        sync_url = postgres.get_connection_url()
        sqlalchemy_url = sync_url.replace("postgresql://", "postgresql+psycopg2://", 1)

        monkeypatch.setenv("TARXIV_POSTGRES_URL", sqlalchemy_url)
        monkeypatch.setenv("TARXIV_CONFIG_DIR", str(config_dir))

        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(workspace_root / "alembic.ini"))
        command.upgrade(alembic_cfg, "head")

        user_db = UserDB("integration", 0, debug=False)

        owner = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0003-0000-0001",
                username="team-owner",
                email="owner@example.com",
            ),
            {"orcid": "0000-0003-0000-0001"},
        )
        member = user_db.get_or_create_user_from_identity(
            "orcid",
            dto.ProviderProfile(
                provider_user_id="0000-0003-0000-0002",
                username="team-member",
                email="member@example.com",
            ),
            {"orcid": "0000-0003-0000-0002"},
        )

        team = user_db.create_team(
            owner.id, dto.TeamCreate(name="editable-team", description="Original")
        )
        user_db.add_user_to_team(
            team.id,
            owner.id,
            dto.TeamMembershipCreate(user_id=member.id, role="member"),
        )

        # Re-adding an existing member is rejected.
        with pytest.raises(DuplicateValueError):
            user_db.add_user_to_team(
                team.id,
                owner.id,
                dto.TeamMembershipCreate(user_id=member.id, role="member"),
            )
        # The owner cannot be demoted via a re-add either.
        with pytest.raises(DuplicateValueError):
            user_db.add_user_to_team(
                team.id,
                owner.id,
                dto.TeamMembershipCreate(user_id=owner.id, role="member"),
            )

        # Create a second team to collide with when testing rename uniqueness.
        user_db.create_team(
            owner.id, dto.TeamCreate(name="taken-name", description="Other")
        )

        # Owner can update name + description.
        updated = user_db.update_team(
            team.id,
            owner.id,
            dto.TeamUpdate(name="renamed-team", description="Updated"),
        )
        assert updated.name == "renamed-team"
        assert updated.description == "Updated"

        # Non-owner members cannot update.
        with pytest.raises(AccessDeniedError):
            user_db.update_team(team.id, member.id, dto.TeamUpdate(description="nope"))

        # Renaming to an existing team name is rejected.
        with pytest.raises(DuplicateValueError):
            user_db.update_team(team.id, owner.id, dto.TeamUpdate(name="taken-name"))

        # A team tag plus an assignment, to verify cascade on delete.
        team_tag = user_db.create_tag(
            owner.id,
            dto.TagCreate(name="team-tag", owner_team_id=team.id),
        )
        user_db.assign_tag_to_object(
            "2024xyz",
            owner.id,
            dto.ObjectTagAssignmentCreate(tag_id=team_tag.id),
        )
        assert any(tag.name == "team-tag" for tag in user_db.list_tags(owner.id))

        # Non-owner cannot delete.
        with pytest.raises(AccessDeniedError):
            user_db.delete_team(team.id, member.id)

        # Owner deletes the team; its tags (and assignments) cascade away.
        assert user_db.delete_team(team.id, owner.id) is True
        remaining_tag_names = {tag.name for tag in user_db.list_tags(owner.id)}
        assert "team-tag" not in remaining_tag_names
        assert user_db.list_objects_for_tag(team_tag.id, owner.id, 50, 0) == []


@pytest.mark.slow
def test_comment_rules(monkeypatch):
    pytest.importorskip("testcontainers")

    workspace_root = Path(__file__).resolve().parents[2]

    with PostgresContainer("postgres:15") as postgres:
        sqlalchemy_url = postgres.get_connection_url().replace(
            "postgresql://", "postgresql+psycopg2://", 1
        )
        monkeypatch.setenv("TARXIV_POSTGRES_URL", sqlalchemy_url)
        monkeypatch.setenv("TARXIV_CONFIG_DIR", str(workspace_root / "aux"))

        from alembic import command
        from alembic.config import Config

        command.upgrade(Config(str(workspace_root / "alembic.ini")), "head")
        user_db = UserDB("integration", 0, debug=False)

        def make_user(n, name):
            orcid = f"0000-0002-0000-000{n}"
            return user_db.get_or_create_user_from_identity(
                "orcid",
                dto.ProviderProfile(provider_user_id=orcid, username=name),
                {"orcid": orcid},
            )

        owner, alice, bob, outsider = (
            make_user(i, name)
            for i, name in enumerate(["owner", "alice", "bob", "outsider"], 1)
        )
        team = user_db.create_team(owner.id, dto.TeamCreate(name="hubble"))
        for member in (alice, bob):
            user_db.add_user_to_team(
                team.id, owner.id, dto.TeamMembershipCreate(user_id=member.id)
            )

        def post(user, body, **kwargs):
            return user_db.create_comment(
                "2024abc", user.id, dto.CommentCreate(body=body, **kwargs)
            )

        # Visibility: team comment seen by members only; personal note by its owner only.
        root = post(alice, "Team comment", owner_team_id=team.id)
        note = post(alice, "My note")
        assert root.owner_type == "team" and root.author_name == "alice"
        assert {c.id for c in user_db.list_comments("2024abc", bob.id)} == {root.id}
        assert user_db.list_comments("2024abc", outsider.id) == []
        assert {c.id for c in user_db.list_comments("2024abc", alice.id)} == {
            root.id,
            note.id,
        }
        with pytest.raises(AccessDeniedError):
            post(outsider, "x", owner_team_id=team.id)

        # Replies: inherit the parent's owner, one level only, invisible parent is 404.
        reply = post(bob, "Agreed", parent_id=root.id)
        assert reply.owner_type == "team" and reply.owner_id == team.id
        with pytest.raises(ValueError):
            post(alice, "nested", parent_id=reply.id)
        with pytest.raises(ValueError):
            post(alice, "mismatch", parent_id=root.id, owner_team_id=owner.id)
        with pytest.raises(LookupError):
            post(outsider, "sneaky", parent_id=root.id)

        # Counts: visible and non-deleted only.
        assert user_db.count_comments(["2024abc", "2024zzz"], alice.id) == {
            "2024abc": 3
        }
        assert user_db.count_comments(["2024abc"], outsider.id) == {}

        # Editing: author only.
        edited = user_db.update_comment(root.id, alice.id, dto.CommentUpdate(body="v2"))
        assert edited.body == "v2"
        with pytest.raises(AccessDeniedError):
            user_db.update_comment(root.id, bob.id, dto.CommentUpdate(body="v3"))
        assert (
            user_db.update_comment(root.id, outsider.id, dto.CommentUpdate(body="x"))
            is None
        )

        # Deleting: a plain member cannot delete someone else's comment.
        with pytest.raises(AccessDeniedError):
            user_db.delete_comment(root.id, bob.id)

        # A root with replies becomes a tombstone; replies still allowed under it.
        assert user_db.delete_comment(root.id, alice.id)
        tombstone = next(
            c for c in user_db.list_comments("2024abc", bob.id) if c.id == root.id
        )
        assert tombstone.deleted and tombstone.body == ""
        assert user_db.count_comments(["2024abc"], bob.id) == {"2024abc": 1}
        late_reply = post(bob, "Still here", parent_id=root.id)

        # The team owner can moderate; deleting the last reply removes the tombstone.
        assert user_db.delete_comment(reply.id, owner.id)
        assert user_db.delete_comment(late_reply.id, bob.id)
        assert user_db.list_comments("2024abc", bob.id) == []

        # Leaving the team removes access, but the comment stays for the team.
        kept = post(bob, "Bye", owner_team_id=team.id)
        user_db.leave_team(team.id, bob.id)
        assert (
            user_db.update_comment(kept.id, bob.id, dto.CommentUpdate(body="x")) is None
        )
        assert [c.id for c in user_db.list_comments("2024abc", alice.id)] == [
            note.id,
            kept.id,
        ]
