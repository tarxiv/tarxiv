from sqlalchemy import Column, String, Text, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.sql import func

Base = declarative_base()


class Institution(Base):
    __tablename__ = "institutions"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name = Column(String, unique=True, nullable=False)
    website = Column(String)
    description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    users = relationship("User", back_populates="institution_rel")


class User(Base):
    __tablename__ = "users"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    orcid_id = Column(String, unique=True, nullable=False)
    provider_user_id = Column(String)
    username = Column(String, unique=True)
    nickname = Column(String)
    email = Column(String)
    institution_id = Column(UUID(as_uuid=True), ForeignKey("institutions.id"))
    institution = Column(String)  # Plain text legacy field from schema
    forename = Column(String)
    surname = Column(String)
    picture_url = Column(String)
    bio = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    institution_rel = relationship("Institution", back_populates="users")


class Team(Base):
    __tablename__ = "teams"

    id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    name = Column(String, unique=True, nullable=False)
    description = Column(Text)
    admin_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
