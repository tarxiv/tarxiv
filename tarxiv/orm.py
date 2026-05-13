"""ORM models for TarXiv relational data."""

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    username: Mapped[str | None] = mapped_column(String, unique=True)
    nickname: Mapped[str | None] = mapped_column(String)
    email: Mapped[str | None] = mapped_column(String)
    institution: Mapped[str | None] = mapped_column(String)
    forename: Mapped[str | None] = mapped_column(String)
    surname: Mapped[str | None] = mapped_column(String)
    picture_url: Mapped[str | None] = mapped_column(String)
    bio: Mapped[str | None] = mapped_column(Text)

    identities: Mapped[list["ExternalIdentity"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    owned_teams: Mapped[list["Team"]] = relationship(back_populates="created_by_user")
    owned_tags: Mapped[list["Tag"]] = relationship(
        back_populates="owner_user", foreign_keys="Tag.owner_user_id"
    )
    team_memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    applied_tag_assignments: Mapped[list["ObjectTagAssignment"]] = relationship(
        back_populates="applied_by_user",
        foreign_keys="ObjectTagAssignment.applied_by_user_id",
    )


class ExternalIdentity(TimestampMixin, Base):
    __tablename__ = "external_identities"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String, nullable=False)
    provider_user_id: Mapped[str] = mapped_column(String, nullable=False)
    provider_username: Mapped[str | None] = mapped_column(String)
    provider_email: Mapped[str | None] = mapped_column(String)
    provider_profile_json: Mapped[dict | None] = mapped_column(JSON)

    user: Mapped[User] = relationship(back_populates="identities")

    __table_args__ = (
        UniqueConstraint("provider", "provider_user_id", name="uq_external_identity"),
    )


class Team(TimestampMixin, Base):
    __tablename__ = "teams"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    created_by_user: Mapped[User | None] = relationship(back_populates="owned_teams")
    memberships: Mapped[list["TeamMembership"]] = relationship(
        back_populates="team", cascade="all, delete-orphan"
    )
    owned_tags: Mapped[list["Tag"]] = relationship(
        back_populates="owner_team",
        foreign_keys="Tag.owner_team_id",
    )


class TeamMembership(Base):
    __tablename__ = "team_memberships"

    team_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[str] = mapped_column(
        String, nullable=False, server_default=text("'member'")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    team: Mapped[Team] = relationship(back_populates="memberships")
    user: Mapped[User] = relationship(back_populates="team_memberships")


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    color: Mapped[str | None] = mapped_column(String)
    owner_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE")
    )
    owner_team_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE")
    )

    owner_user: Mapped[User | None] = relationship(
        back_populates="owned_tags", foreign_keys=[owner_user_id]
    )
    owner_team: Mapped[Team | None] = relationship(
        back_populates="owned_tags", foreign_keys=[owner_team_id]
    )

    object_assignments: Mapped[list["ObjectTagAssignment"]] = relationship(
        back_populates="tag", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "(owner_user_id IS NOT NULL AND owner_team_id IS NULL) OR "
            "(owner_user_id IS NULL AND owner_team_id IS NOT NULL)",
            name="ck_tags_single_owner",
        ),
        UniqueConstraint("owner_user_id", "name", name="uq_tags_owner_user_name"),
        UniqueConstraint("owner_team_id", "name", name="uq_tags_owner_team_name"),
    )


class ObjectTagAssignment(TimestampMixin, Base):
    __tablename__ = "object_tag_assignments"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    object_id: Mapped[str] = mapped_column(String, nullable=False)
    tag_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tags.id", ondelete="CASCADE"), nullable=False
    )
    applied_by_user_id: Mapped[UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )

    tag: Mapped[Tag] = relationship(back_populates="object_assignments")
    applied_by_user: Mapped[User | None] = relationship(
        back_populates="applied_tag_assignments",
        foreign_keys=[applied_by_user_id],
    )

    __table_args__ = (
        UniqueConstraint("object_id", "tag_id", name="uq_object_tag_assignment"),
    )
