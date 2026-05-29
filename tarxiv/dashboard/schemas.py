from typing import Optional

from pydantic import BaseModel, TypeAdapter, Field

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
    """Schema for the metadata response from an object query.

    The metadata is source-keyed: every per-source payload lives under
    ``data_sources[<source>]`` and each source carries its own field set
    (e.g. ``tns`` provides discovery info, ``sherlock`` provides host
    associations, survey sources provide photometry arrays). The shape of
    each source dict therefore varies, so ``data_sources`` is kept permissive.
    """

    tarxiv_id: str
    source: str | None = None
    ra: str | None = None  # top-level HMS string
    dec: str | None = None  # top-level DMS string
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
