"Library for data model for local calendar objects." ""

from __future__ import annotations

import datetime
import zoneinfo
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, root_validator

DATE_STR_FORMAT = "%Y-%m-%d"
EVENT_FIELDS = "id,summary,description,location,start,end,transparency"


class Calendar(BaseModel):
    """Metadata associated with a calendar."""

    id: str
    summary: str = ""
    description: Optional[str]
    location: Optional[str]
    timezone: Optional[str]


class DateOrDatetime(BaseModel):
    """A date or datetime."""

    date: Optional[datetime.date]
    date_time: Optional[datetime.datetime] = Field(alias="dateTime")
    # Note: timezone is only used for creating new events
    timezone: Optional[str] = Field(alias="timeZone")

    @property
    def value(self) -> Union[datetime.date, datetime.datetime]:
        """Return either a datetime or date representing the Datetime."""
        if self.date is not None:
            return self.date
        if self.date_time is not None:
            if self.timezone is not None:
                return self.date_time.replace(tzinfo=zoneinfo.ZoneInfo(self.timezone))
            return self.date_time
        raise ValueError("Datetime has invalid state with no date or date_time")

    @root_validator
    def check_date_or_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        if not values.get("date") and not values.get("date_time"):
            raise ValueError("Unexpected missing date or dateTime value")
        # Truncate microseconds for datetime serialization back to json
        if datetime_value := values.get("date_time"):
            if isinstance(datetime_value, datetime.datetime):
                values["date_time"] = datetime_value.replace(microsecond=0)
        elif values.get("timezone"):
            raise ValueError("Timezone with date (only) not supported")
        return values

    class Config:
        """Model configuration."""
        allow_population_by_field_name = True
        arbitrary_types_allowed = True


class Event(BaseModel):
    """A single event on a calendar."""

    id: Optional[str] = None
    summary: str = ""
    start: DateOrDatetime
    end: DateOrDatetime
    description: Optional[str]
    location: Optional[str]
    transparency: str = Field(default="opaque")

    class Config:
        """Model configuration."""
        allow_population_by_field_name = True
