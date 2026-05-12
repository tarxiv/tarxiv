import os

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from . import dto, orm
from .utils import TarxivModule


class DataLayerError(Exception):
    """Base exception for database errors."""


class UserRetrievalError(DataLayerError):
    """Raised when there is a system failure retrieving a user."""


class UserDB(TarxivModule):
    """Relational access layer for TarXiv users and external identities."""

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="UserDB",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        connection_url = os.environ.get("TARXIV_POSTGRES_URL")
        if not connection_url:
            raise RuntimeError("Missing TARXIV_POSTGRES_URL environment variable")

        self.engine = create_engine(connection_url)
        self.session_factory = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

        self._test_db_connection()

    def _test_db_connection(self):
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1"))
                if result.scalar() != 1:
                    raise RuntimeError("Unexpected database healthcheck response")
        except Exception as exc:
            self.logger.error(f"Database connection test failed: {exc}")
            raise RuntimeError(
                "Database connection failed. Check logs for details."
            ) from exc

    def get_session(self) -> Session:
        return self.session_factory()

    def get_user_by_external_identity(
        self, provider: str, provider_user_id: str
    ) -> dto.User | None:
        with self.get_session() as session:
            try:
                identity = (
                    session.query(orm.ExternalIdentity)
                    .filter(orm.ExternalIdentity.provider == provider)
                    .filter(orm.ExternalIdentity.provider_user_id == provider_user_id)
                    .first()
                )
                if identity is None:
                    return None
                return dto.User.model_validate(identity.user)
            except SQLAlchemyError as exc:
                self.logger.error(
                    {
                        "status": (
                            "Database error while querying external identity "
                            f"{provider}:{provider_user_id}: {exc}"
                        )
                    },
                    exc_info=True,
                )
                raise UserRetrievalError(
                    "A system error occurred while accessing the user database."
                ) from exc

    def get_or_create_user_from_identity(
        self,
        provider: str,
        profile: dto.ProviderProfile,
        provider_profile_json: dict | None = None,
    ) -> dto.User:
        session = self.get_session()
        try:
            identity = (
                session.query(orm.ExternalIdentity)
                .filter(orm.ExternalIdentity.provider == provider)
                .filter(
                    orm.ExternalIdentity.provider_user_id == profile.provider_user_id
                )
                .first()
            )
            if identity is not None:
                user = identity.user
                self._fill_empty_user_fields_from_profile(user, profile)
                identity.provider_username = profile.username
                identity.provider_email = profile.email
                identity.provider_profile_json = provider_profile_json
            else:
                user = orm.User()
                self._fill_empty_user_fields_from_profile(user, profile, overwrite=True)
                session.add(user)
                session.flush()

                identity = orm.ExternalIdentity(
                    user_id=user.id,
                    provider=provider,
                    provider_user_id=profile.provider_user_id,
                    provider_username=profile.username,
                    provider_email=profile.email,
                    provider_profile_json=provider_profile_json,
                )
                session.add(identity)

            session.commit()
            session.refresh(user)
            return dto.User.model_validate(user)
        except SQLAlchemyError as exc:
            session.rollback()
            self.logger.error(
                {
                    "status": (
                        "Database error while syncing external identity "
                        f"{provider}:{profile.provider_user_id}: {exc}"
                    )
                },
                exc_info=True,
            )
            raise DataLayerError(
                "A system error occurred while syncing the user account."
            ) from exc
        finally:
            session.close()

    @staticmethod
    def _fill_empty_user_fields_from_profile(
        user: orm.User, profile: dto.ProviderProfile, overwrite: bool = False
    ) -> None:
        field_names = (
            "username",
            "nickname",
            "email",
            "institution",
            "forename",
            "surname",
            "picture_url",
            "bio",
        )
        for field_name in field_names:
            incoming_value = getattr(profile, field_name)
            if incoming_value is None:
                continue
            if overwrite or getattr(user, field_name) in (None, ""):
                setattr(user, field_name, incoming_value)
