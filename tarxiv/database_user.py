import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError

from .utils import TarxivModule

from . import orm, dto


class DataLayerError(Exception):
    """Base exception for database errors."""

    pass


class UserRetrievalError(DataLayerError):
    """Raised when there is a system failure retrieving a user."""

    pass


class UserDB(TarxivModule):
    """ """

    def __init__(self, script_name, reporting_mode, debug=False):
        super().__init__(
            script_name=script_name,
            module="UserDB",
            reporting_mode=reporting_mode,
            debug=debug,
        )

        log = {"status": "Initializing UserDB module."}
        self.logger.info(log, extra=log)

        connection_url = os.environ.get("TARXIV_POSTGRES_URL")
        if not connection_url:
            raise RuntimeError("Missing TARXIV_POSTGRES_URL environment variable")

        self.engine = create_engine(connection_url)
        self.session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

        try:
            self._test_db_connection()
        except Exception as e:
            self.logger.error(f"Failed to connect to the database: {e}")
            raise RuntimeError(
                "Database connection failed. Check logs for details."
            ) from e

    def _test_db_connection(self):
        """Test the database connection by executing a simple query."""
        try:
            with self.get_session() as session:
                result = session.execute(text("SELECT 1"))
                if result.scalar() == 1:
                    log = {"status": "Database connection test successful."}
                    self.logger.info(log, extra=log)
                else:
                    log = {
                        "status": "Database connection test failed: Unexpected result."
                    }
                    self.logger.error(log, extra=log)
        except Exception as e:
            self.logger.error(f"Database connection test failed: {e}")
            raise

    def get_session(self) -> Session:
        """Provide a session for database operations."""
        return self.session()

    # def sync_user_profile(self, orcid_id: str, profile_data: dict) -> dto.User:
    #     """
    #     Create or update a user based on their ORCID profile.

    #     :param orcid_id: The unique ORCID iD
    #     :param profile_data: Normalized profile dictionary from ORCID provider
    #     :return: Updated or newly created User object
    #     """
    #     session = self.get_session()
    #     try:
    #         user = session.query(orm.User).filter(orm.User.orcid_id == orcid_id).first()

    #         if not user:
    #             log = {"status": f"Creating new user for ORCID: {orcid_id}"}
    #             self.logger.info(log, extra=log)
    #             user = orm.User(orcid_id=orcid_id)
    #             session.add(user)
    #         else:
    #             log = {"status": f"Updating existing user for ORCID: {orcid_id}"}
    #             self.logger.info(log, extra=log)

    #         # # Map profile data to User model fields
    #         # user.email = profile_data.get("email")
    #         # user.forename = profile_data.get("forename")
    #         # user.surname = profile_data.get("surname")
    #         # user.username = profile_data.get("username")
    #         # user.nickname = profile_data.get("nickname")
    #         # user.bio = profile_data.get("bio")
    #         # user.picture_url = profile_data.get("picture_url")
    #         # user.provider_user_id = profile_data.get("provider_user_id")

    #         session.commit()
    #         session.refresh(user)
    #         return dto.User.model_validate(user)
    #     except Exception as e:
    #         session.rollback()
    #         log = {"status": f"Error syncing user {orcid_id}: {str(e)}"}
    #         self.logger.error(log, extra=log)
    #         raise
    #     finally:
    #         session.close()

    def get_user_by_orcid_id(self, orcid_id: str) -> dto.User | None:
        """Retrieve a user by their ORCID ID.

        Parameters
        ----------
        orcid_id (str): The ORCID iD of the user to retrieve.

        Returns
        -------
        dto.User: The dto.User object corresponding to the provided ORCID iD, or None if not found.
        """
        with Session(self.engine) as session:
            try:
                user = (
                    session.query(orm.User)
                    .filter(orm.User.orcid_id == orcid_id)
                    .first()
                )
                if user:
                    log = {"status": f"User found for ORCID: {orcid_id}"}
                    self.logger.info(log, extra=log)
                    return dto.User.model_validate(user)
                else:
                    log = {"status": f"No user found for ORCID: {orcid_id}"}
                    self.logger.info(log, extra=log)
                    return None
            except SQLAlchemyError as e:
                # exc_info=True automatically includes the full stack trace in your logs
                log = {"status": f"Database error while querying ORCID {orcid_id}: {e}"}
                self.logger.error(log, extra=log, exc_info=True)

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
    def insert_new_user(self, user: dto.User) -> dto.User:
        """Insert a new user into the database.

        Parameters
        ----------
        user (dto.User): The user data to insert.

        Returns
        -------
        dto.User: The newly created user object.

        Raises
        ------
        DataLayerError: If there is an error during insertion.
        """
        session = self.get_session()
        try:
            # Check for existing user with the same ORCID ID
            existing_user = (
                session.query(orm.User)
                .filter(orm.User.orcid_id == user.orcid_id)
                .first()
            )
            if existing_user:
                # TODO: Should this change to an update instead of raising an error?
                # Depends on how we want to handle duplicates.
                raise DataLayerError(f"User with ORCID {user.orcid_id} already exists.")

            # new_user = User(
            #     orcid_id=user.orcid_id,
            #     email=user.email,
            #     forename=user.forename,
            #     surname=user.surname,
            #     username=user.username,
            #     nickname=user.nickname,
            #     bio=user.bio,
            #     picture_url=user.picture_url,
            #     provider_user_id=user.provider_user_id,
            # )

            # user.model_dump() converts the Pydantic object to a dictionary.
            # exclude_unset=True ignores fields the frontend didn't provide.
            # This is definitely a design choice - it REQURIES the ORMs and DTOs to have matching field names
            # DTO field names can also have aliases via Field(..., alias="fieldName")
            new_user = orm.User(**user.model_dump(exclude_unset=True))

            session.add(new_user)
            session.commit()
            session.refresh(new_user)

            return dto.User.model_validate(new_user)
        except SQLAlchemyError as e:
            session.rollback()
            log = {
                "status": f"Database error while inserting user {user.orcid_id}: {str(e)}"
            }
            self.logger.error(log, extra=log)
            raise DataLayerError(
                "A system error occurred while inserting the user into the database."
            ) from e
