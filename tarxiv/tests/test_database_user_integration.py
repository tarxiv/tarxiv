import os
from pathlib import Path

import pytest
from testcontainers.postgres import PostgresContainer

from tarxiv import dto
from tarxiv.database_user import UserDB


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
        fetched = user_db.get_user_by_external_identity(
            "orcid", "0000-0002-1825-0097"
        )

        assert created.id == repeated.id
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.email == "ada@example.com"
        assert fetched.forename == "Ada"
