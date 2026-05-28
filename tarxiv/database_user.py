import os
from uuid import UUID

from sqlalchemy import create_engine, func, or_, text
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, joinedload, sessionmaker

from . import dto, orm
from .utils import TarxivModule


class DataLayerError(Exception):
    """Base exception for database errors."""


class UserRetrievalError(DataLayerError):
    """Raised when there is a system failure retrieving a user."""


class DuplicateValueError(DataLayerError):
    """Raised when a unique field conflicts with an existing record."""


class AccessDeniedError(DataLayerError):
    """Raised when a user is not permitted to access the requested resource."""


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
                    session
                    .query(orm.ExternalIdentity)
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
                session
                .query(orm.ExternalIdentity)
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

    def get_user(self, user_id: UUID | str) -> dto.User | None:
        with self.get_session() as session:
            try:
                user = session.get(orm.User, self._coerce_uuid(user_id))
                if user is None:
                    return None
                return dto.User.model_validate(user)
            except SQLAlchemyError as exc:
                raise UserRetrievalError(
                    "A system error occurred while accessing the user database."
                ) from exc

    def update_user_profile(
        self, user_id: UUID | str, profile_update: dto.UserProfileUpdate
    ) -> dto.User | None:
        session = self.get_session()
        try:
            user = session.get(orm.User, self._coerce_uuid(user_id))
            if user is None:
                return None

            for field_name, value in profile_update.model_dump(
                exclude_unset=True, exclude_none=False
            ).items():
                setattr(user, field_name, value)

            session.commit()
            session.refresh(user)
            return dto.User.model_validate(user)
        except IntegrityError as exc:
            session.rollback()
            if "username" in str(exc).lower():
                raise DuplicateValueError("Username is already taken.") from exc
            raise DataLayerError(
                "A system error occurred while updating the user profile."
            ) from exc
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while updating the user profile."
            ) from exc
        finally:
            session.close()

    def list_user_teams(self, user_id: UUID | str) -> list[dto.TeamMembership]:
        with self.get_session() as session:
            try:
                memberships = (
                    session
                    .query(orm.TeamMembership)
                    .options(joinedload(orm.TeamMembership.team))
                    .filter(orm.TeamMembership.user_id == self._coerce_uuid(user_id))
                    .all()
                )
                return [
                    dto.TeamMembership(
                        team_id=item.team_id,
                        user_id=item.user_id,
                        role=item.role,
                        created_at=item.created_at,
                        team_name=item.team.name if item.team is not None else None,
                        team_description=(
                            item.team.description if item.team is not None else None
                        ),
                    )
                    for item in memberships
                ]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while loading team memberships."
                ) from exc

    def list_tagged_object_ids_for_user(
        self, user_id: UUID | str, tag_ids: list[UUID | str]
    ) -> list[str]:
        if not tag_ids:
            return []

        with self.get_session() as session:
            try:
                user_uuid = self._coerce_uuid(user_id)
                team_ids = self._team_ids_for_user(session, user_uuid)
                normalized_tag_ids = [self._coerce_uuid(tag_id) for tag_id in tag_ids]

                query = (
                    session
                    .query(orm.ObjectTagAssignment.object_id)
                    .join(orm.Tag)
                    .filter(orm.ObjectTagAssignment.tag_id.in_(normalized_tag_ids))
                )

                if team_ids:
                    query = query.filter(
                        (orm.Tag.owner_user_id == user_uuid)
                        | (orm.Tag.owner_team_id.in_(team_ids))
                    )
                else:
                    query = query.filter(orm.Tag.owner_user_id == user_uuid)

                rows = query.distinct().all()
                return [row[0] for row in rows]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while loading tag-filtered objects."
                ) from exc

    def create_team(
        self, creator_user_id: UUID | str, team: dto.TeamCreate
    ) -> dto.Team:
        session = self.get_session()
        try:
            creator_uuid = self._coerce_uuid(creator_user_id)
            team_row = orm.Team(
                name=team.name,
                description=team.description,
                created_by_user_id=creator_uuid,
            )
            session.add(team_row)
            session.flush()
            session.add(
                orm.TeamMembership(
                    team_id=team_row.id,
                    user_id=creator_uuid,
                    role="owner",
                )
            )
            session.commit()
            session.refresh(team_row)
            return dto.Team.model_validate(team_row)
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while creating the team."
            ) from exc
        finally:
            session.close()

    def search_users(self, query: str, limit: int = 20) -> list[dto.UserSummary]:
        normalized = query.strip()
        if not normalized:
            return []

        with self.get_session() as session:
            try:
                pattern = f"%{normalized.lower()}%"
                users = (
                    session
                    .query(orm.User)
                    .filter(
                        or_(
                            func.lower(func.coalesce(orm.User.username, "")).like(
                                pattern
                            ),
                            func.lower(func.coalesce(orm.User.nickname, "")).like(
                                pattern
                            ),
                            func.lower(func.coalesce(orm.User.forename, "")).like(
                                pattern
                            ),
                            func.lower(func.coalesce(orm.User.surname, "")).like(
                                pattern
                            ),
                            func.lower(func.coalesce(orm.User.email, "")).like(pattern),
                        )
                    )
                    .order_by(orm.User.username.asc().nullslast(), orm.User.id.asc())
                    .limit(limit)
                    .all()
                )
                return [dto.UserSummary.model_validate(user) for user in users]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while searching for users."
                ) from exc

    def search_teams(
        self, user_id: UUID | str, query: str, limit: int = 20
    ) -> list[dto.TeamSummary]:
        normalized = query.strip()
        if not normalized:
            return []

        with self.get_session() as session:
            try:
                user_uuid = self._coerce_uuid(user_id)
                member_team_ids = set(self._team_ids_for_user(session, user_uuid))
                pattern = f"%{normalized.lower()}%"
                teams = (
                    session
                    .query(orm.Team)
                    .filter(
                        or_(
                            func.lower(orm.Team.name).like(pattern),
                            func.lower(func.coalesce(orm.Team.description, "")).like(
                                pattern
                            ),
                        )
                    )
                    .order_by(orm.Team.name.asc())
                    .limit(limit)
                    .all()
                )
                return [
                    dto.TeamSummary(
                        id=team.id,
                        name=team.name,
                        description=team.description,
                        is_member=team.id in member_team_ids,
                    )
                    for team in teams
                ]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while searching for teams."
                ) from exc

    def join_team(self, team_id: UUID | str, user_id: UUID | str) -> dto.TeamMembership:
        session = self.get_session()
        try:
            team_uuid = self._coerce_uuid(team_id)
            user_uuid = self._coerce_uuid(user_id)

            membership = (
                session
                .query(orm.TeamMembership)
                .options(joinedload(orm.TeamMembership.team))
                .filter(orm.TeamMembership.team_id == team_uuid)
                .filter(orm.TeamMembership.user_id == user_uuid)
                .first()
            )
            if membership is None:
                membership = orm.TeamMembership(
                    team_id=team_uuid,
                    user_id=user_uuid,
                    role="member",
                )
                session.add(membership)
                session.commit()
                membership = (
                    session
                    .query(orm.TeamMembership)
                    .options(joinedload(orm.TeamMembership.team))
                    .filter(orm.TeamMembership.team_id == team_uuid)
                    .filter(orm.TeamMembership.user_id == user_uuid)
                    .first()
                )

            if membership is None:
                raise DataLayerError("Team membership could not be created.")

            return dto.TeamMembership(
                team_id=membership.team_id,
                user_id=membership.user_id,
                role=membership.role,
                created_at=membership.created_at,
                team_name=membership.team.name if membership.team is not None else None,
                team_description=(
                    membership.team.description if membership.team is not None else None
                ),
            )
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while joining the team."
            ) from exc
        finally:
            session.close()

    def leave_team(self, team_id: UUID | str, user_id: UUID | str) -> bool:
        session = self.get_session()
        try:
            team_uuid = self._coerce_uuid(team_id)
            user_uuid = self._coerce_uuid(user_id)
            membership = (
                session
                .query(orm.TeamMembership)
                .filter(orm.TeamMembership.team_id == team_uuid)
                .filter(orm.TeamMembership.user_id == user_uuid)
                .first()
            )
            if membership is None:
                return False

            if membership.role == "owner":
                owner_count = (
                    session
                    .query(orm.TeamMembership)
                    .filter(orm.TeamMembership.team_id == team_uuid)
                    .filter(orm.TeamMembership.role == "owner")
                    .count()
                )
                if owner_count <= 1:
                    raise DataLayerError("You cannot leave a team as its only owner.")

            session.delete(membership)
            session.commit()
            return True
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while leaving the team."
            ) from exc
        finally:
            session.close()

    def add_user_to_team(
        self,
        team_id: UUID | str,
        acting_user_id: UUID | str,
        membership: dto.TeamMembershipCreate,
    ) -> dto.TeamMembership:
        session = self.get_session()
        try:
            team_uuid = self._coerce_uuid(team_id)
            actor_uuid = self._coerce_uuid(acting_user_id)
            target_user_uuid = self._coerce_uuid(membership.user_id)

            actor_membership = (
                session
                .query(orm.TeamMembership)
                .filter(orm.TeamMembership.team_id == team_uuid)
                .filter(orm.TeamMembership.user_id == actor_uuid)
                .first()
            )
            if actor_membership is None or actor_membership.role not in {
                "owner",
                "admin",
            }:
                raise DataLayerError("You do not have permission to add team members.")

            team_membership = (
                session
                .query(orm.TeamMembership)
                .filter(orm.TeamMembership.team_id == team_uuid)
                .filter(orm.TeamMembership.user_id == target_user_uuid)
                .first()
            )
            if team_membership is None:
                team_membership = orm.TeamMembership(
                    team_id=team_uuid,
                    user_id=target_user_uuid,
                    role=membership.role,
                )
                session.add(team_membership)
            else:
                team_membership.role = membership.role

            session.commit()
            session.refresh(team_membership)
            return dto.TeamMembership.model_validate(team_membership)
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while updating team membership."
            ) from exc
        finally:
            session.close()

    def list_team_members(
        self, team_id: UUID | str, requesting_user_id: UUID | str
    ) -> list[dto.TeamMemberView]:
        with self.get_session() as session:
            try:
                team_uuid = self._coerce_uuid(team_id)
                requester_uuid = self._coerce_uuid(requesting_user_id)
                self._ensure_team_membership(session, team_uuid, requester_uuid)

                memberships = (
                    session
                    .query(orm.TeamMembership)
                    .options(joinedload(orm.TeamMembership.user))
                    .filter(orm.TeamMembership.team_id == team_uuid)
                    .order_by(orm.TeamMembership.created_at.asc())
                    .all()
                )
                return [
                    dto.TeamMemberView(
                        team_id=item.team_id,
                        user_id=item.user_id,
                        role=item.role,
                        created_at=item.created_at,
                        username=item.user.username if item.user else None,
                        forename=item.user.forename if item.user else None,
                        surname=item.user.surname if item.user else None,
                        email=item.user.email if item.user else None,
                    )
                    for item in memberships
                ]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while loading team members."
                ) from exc

    def list_tags(self, user_id: UUID | str) -> list[dto.Tag]:
        with self.get_session() as session:
            try:
                user_uuid = self._coerce_uuid(user_id)
                team_ids = self._team_ids_for_user(session, user_uuid)
                query = session.query(orm.Tag).order_by(orm.Tag.name.asc())
                if team_ids:
                    tags = query.filter(
                        (orm.Tag.owner_user_id == user_uuid)
                        | (orm.Tag.owner_team_id.in_(team_ids))
                    ).all()
                else:
                    tags = query.filter(orm.Tag.owner_user_id == user_uuid).all()
                return [self._build_tag_dto(tag) for tag in tags]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while loading tags."
                ) from exc

    def create_tag(self, user_id: UUID | str, tag: dto.TagCreate) -> dto.Tag:
        session = self.get_session()
        try:
            user_uuid = self._coerce_uuid(user_id)
            owner_team_uuid = (
                self._coerce_uuid(tag.owner_team_id)
                if tag.owner_team_id is not None
                else None
            )
            if owner_team_uuid is not None:
                self._ensure_team_membership(session, owner_team_uuid, user_uuid)

            tag_row = orm.Tag(
                name=tag.name,
                description=tag.description,
                color=tag.color,
                owner_user_id=None if owner_team_uuid is not None else user_uuid,
                owner_team_id=owner_team_uuid,
            )
            session.add(tag_row)
            session.commit()
            session.refresh(tag_row)
            return self._build_tag_dto(tag_row)
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while creating the tag."
            ) from exc
        finally:
            session.close()

    def assign_tag_to_object(
        self,
        object_id: str,
        acting_user_id: UUID | str,
        assignment: dto.ObjectTagAssignmentCreate,
    ) -> dto.ObjectTagAssignmentView:
        session = self.get_session()
        try:
            actor_uuid = self._coerce_uuid(acting_user_id)
            team_ids = self._team_ids_for_user(session, actor_uuid)
            tag_row = self._resolve_visible_tag(
                session, assignment, actor_uuid, team_ids
            )

            existing = (
                session
                .query(orm.ObjectTagAssignment)
                .filter(orm.ObjectTagAssignment.object_id == object_id)
                .filter(orm.ObjectTagAssignment.tag_id == tag_row.id)
                .first()
            )
            if existing is not None:
                return self._build_assignment_view(existing)

            assignment_row = orm.ObjectTagAssignment(
                object_id=object_id,
                tag_id=tag_row.id,
                applied_by_user_id=actor_uuid,
            )
            session.add(assignment_row)
            session.commit()
            session.refresh(assignment_row)
            session.refresh(tag_row)
            return self._build_assignment_view(assignment_row)
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while assigning the tag to the object."
            ) from exc
        finally:
            session.close()

    def list_object_tags_for_user(
        self, object_id: str, user_id: UUID | str
    ) -> list[dto.ObjectTagAssignmentView]:
        with self.get_session() as session:
            try:
                user_uuid = self._coerce_uuid(user_id)
                team_ids = self._team_ids_for_user(session, user_uuid)

                query = (
                    session
                    .query(orm.ObjectTagAssignment)
                    .options(joinedload(orm.ObjectTagAssignment.tag))
                    .join(orm.Tag)
                    .filter(orm.ObjectTagAssignment.object_id == object_id)
                )
                if team_ids:
                    assignments = query.filter(
                        (orm.Tag.owner_user_id == user_uuid)
                        | (orm.Tag.owner_team_id.in_(team_ids))
                    ).all()
                else:
                    assignments = query.filter(orm.Tag.owner_user_id == user_uuid).all()

                return [self._build_assignment_view(item) for item in assignments]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while loading object tags."
                ) from exc

    def list_objects_for_tag(
        self, tag_id: UUID | str, user_id: UUID | str, limit: int = 100, offset: int = 0
    ) -> list[dto.TaggedObject]:
        with self.get_session() as session:
            try:
                user_uuid = self._coerce_uuid(user_id)
                tag_uuid = self._coerce_uuid(tag_id)
                team_ids = self._team_ids_for_user(session, user_uuid)

                query = (
                    session
                    .query(orm.ObjectTagAssignment.object_id)
                    .join(orm.Tag)
                    .filter(orm.ObjectTagAssignment.tag_id == tag_uuid)
                )
                if team_ids:
                    query = query.filter(
                        (orm.Tag.owner_user_id == user_uuid)
                        | (orm.Tag.owner_team_id.in_(team_ids))
                    )
                else:
                    query = query.filter(orm.Tag.owner_user_id == user_uuid)

                object_ids = (
                    query
                    .order_by(orm.ObjectTagAssignment.object_id.asc())
                    .limit(limit)
                    .offset(offset)
                    .all()
                )
                return [dto.TaggedObject(object_id=row[0]) for row in object_ids]
            except SQLAlchemyError as exc:
                raise DataLayerError(
                    "A system error occurred while loading tagged objects."
                ) from exc

    def remove_object_tag_assignment(
        self, assignment_id: UUID | str, acting_user_id: UUID | str
    ) -> bool:
        session = self.get_session()
        try:
            actor_uuid = self._coerce_uuid(acting_user_id)
            assignment = (
                session
                .query(orm.ObjectTagAssignment)
                .filter(orm.ObjectTagAssignment.id == self._coerce_uuid(assignment_id))
                .first()
            )
            if assignment is None:
                return False

            if assignment.tag.owner_user_id == actor_uuid:
                allowed = True
            elif assignment.tag.owner_team_id is not None:
                membership = (
                    session
                    .query(orm.TeamMembership)
                    .filter(orm.TeamMembership.team_id == assignment.tag.owner_team_id)
                    .filter(orm.TeamMembership.user_id == actor_uuid)
                    .first()
                )
                allowed = membership is not None
            else:
                allowed = False

            if not allowed:
                raise DataLayerError("You do not have permission to remove this tag.")

            session.delete(assignment)
            session.commit()
            return True
        except SQLAlchemyError as exc:
            session.rollback()
            raise DataLayerError(
                "A system error occurred while removing the object tag."
            ) from exc
        finally:
            session.close()

    @staticmethod
    def _coerce_uuid(value: UUID | str) -> UUID:
        if isinstance(value, UUID):
            return value
        return UUID(str(value))

    @staticmethod
    def _resolve_tag(
        session: Session, assignment: dto.ObjectTagAssignmentCreate
    ) -> orm.Tag:
        raise NotImplementedError

    @staticmethod
    def _ensure_team_membership(session: Session, team_id: UUID, user_id: UUID) -> None:
        membership = (
            session
            .query(orm.TeamMembership)
            .filter(orm.TeamMembership.team_id == team_id)
            .filter(orm.TeamMembership.user_id == user_id)
            .first()
        )
        if membership is None:
            raise AccessDeniedError("You are not a member of the requested team.")

    @staticmethod
    def _build_assignment_view(
        assignment: orm.ObjectTagAssignment,
    ) -> dto.ObjectTagAssignmentView:
        owner_type = "team" if assignment.tag.owner_team_id is not None else "user"
        owner_id = assignment.tag.owner_team_id or assignment.tag.owner_user_id
        if owner_id is None:
            raise DataLayerError("Invalid tag assignment owner state.")

        return dto.ObjectTagAssignmentView(
            id=assignment.id,
            object_id=assignment.object_id,
            tag=UserDB._build_tag_dto(assignment.tag),
            owner_type=owner_type,
            owner_id=owner_id,
            applied_by_user_id=assignment.applied_by_user_id,
            created_at=assignment.created_at,
            updated_at=assignment.updated_at,
        )

    @staticmethod
    def _build_tag_dto(tag: orm.Tag) -> dto.Tag:
        owner_type = "team" if tag.owner_team_id is not None else "user"
        owner_id = tag.owner_team_id or tag.owner_user_id
        if owner_id is None:
            raise DataLayerError("Invalid tag owner state.")

        if owner_type == "team":
            owner_name = tag.owner_team.name if tag.owner_team is not None else None
        else:
            owner_name = tag.owner_user.username if tag.owner_user is not None else None

        return dto.Tag(
            id=tag.id,
            name=tag.name,
            description=tag.description,
            color=tag.color,
            owner_type=owner_type,
            owner_id=owner_id,
            owner_name=owner_name,
            created_at=tag.created_at,
            updated_at=tag.updated_at,
        )

    @staticmethod
    def _team_ids_for_user(session: Session, user_id: UUID) -> list[UUID]:
        return [
            membership.team_id
            for membership in (
                session
                .query(orm.TeamMembership)
                .filter(orm.TeamMembership.user_id == user_id)
                .all()
            )
        ]

    @staticmethod
    def _resolve_visible_tag(
        session: Session,
        assignment: dto.ObjectTagAssignmentCreate,
        user_id: UUID,
        team_ids: list[UUID],
    ) -> orm.Tag:
        query = session.query(orm.Tag)

        if assignment.tag_id is not None:
            query = query.filter(orm.Tag.id == assignment.tag_id)
        elif assignment.tag_name is not None:
            query = query.filter(orm.Tag.name == assignment.tag_name)
            if assignment.owner_team_id is not None:
                query = query.filter(
                    orm.Tag.owner_team_id
                    == UserDB._coerce_uuid(assignment.owner_team_id)
                )
            else:
                query = query.filter(orm.Tag.owner_user_id == user_id)
        else:
            raise DataLayerError("A tag_id or tag_name is required.")

        tag_row = query.first()
        if tag_row is None:
            raise DataLayerError("Tag not found.")

        if tag_row.owner_user_id == user_id:
            return tag_row
        if tag_row.owner_team_id is not None and tag_row.owner_team_id in team_ids:
            return tag_row

        raise DataLayerError("Tag not found.")
