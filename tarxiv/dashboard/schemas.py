from typing import List, Optional

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

    value: str | float
    source: str


class Detection(PropertyValue):
    """A detection, nondetection, or change with additional fields."""

    filter: str
    # date: datetime | str
    date: str


class MetadataResponseModel(BaseModel):
    """Schema for the metadata response from an object query."""

    sources: list[Source]
    identifiers: list[Identifier]
    ra_deg: list[PropertyValue]
    dec_deg: list[PropertyValue]
    ra_hms: list[PropertyValue]
    dec_dms: list[PropertyValue]
    object_type: list[PropertyValue]
    discovery_date: list[PropertyValue]
    reporting_group: list[PropertyValue]
    discovery_data_source: list[PropertyValue]
    redshift: list[PropertyValue]
    peak_mag: list[Detection]
    latest_detection: list[Detection]
    latest_nondetection: list[Detection]
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
