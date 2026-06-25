"""DTO - Data Transfer Objects for TarXiv.

This is the single source of truth for the API/dashboard data-transfer models.
(The dashboard previously kept a parallel copy in ``dashboard/schemas.py``; that
duplicate has been removed in favour of importing from here.)
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class MetadataResponseModel(BaseModel):
    """Schema for the metadata response from an object query.

    The metadata is source-keyed: every per-source payload lives under
    ``data_sources[<source>]`` and each source carries its own field set
    (e.g. ``tns`` provides discovery info, ``sherlock`` provides host
    associations, survey sources provide photometry arrays). The shape of
    each source dict therefore varies, so ``data_sources`` is kept permissive.

    The top-level fields carry the canonical object coordinates and provenance
    that the database now stores directly on the meta document: decimal
    (``ra_deg``/``dec_deg``) and sexagesimal (``ra_hms``/``dec_dms``)
    coordinates, plus discovery/update provenance.
    """

    tarxiv_id: str
    source: str | None = None
    source_id: str | None = None
    ra_deg: float | None = None
    dec_deg: float | None = None
    ra_hms: str | None = None  # sexagesimal HMS string
    dec_dms: str | None = None  # sexagesimal DMS string
    discovery_date: str | None = None
    update_date: str | None = None
    data_sources: dict[str, dict] = Field(default_factory=dict)


class LightcurveResponseSingle(BaseModel):
    """Schema for the lightcurve response from an object query."""

    mjd: float | None
    mag: float | None
    mag_err: float | None
    limit: float | None
    fwhm: float | None
    filter: str | None
    detection: int | None
    camera: str | None
    survey: str | None


LightcurveResponseModel = TypeAdapter(list[LightcurveResponseSingle])
# Apparently TypeAdapater shouldn't be used on BaseModel fields according to:
# https://docs.pydantic.dev/dev/concepts/type_adapter/
# But they don't provide an alternative and it works fine...


class ConeSearchResponseSingle(BaseModel):
    """Schema for a single result from a cone search."""

    obj_name: str
    ra: float
    dec: float
    distance_deg: float


ConeSearchResponseModel = TypeAdapter(list[ConeSearchResponseSingle])


class ProviderProfile(BaseModel):
    provider_user_id: str
    username: str | None = None
    nickname: str | None = None
    email: str | None = None
    institution: str | None = None
    forename: str | None = None
    surname: str | None = None
    picture_url: str | None = None
    bio: str | None = None


class User(BaseModel):
    id: UUID
    username: str | None = None
    nickname: str | None = None
    email: str | None = None
    institution: str | None = None
    forename: str | None = None
    surname: str | None = None
    picture_url: str | None = None
    bio: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class UserSummary(BaseModel):
    id: UUID
    username: str | None = None
    nickname: str | None = None
    email: str | None = None
    forename: str | None = None
    surname: str | None = None

    model_config = ConfigDict(from_attributes=True)


class UserProfileUpdate(BaseModel):
    username: str | None = None
    nickname: str | None = None
    email: str | None = None
    institution: str | None = None
    forename: str | None = None
    surname: str | None = None
    picture_url: str | None = None
    bio: str | None = None


class ExternalIdentity(BaseModel):
    id: UUID
    user_id: UUID
    provider: str
    provider_user_id: str
    provider_username: str | None = None
    provider_email: str | None = None
    provider_profile_json: dict | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class Team(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_by_user_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamSummary(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    is_member: bool = False

    model_config = ConfigDict(from_attributes=True)


class TeamMembership(BaseModel):
    team_id: UUID
    user_id: UUID
    role: str
    created_at: datetime | None = None
    team_name: str | None = None
    team_description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamMemberView(BaseModel):
    team_id: UUID
    user_id: UUID
    role: str
    created_at: datetime | None = None
    username: str | None = None
    forename: str | None = None
    surname: str | None = None
    email: str | None = None

    model_config = ConfigDict(from_attributes=True)


class Tag(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    color: str | None = None
    owner_type: str
    owner_id: UUID
    owner_name: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class TeamCreate(BaseModel):
    name: str
    description: str | None = None


class TeamUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class TeamMembershipCreate(BaseModel):
    user_id: UUID
    role: str = "member"


class TagCreate(BaseModel):
    name: str
    description: str | None = None
    color: str | None = None
    owner_team_id: UUID | None = None


class ObjectTagAssignment(BaseModel):
    id: UUID
    object_id: str
    tag_id: UUID
    applied_by_user_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ObjectTagAssignmentCreate(BaseModel):
    tag_id: UUID | None = None
    tag_name: str | None = None
    owner_team_id: UUID | None = None


class ObjectTagAssignmentView(BaseModel):
    id: UUID
    object_id: str
    tag: Tag
    owner_type: str
    owner_id: UUID
    applied_by_user_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class TaggedObject(BaseModel):
    object_id: str
