"Library for data model for local calendar objects." ""

from __future__ import annotations

import datetime
import zoneinfo
from enum import Enum
from typing import Any, Optional, Union

from pydantic import BaseModel, Field, root_validator

DATE_STR_FORMAT = "%Y-%m-%d"
EVENT_FIELDS = (
    "id,summary,description,location,start,end,transparency,eventType,"
    "visibility,attendees,attendeesOmitted"
)


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
            if self.date_time.tzinfo is None and self.timezone is not None:
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


class EventStatusEnum(str, Enum):
    "Status of the event."

    CONFIRMED = "confirmed"
    TENTATIVE = "tentative"
    CANCELLED = "cancelled"


class EventTypeEnum(str, Enum):
    """Type of the event."""

    DEFAULT = "default"
    OUT_OF_OFFICE = "outOfOffice"
    FOCUS_TIME = "focusTime"


class VisibilityEnum(str, Enum):
    """Visibility of the event."""

    DEFAULT = "default"
    PUBLIC = "public"
    PRIVATE = "private"  # Same as confidential


class ResponseStatus(str, Enum):
    """The attendee's response status."""

    NEEDS_ACTION = "needsAction"
    DECLINED = "declined"
    TENTATIVE = "tentative"
    ACCEPTED = "accepted"


class Attendee(BaseModel):
    """An attendee of an event."""

    id: Optional[str] = None
    email: str = ""
    display_name: Optional[str] = Field(alias="displayName", default=None)
    optional: bool = False
    comment: Optional[str] = None
    response_status: ResponseStatus = Field(
        alias="responseStatus", default=ResponseStatus.NEEDS_ACTION
    )


class Event(BaseModel):
    """A single event on a calendar."""

    id: Optional[str] = None
    summary: str = ""
    start: DateOrDatetime
    end: DateOrDatetime
    description: Optional[str]
    location: Optional[str]
    transparency: str = Field(default="opaque")
    # Note deleted events are only returned in some scenarios based on request options
    # such as enabling incremental sync or explicitly asking for deleted items. That is,
    # most users should not need to check the status.
    status: EventStatusEnum = EventStatusEnum.CONFIRMED
    event_type: EventTypeEnum = Field(alias="eventType", default=EventTypeEnum.DEFAULT)
    visibility: VisibilityEnum = VisibilityEnum.DEFAULT
    attendees: list[Attendee] = []
    attendeesOmitted: bool = False

    @root_validator(pre=True)
    def allow_cancelled_events(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Special case for canceled event tombstones that are missing required fields."""
        if status := values.get("status"):
            if status == EventStatusEnum.CANCELLED:
                if "start" not in values:
                    values["start"] = DateOrDatetime(date=datetime.date.min)
                if "end" not in values:
                    values["end"] = DateOrDatetime(date=datetime.date.min)
        return values

    @root_validator(pre=True)
    def adjust_visibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Convert legacy visibility types to new types."""
        if visibility := values.get("visibility"):
            if visibility == "confidential":
                values["visibility"] = "private"
        return values

    class Config:
        """Model configuration."""

        allow_population_by_field_name = True
