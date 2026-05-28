"""DTO - Data Transfer Objects for TarXiv."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

# from datetime import datetime


# class SearchIDRequest(BaseModel):
#     search_id: str


# class ConeSearchRequest(BaseModel):
#     ra: float
#     dec: float
#     radius: float  # in arcseconds


class Source(BaseModel):
    """Source of the data for a given property."""

    name: str
    bibcode: str
    reference: str
    alias: int


class Identifier(BaseModel):
    """An identifier for the object from a given source."""

    name: str | int
    source: str


class PropertyValue(BaseModel):
    """A value for a given property from a given source."""

    value: str | float | None
    source: str | None


class Detection(PropertyValue):
    """A detection, nondetection, or change with additional fields."""

    filter: str
    # date: datetime | str
    date: str
    mag_rate: Optional[float] = None


class MetadataResponseModel(BaseModel):
    """Schema for the metadata response from an object query."""

    sources: list[Source]
    identifiers: list[Identifier]
    ra_deg: list[PropertyValue] | None = None
    dec_deg: list[PropertyValue] | None = None
    ra_hms: list[PropertyValue] | None = None
    dec_dms: list[PropertyValue] | None = None
    object_type: list[PropertyValue] | None = None
    discovery_date: list[PropertyValue] | None = None
    reporting_group: list[PropertyValue] | None = None
    discovery_data_source: list[PropertyValue] | None = None
    redshift: list[PropertyValue] | None = None
    peak_mag: list[Detection] | None = None
    latest_detection: list[Detection] | None = None
    latest_nondetection: list[Detection] | None = None
    latest_change: Optional[list[Detection]] = Field(default_factory=list)


class LightcurveResponseSingle(BaseModel):
    """Schema for the lightcurve response from an object query."""

    mjd: float | None
    mag: float | None
    mag_err: float | None
    limit: float | None
    fwhm: float | None
    filter: str | None
    detection: int | None
    tel_unit: str | None
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
