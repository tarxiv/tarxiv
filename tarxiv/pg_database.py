import os
import logging

from pydantic import BaseModel, ConfigDict
from typing import Optional
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .orm_models import Base, User
from .schemas import UserDTO

logger = logging.getLogger(__name__)


class DataLayerError(Exception):
    """Base exception for database errors."""

    pass


class UserRetrievalError(DataLayerError):
    """Raised when there is a system failure retrieving a user."""

    pass


class UserSchema(BaseModel):
    """A static, safe representation of a User for the Dash UI."""

    model_config = ConfigDict(
        from_attributes=True
    )  # Essential for SQLAlchemy integration

    id: int
    orcid_id: str
    name: str
    email: Optional[str] = None
    # Note: Only include fields the UI actually needs!


class PostgresDB:
    """Interface for TarXiv PostgreSQL data."""

    def __init__(self, connection_url=None):
        if not connection_url:
            connection_url = os.environ.get("TARXIV_POSTGRES_URL")
            if not connection_url:
                raise RuntimeError("Missing TARXIV_POSTGRES_URL environment variable")

        self.engine = create_engine(connection_url)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def get_session(self) -> Session:
        """Provide a session for database operations."""
        return self.SessionLocal()

    def sync_user_profile(self, orcid_id: str, profile_data: dict) -> UserDTO:
        """
        Create or update a user based on their ORCID profile.

        :param orcid_id: The unique ORCID iD
        :param profile_data: Normalized profile dictionary from ORCID provider
        :return: Updated or newly created User object
        """
        session = self.get_session()
        try:
            user = session.query(User).filter(User.orcid_id == orcid_id).first()

            if not user:
                logger.info(f"Creating new user for ORCID: {orcid_id}")
                user = User(orcid_id=orcid_id)
                session.add(user)
            else:
                logger.info(f"Updating existing user for ORCID: {orcid_id}")

            # Map profile data to User model fields
            user.email = profile_data.get("email")
            user.forename = profile_data.get("forename")
            user.surname = profile_data.get("surname")
            user.username = profile_data.get("username")
            user.nickname = profile_data.get("nickname")
            user.bio = profile_data.get("bio")
            user.picture_url = profile_data.get("picture_url")
            user.provider_user_id = profile_data.get("provider_user_id")

            session.commit()
            session.refresh(user)
            return UserDTO.model_validate(user)
        except Exception as e:
            session.rollback()
            logger.error(f"Error syncing user {orcid_id}: {str(e)}")
            raise
        finally:
            session.close()

    def get_user_by_orcid_id(self, orcid_id: str) -> UserDTO | None:
        """Retrieve a user by their ORCID ID.

        Parameters
        ----------
        orcid_id (str): The ORCID iD of the user to retrieve.

        Returns
        -------
        UserDTO: The UserDTO object corresponding to the provided ORCID iD, or None if not found.
        """
        with Session(self.engine) as session:
            try:
                user = session.query(User).filter(User.orcid_id == orcid_id).first()
                if user:
                    logger.info(f"User found for ORCID: {orcid_id}")
                    return UserDTO.model_validate(user)
                else:
                    logger.info(f"No user found for ORCID: {orcid_id}")
                    return None
            except SQLAlchemyError as e:
                # exc_info=True automatically includes the full stack trace in your logs
                logger.error(
                    f"Database error while querying ORCID {orcid_id}: {e}",
                    exc_info=True,
                )

                # Raise a clean, custom exception for the UI layer to catch
                raise UserRetrievalError(
                    "A system error occurred while accessing the user database."
                ) from e

    # Insert a new user into the database, I have a few questions:
    # 1. Should this check for existing users or do that logic externally?
    # A: Check here to prevent duplicates
    # 2. Should this return the new user or just a success/failure status?
    # A: Return the new user for confirmation and potential use in the UI
    # 3. Should this raise exceptions on failure or return a status code/message?
    # A: Raise exceptions to allow the UI to handle them appropriately
    def insert_new_user(self, user: UserDTO):
        """Insert a new user into the database.

        Parameters
        ----------
        user (UserDTO): The user data to insert.

        Returns
        -------
        UserDTO: The newly created user object.

        Raises
        ------
        DataLayerError: If there is an error during insertion.
        """
        session = self.get_session()
        try:
            # Check for existing user with the same ORCID ID
            existing_user = (
                session.query(User).filter(User.orcid_id == user.orcid_id).first()
            )
            if existing_user:
                # TODO: Should this change to an update instead of raising an error?
                # Depends on how we want to handle duplicates.
                raise DataLayerError(f"User with ORCID {user.orcid_id} already exists.")

            new_user = User(
                orcid_id=user.orcid_id,
                email=user.email,
                forename=user.forename,
                surname=user.surname,
                username=user.username,
                nickname=user.nickname,
                bio=user.bio,
                picture_url=user.picture_url,
                provider_user_id=user.provider_user_id,
            )
            session.add(new_user)
            session.commit()
            session.refresh(new_user)
            return UserDTO.model_validate(new_user)
        except SQLAlchemyError as e:
            session.rollback()
            logger.error(f"Database error while inserting user {user.orcid_id}: {e}")
            raise DataLayerError(
                "A system error occurred while inserting the user into the database."
            ) from e
