"""Library for data model for local calendar objects.

This librayr contains [pydantic](https://pydantic-docs.helpmanual.io/) models
for the Google Calendar API data model. These objects support all methods for
parsing and serialization supported by pydnatic.
"""

from __future__ import annotations

import datetime
import logging
import zoneinfo
from enum import Enum
from typing import Any, Optional, Union

from dateutil import rrule
from ical.timespan import Timespan
from pydantic import BaseModel, Field, root_validator, validator

__all__ = [
    "Calendar",
    "Event",
    "DateOrDatetime",
    "EventStatusEnum",
    "EventTypeEnum",
    "VisibilityEnum",
    "ResponseStatus",
    "Attendee",
]

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
    """Identifier of the calendar."""

    summary: str = ""
    """Title of the calendar."""

    description: Optional[str]
    """Description of the calendar."""

    location: Optional[str]
    """Geographic location of the calendar as free-form text."""

    timezone: Optional[str] = Field(alias="timeZone", default=None)
    """The time zone of the calendar."""


class DateOrDatetime(BaseModel):
    """A date or datetime."""

    date: Optional[datetime.date] = Field(default=None)
    """The date, in the format "yyyy-mm-dd", if this is an all-day event."""

    date_time: Optional[datetime.datetime] = Field(alias="dateTime", default=None)
    """The time, as a combined date-time value."""

    # Note: timezone is only used for creating new events
    timezone: Optional[str] = Field(alias="timeZone", default=None)
    """The time zone in which the time is specified."""

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

    @root_validator
    def _check_date_or_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
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
    """The event is confirmed."""

    TENTATIVE = "tentative"
    """The event is tentatively confirmed."""

    CANCELLED = "cancelled"
    """The event is cancelled (deleted)."""


class EventTypeEnum(str, Enum):
    """Type of the event."""

    DEFAULT = "default"
    """A regular event or not further specified."""

    OUT_OF_OFFICE = "outOfOffice"
    """An out-of-office event."""

    FOCUS_TIME = "focusTime"
    """A focus-time event."""


class VisibilityEnum(str, Enum):
    """Visibility of the event."""

    DEFAULT = "default"
    """Uses the default visibility for events on the calendar."""

    PUBLIC = "public"
    """The event is public and event details are visible to all readers of the calendar."""

    PRIVATE = "private"  # Same as confidential
    """The event is private and only event attendees may view event details."""


class ResponseStatus(str, Enum):
    """The attendee's response status."""

    NEEDS_ACTION = "needsAction"
    """The attendee has not responded to the invitation (recommended for new events)."""

    DECLINED = "declined"
    """The attendee has declined the invitation."""

    TENTATIVE = "tentative"
    """The attendee has tentatively accepted the invitation."""

    ACCEPTED = "accepted"
    """The attendee has accepted the invitation."""


class Attendee(BaseModel):
    """An attendee of an event."""

    id: Optional[str] = None
    """The attendee's Profile ID, if available."""

    email: str = ""
    """The attendee's email address, if available."""

    display_name: Optional[str] = Field(alias="displayName", default=None)
    """The attendee's name, if available."""

    optional: bool = False
    """Whether this is an optional attendee."""

    comment: Optional[str] = None
    """The attendee's response comment."""

    response_status: ResponseStatus = Field(
        alias="responseStatus", default=ResponseStatus.NEEDS_ACTION
    )
    """The attendee's response status."""


class Event(BaseModel):
    """A single event on a calendar."""

    id: Optional[str] = None
    """Opaque identifier of the event."""

    ical_uuid: Optional[str] = Field(alias="iCalUID", default=None)
    """Event unique identifier as defined in RFC5545."""

    summary: str = ""
    """Title of the event."""

    start: DateOrDatetime
    """The (inclusive) start time of the event."""

    end: DateOrDatetime
    """The (exclusive) end time of the event."""

    description: Optional[str]
    """Description of the event, which can contain HTML."""

    location: Optional[str]
    """Geographic location of the event as free-form text."""

    transparency: str = Field(default="opaque")
    """Whether the event blocks time on the calendar.

    Will either be `opaque` which means the calendar does block time on the
    calendar or `transparent` which means it does not block time on the calendar.
    """

    # Note deleted events are only returned in some scenarios based on request options
    # such as enabling incremental sync or explicitly asking for deleted items. That is,
    # most users should not need to check the status.
    status: EventStatusEnum = EventStatusEnum.CONFIRMED
    """Status of the event."""

    event_type: EventTypeEnum = Field(alias="eventType", default=EventTypeEnum.DEFAULT)
    """Specific type of the event."""

    visibility: VisibilityEnum = VisibilityEnum.DEFAULT
    """Visibility of the event."""

    attendees: list[Attendee] = []
    """The attendees of the event."""

    attendees_omitted: bool = Field(alias="attendeesOmitted", default=False)
    """Whether attendees may have been omitted from the event's representation."""

    recurrence: list[str] = []
    """List of RRULE, EXRULE, RDATE and EXDATE lines for a recurring event.

    See RFC5545 for more details."""

    recurring_event_id: Optional[str] = Field(alias="recurringEventId", default=None)
    """The id of the primary even to which this recurring event belongs."""

    original_start_time: Optional[DateOrDatetime] = Field(
        alias="originalStartTime", default=None
    )
    """A unique identifier for when this event would start in the original recurring event."""

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
    def _allow_cancelled_events(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Special case for canceled event tombstones that are missing required fields."""
        if status := values.get("status"):
            if status == EventStatusEnum.CANCELLED:
                if "start" not in values:
                    values["start"] = DateOrDatetime(date=datetime.date.min)
                if "end" not in values:
                    values["end"] = DateOrDatetime(date=datetime.date.min)
        return values

    @root_validator(pre=True)
    def _adjust_visibility(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Convert legacy visibility types to new types."""
        if visibility := values.get("visibility"):
            if visibility == "confidential":
                values["visibility"] = "private"
        return values

    @validator("recurrence", each_item=True)
    def _validate_rrule_params(cls, rule: str) -> str:
        """Remove rrule property parameters not supported by the dateutil.rrule library."""
        if not rule.startswith("RRULE;"):
            return rule
        right = rule[6:]
        parts = right.split(":", maxsplit=1)
        if len(parts) == 2:
            # Rebuild string without parameters
            return f"RRULE:{parts[1]}"
        return rule  # rrule parser fail

    @root_validator
    def _validate_rrule(cls, values: dict[str, Any]) -> dict[str, Any]:
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
        return self.timespan.intersects(other.timespan)

    def includes(self, other: "Event") -> bool:
        """Return True if the other event starts and ends within this event."""
        return self.timespan.includes(other.timespan)

    def __lt__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.timespan < other.timespan

    def __gt__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.timespan > other.timespan

    def __le__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.timespan <= other.timespan

    def __ge__(self, other: Any) -> bool:
        if not isinstance(other, Event):
            return NotImplemented
        return self.timespan >= other.timespan

    class Config:
        """Model configuration."""

        allow_population_by_field_name = True
