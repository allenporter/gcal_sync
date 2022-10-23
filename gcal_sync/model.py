"Library for data model for local calendar objects." ""

from __future__ import annotations

import datetime
import logging
import zoneinfo
from enum import Enum
from typing import Any, Optional, Union

from dateutil import rrule
from pydantic import BaseModel, Field, root_validator

from .timespan import Timespan

_LOGGER = logging.getLogger(__name__)

DATE_STR_FORMAT = "%Y-%m-%d"
EVENT_FIELDS = (
    "id,summary,description,location,start,end,transparency,status,eventType,"
    "visibility,attendees,attendeesOmitted,recurrence,recurringEventId,originalStartTime"
)
MIDNIGHT = datetime.time()


class Calendar(BaseModel):
    """Metadata associated with a calendar."""

    id: str
    summary: str = ""
    description: Optional[str]
    location: Optional[str]
    timezone: Optional[str] = Field(alias="timeZone", default=None)


class DateOrDatetime(BaseModel):
    """A date or datetime."""

    date: Optional[datetime.date] = Field(default=None)
    date_time: Optional[datetime.datetime] = Field(alias="dateTime", default=None)
    # Note: timezone is only used for creating new events
    timezone: Optional[str] = Field(alias="timeZone", default=None)

    @classmethod
    def parse(cls, value: datetime.date | datetime.datetime) -> DateOrDatetime:
        """Create a DateOrDatetime from a raw date or datetime value."""
        if isinstance(value, datetime.datetime):
            return cls(date_time=value)
        return cls(date=value)

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

    def normalize(self, tzinfo: datetime.tzinfo | None = None) -> datetime.datetime:
        """Convert date or datetime to a value that can be used for comparison."""
        value = self.value
        if not isinstance(value, datetime.datetime):
            value = datetime.datetime.combine(value, MIDNIGHT)
        if value.tzinfo is None:
            value = value.replace(tzinfo=(tzinfo if tzinfo else datetime.timezone.utc))
        return value

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, DateOrDatetime):
            return NotImplemented
        return self.normalize() < other.normalize()

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, DateOrDatetime):
            return NotImplemented
        return self.normalize() > other.normalize()

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, DateOrDatetime):
            return NotImplemented
        return self.normalize() <= other.normalize()

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, DateOrDatetime):
            return NotImplemented
        return self.normalize() >= other.normalize()

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
    ical_uuid: Optional[str] = Field(alias="iCalUID", default=None)
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
    attendees_omitted: bool = Field(alias="attendeesOmitted", default=False)
    recurrence: list[str] = []
    recurring_event_id: Optional[str] = Field(alias="recurringEventId", default=None)
    original_start_time: Optional[DateOrDatetime] = Field(
        alias="originalStartTime", default=None
    )

    @property
    def computed_duration(self) -> datetime.timedelta:
        """Return the event duration."""
        return self.end.value - self.start.value

    @property
    def rrule(self) -> rrule.rrule | rrule.rruleset:
        """Return the recurrence rules as a set of rules."""
        try:
            return rrule.rrulestr("\n".join(self.recurrence), dtstart=self.start.value)
        except ValueError as err:
            raise ValueError(
                f"Invalid recurrence rule: {self.json()}: {str(err)}"
            ) from err

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

    @root_validator
    def validate_rrule(cls, values: dict[str, Any]) -> dict[str, Any]:
        """The API returns invalid RRULEs that need to be coerced to valid."""
        # Rules may need updating of start time has a timezone
        if not (recurrence := values.get("recurrence")) or not (
            dtstart := values.get("start")
        ):
            return values
        values["recurrence"] = [cls._adjust_rrule(rule, dtstart) for rule in recurrence]
        return values

    @classmethod
    def _adjust_rrule(cls, rule: str, dtstart: DateOrDatetime) -> str:
        """Apply fixes to the rrule."""
        if not rule.startswith("RRULE:"):
            return rule

        parts = {}
        for part in rule[6:].split(";"):
            if "=" not in part:
                raise ValueError(
                    f"Recurrence rule had unexpected format missing '=': {rule}"
                )
            key, value = part.split("=", 1)
            key = key.upper()
            parts[key.upper()] = value

        if not (until := parts.get("UNTIL")):
            return rule

        until_parts = until.split("T")
        if len(until_parts) > 2:
            raise ValueError(f"Recurrence rule had invalid UNTIL: {rule}")

        if dtstart.date_time:
            if dtstart.date_time.tzinfo and len(until_parts) == 1:
                # UNTIL is a DATE but must be a DATE-TIME
                parts["UNTIL"] = f"{until}T000000Z"
            elif dtstart.date_time.tzinfo is None and until_parts[1].endswith("Z"):
                # Date should be floating
                parts["UNTIL"] = f"{until_parts[0]}T{until_parts[1][:-1]}"
        elif dtstart.date:
            if len(until_parts) > 1:
                # UNTIL is a DATE-TIME but must be a DATE
                parts["UNTIL"] = until_parts[0]

        rule = ";".join(f"{k}={v}" for k, v in parts.items())
        try:
            rrule.rrulestr(rule, dtstart=dtstart.value)
        except ValueError as err:
            raise ValueError(
                f"Invalid recurrence rule {rule} for {dtstart}: {str(err)}"
            ) from err
        return rule

    @property
    def timespan(self) -> Timespan:
        """Return a timespan representing the event start and end."""
        return self.timespan_of(datetime.timezone.utc)

    def timespan_of(self, tzinfo: datetime.tzinfo | None = None) -> Timespan:
        """Return a timespan representing the event start and end."""
        if tzinfo is None:
            tzinfo = datetime.timezone.utc
        return Timespan.of(
            self.start.normalize(tzinfo),
            self.end.normalize(tzinfo),
        )

    def intersects(self, other: "Event") -> bool:
        """Return True if this event overlaps with the other event."""
        return (
            other.start <= self.start < other.end
            or other.start < self.end <= other.end
            or self.start <= other.start < self.end
            or self.start < other.end <= self.end
        )

    def includes(self, other: "Event") -> bool:
        """Return True if the other event starts and ends within this event."""
        return (
            self.start <= other.start < self.end and self.start <= other.end < self.end
        )

    def _tuple(self) -> tuple[datetime.datetime, datetime.datetime]:
        return (self.start.normalize(), self.end.normalize())

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self._tuple() < other._tuple()

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self._tuple() > other._tuple()

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self._tuple() <= other._tuple()

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self._tuple() >= other._tuple()

    class Config:
        """Model configuration."""

        allow_population_by_field_name = True
