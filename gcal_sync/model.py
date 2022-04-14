"Library for data model for local calendar objects." ""

from __future__ import annotations

import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, root_validator

DATE_STR_FORMAT = "%Y-%m-%d"


class Calendar(BaseModel):
    """Metadata associated with a calendar."""

    id: str
    summary: str
    description: Optional[str]
    location: Optional[str]
    timezone: Optional[str]


class Datetime(BaseModel):
    """A date or datetime."""

    date: Optional[datetime.date]
    date_time: Optional[datetime.datetime] = Field(alias="dateTime")
    timezone: Optional[str] = Field(alias="timeZone")

    @property
    def value(self) -> Union[datetime.date, datetime.datetime]:
        """Return either a datetime or date representing the Datetime."""
        if self.date is not None:
            return self.date
        if self.date_time is not None:
            return self.date_time
        raise ValueError("Datetime has invalid state with no date or date_time")

    @root_validator
    def check_date_or_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        if not values.get("date") and not values.get("date_time"):
            raise ValueError("Unexpected missing date or dateTime value")
        return values


class Event(BaseModel):
    """A single event on a calendar."""

    id: Optional[str] = None
    summary: str
    start: Datetime
    end: Datetime
    description: Optional[str]
    location: Optional[str]
    transparency: Optional[str]
