"""Tests for the data model."""

from __future__ import annotations

import datetime
import json
import zoneinfo
from typing import Any

import pytest

from gcal_sync.model import (
    EVENT_FIELDS,
    ID_DELIM,
    AccessRole,
    Attendee,
    Calendar,
    DateOrDatetime,
    Event,
    EventStatusEnum,
    EventTypeEnum,
    ReminderMethod,
    ReminderOverride,
    ResponseStatus,
    SyntheticEventId,
    VisibilityEnum,
)
from gcal_sync.exceptions import CalendarParseException

SUMMARY = "test summary"
LOS_ANGELES = zoneinfo.ZoneInfo("America/Los_Angeles")
OSLO_TEXT = "Europe/Oslo"
OSLO = zoneinfo.ZoneInfo(OSLO_TEXT)
EXCLUDED_FIELDS = {"recur", "private_calendar_id"}


def test_calendar() -> None:
    """Exercise basic parsing of a calendar API response."""

    calendar = Calendar.parse_obj(
        {
            "kind": "calendar#calendarListEntry",
            "id": "some-calendar-id",
            "summary": "Calendar summary",
            "description": "Calendar description",
            "location": "Some location",
            "hidden": False,
            "accessRole": "owner",
        }
    )
    assert calendar.id == "some-calendar-id"
    assert calendar.summary == "Calendar summary"
    assert calendar.description == "Calendar description"
    assert calendar.location == "Some location"
    assert calendar.timezone is None
    assert calendar.access_role == AccessRole.OWNER


def test_calendar_timezone() -> None:
    """Exercise basic parsing of a calendar API response."""

    calendar = Calendar.parse_obj(
        {
            "kind": "calendar#calendarListEntry",
            "id": "some-calendar-id",
            "summary": "Calendar summary",
            "timeZone": "America/Los_Angeles",
            "accessRole": "reader",
        }
    )
    assert calendar.id == "some-calendar-id"
    assert calendar.summary == "Calendar summary"
    assert calendar.description is None
    assert calendar.location is None
    assert calendar.timezone == "America/Los_Angeles"
    assert calendar.access_role == AccessRole.READER


def test_event_with_date() -> None:
    """Exercise basic parsing of an event API response."""

    event = Event.parse_obj(
        {
            "kind": "calendar#event",
            "id": "some-event-id",
            "status": "confirmed",
            "summary": "Event summary",
            "description": "Event description",
            "location": "Event location",
            "start": {
                "date": "2022-04-12",
            },
            "end": {
                "date": "2022-04-13",
            },
            "transparency": "transparent",
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.description == "Event description"
    assert event.status == EventStatusEnum.CONFIRMED
    assert event.location == "Event location"
    assert event.transparency == "transparent"
    assert event.start
    assert event.start.date == datetime.date(2022, 4, 12)
    assert event.start.date_time is None
    assert event.start.timezone is None
    assert event.start.value == datetime.date(2022, 4, 12)
    assert event.end
    assert event.end.date == datetime.date(2022, 4, 13)
    assert event.end.date_time is None
    assert event.end.timezone is None
    assert event.end.value == datetime.date(2022, 4, 13)
    assert event.timespan.duration == datetime.timedelta(days=1)


def test_event_datetime() -> None:
    """Exercise basic parsing of an event API response."""

    event = Event.parse_obj(
        {
            "kind": "calendar#event",
            "id": "some-event-id",
            "summary": "Event summary",
            "start": {
                "dateTime": "2022-04-12T16:30:00-08:00",
            },
            "end": {
                "dateTime": "2022-04-12T17:00:00-08:00",
            },
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.description is None
    assert event.status == EventStatusEnum.CONFIRMED
    assert event.location is None
    tzinfo = datetime.timezone(datetime.timedelta(hours=-8))

    assert event.start
    assert event.start.date is None
    assert event.start.date_time
    assert event.start.date_time == datetime.datetime(
        2022, 4, 12, 16, 30, 0, tzinfo=tzinfo
    )
    assert event.start.timezone is None
    assert event.start.value == datetime.datetime(2022, 4, 12, 16, 30, 0, tzinfo=tzinfo)

    assert event.end
    assert event.end.date is None
    assert event.end.date_time == datetime.datetime(
        2022, 4, 12, 17, 0, 0, tzinfo=tzinfo
    )
    assert event.end.timezone is None
    assert event.end.value == datetime.datetime(2022, 4, 12, 17, 0, 0, tzinfo=tzinfo)


def test_invalid_datetime() -> None:
    """Test cases with invalid date or datetime fields."""

    base_event = {
        "kind": "calendar#event",
        "id": "some-event-id",
        "summary": "Event summary",
        "end": {
            "dateTime": "2022-04-12T17:00:00-08:00",
        },
    }

    with pytest.raises(CalendarParseException):
        Event.parse_obj(
            {
                **base_event,
                "start": {},
            }
        )

    with pytest.raises(CalendarParseException):
        Event.parse_obj(
            {
                **base_event,
                "start": {"dateTime": "invalid-datetime"},
            }
        )

    with pytest.raises(CalendarParseException):
        Event.parse_obj(
            {
                **base_event,
                "start": {"date": "invalid-datetime"},
            }
        )


def test_event_timezone() -> None:
    """Exercise a datetime with a time zone."""

    event = Event.parse_obj(
        {
            "kind": "calendar#event",
            "id": "some-event-id",
            "summary": "Event summary",
            "start": {
                "dateTime": "2022-04-12T16:30:00",
                "timeZone": "America/Regina",
            },
            "end": {
                "dateTime": "2022-04-12T17:00:00",
                "timeZone": "America/Regina",
            },
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.description is None
    assert event.location is None

    tzinfo = datetime.timezone(datetime.timedelta(hours=-6))

    assert event.start
    assert event.start.date is None
    assert event.start.date_time
    assert event.start.date_time == datetime.datetime(2022, 4, 12, 16, 30, 0)
    assert event.start.timezone == "America/Regina"
    assert event.start.value == datetime.datetime(2022, 4, 12, 16, 30, 0, tzinfo=tzinfo)

    assert event.end
    assert event.end.date is None
    assert event.end.date_time == datetime.datetime(2022, 4, 12, 17, 0, 0)
    assert event.end.timezone == "America/Regina"
    assert event.end.value == datetime.datetime(2022, 4, 12, 17, 0, 0, tzinfo=tzinfo)

    assert json.loads(event.json(exclude_unset=True, by_alias=True)) == {
        "id": "some-event-id",
        "summary": "Event summary",
        "start": {"dateTime": "2022-04-12T16:30:00", "timeZone": "America/Regina"},
        "end": {"dateTime": "2022-04-12T17:00:00", "timeZone": "America/Regina"},
    }


def test_event_utc() -> None:
    """Exercise a datetime in UTC"""

    event = Event.parse_obj(
        {
            "kind": "calendar#event",
            "id": "some-event-id",
            "summary": "Event summary",
            "start": {
                "dateTime": "2022-04-12T16:30:00Z",
            },
            "end": {
                "dateTime": "2022-04-12T17:00:00Z",
            },
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.description is None
    assert event.location is None
    assert event.transparency == "opaque"

    assert event.start
    assert event.start.date is None
    assert event.start.date_time
    assert event.start.date_time == datetime.datetime(
        2022, 4, 12, 16, 30, 0, tzinfo=datetime.timezone.utc
    )
    assert event.start.timezone is None
    assert event.start.value == datetime.datetime(
        2022, 4, 12, 16, 30, 0, tzinfo=datetime.timezone.utc
    )

    assert event.end
    assert event.end.date is None
    assert event.end.date_time == datetime.datetime(
        2022, 4, 12, 17, 0, 0, tzinfo=datetime.timezone.utc
    )
    assert event.start.timezone is None
    assert event.end.timezone is None
    assert event.end.value == datetime.datetime(
        2022, 4, 12, 17, 0, 0, tzinfo=datetime.timezone.utc
    )


@pytest.mark.parametrize(
    ("event_data", "expected_start", "expected_end"),
    [
        (
            {
                "start": {
                    "dateTime": "2025-04-12T00:00:00",
                    "timeZone": OSLO_TEXT,
                },
                "end": {
                    "dateTime": "2025-04-13T00:00:00",
                    "timeZone": OSLO_TEXT,
                },
                "private_calendar_id": "12345@resource.calendar.google.com",
            },
            datetime.date(2025, 4, 12),
            datetime.date(2025, 4, 13),
        ),
        (
            {
                "start": {
                    "dateTime": "2025-04-12T00:00:00",
                    "timeZone": OSLO_TEXT,
                },
                "end": {
                    "dateTime": "2025-04-13T09:30:00",
                    "timeZone": OSLO_TEXT,
                },
                "private_calendar_id": "12345@resource.calendar.google.com",
            },
            datetime.datetime(2025, 4, 12, 0, 0, 0, tzinfo=OSLO),
            datetime.datetime(2025, 4, 13, 9, 30, 0, tzinfo=OSLO),
        ),
        (
            {
                "start": {
                    "dateTime": "2025-04-12T00:00:00",
                    "timeZone": OSLO_TEXT,
                },
                "end": {
                    "dateTime": "2025-04-13T00:00:00",
                    "timeZone": OSLO_TEXT,
                },
            },
            datetime.datetime(2025, 4, 12, 0, 0, 0, tzinfo=OSLO),
            datetime.datetime(2025, 4, 13, 0, 0, 0, tzinfo=OSLO),
        ),
        (
            {
                "start": {
                    "dateTime": "2025-04-12T18:00:00",
                    "timeZone": OSLO_TEXT,
                },
                "end": {
                    "dateTime": "2025-04-13T00:00:00",
                    "timeZone": OSLO_TEXT,
                },
            },
            datetime.datetime(2025, 4, 12, 18, 0, 0, tzinfo=OSLO),
            datetime.datetime(2025, 4, 13, 0, 0, 0, tzinfo=OSLO),
        ),
        (
            {
                "start": {
                    "dateTime": "2025-04-12T09:00:00",
                    "timeZone": OSLO_TEXT,
                },
                "end": {
                    "dateTime": "2025-04-12T18:00:00",
                    "timeZone": OSLO_TEXT,
                },
            },
            datetime.datetime(2025, 4, 12, 9, 0, 0, tzinfo=OSLO),
            datetime.datetime(2025, 4, 12, 18, 0, 0, tzinfo=OSLO),
        ),
    ],
    ids=[
        "resource-all-day-event",
        "resource-event-not-all-day",
        "non-resource-midnight-to-midnight",
        "non-resource-ends-midnight",
        "non-resource-event",
    ],
)
def test_all_day_event_fix_for_resource(
    event_data: dict[str, Any],
    expected_start: datetime.datetime | datetime.date,
    expected_end: datetime.datetime | datetime.date,
) -> None:
    """Test adjusting incorrect resource all day events."""

    event = Event.parse_obj(
        {
            "kind": "calendar#event",
            "id": "some-event-id",
            "summary": "Event summary",
            **event_data,
        }
    )
    assert event.start
    assert event.start.value == expected_start

    assert event.end
    assert event.end.value == expected_end


def test_event_timezone_comparison() -> None:
    """Compare different ways the same time can be returned."""

    event1 = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #1",
            "start": {
                "dateTime": "2022-05-01T13:00:00-07:00",
                "timeZone": "America/Los_Angeles",
            },
            "end": {
                "dateTime": "2022-05-01T13:30:00-07:00",
                "timeZone": "America/Los_Angeles",
            },
        }
    )
    event2 = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #2",
            "start": {
                "dateTime": "2022-05-01T20:00:00Z",
                "timeZone": "UTC",
            },
            "end": {
                "dateTime": "2022-05-01T20:30:00Z",
                "timeZone": "UTC",
            },
        }
    )
    dt1 = event1.start.value
    assert isinstance(dt1, datetime.datetime)
    dt2 = event2.start.value
    assert isinstance(dt2, datetime.datetime)
    assert dt1 == dt2
    assert dt1.astimezone(datetime.timezone.utc) == dt2.astimezone(
        datetime.timezone.utc
    )

    assert event1.intersects(event2)
    assert not event1.includes(event2)


def test_event_timezone_comparison_timetone_not_used() -> None:
    """Compare different ways the same time can be returned."""

    event1 = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #1",
            "start": {
                "dateTime": "2022-05-01T22:00:00+02:00",
                "timeZone": "Europe/Amsterdam",
            },
            "end": {
                "dateTime": "2022-05-01T23:00:00+02:00",
                "timeZone": "Europe/Amsterdam",
            },
        }
    )
    event2 = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #2",
            "start": {
                # Ambiguous given utc plus timezone
                "dateTime": "2022-05-01T20:00:00Z",
                "timeZone": "Europe/Amsterdam",
            },
            "end": {
                "dateTime": "2022-05-01T21:00:00Z",
                "timeZone": "Europe/Amsterdam",
            },
            "accessRole": "reader",
        }
    )
    dt1 = event1.start.value
    assert isinstance(dt1, datetime.datetime)
    dt2 = event2.start.value
    assert isinstance(dt2, datetime.datetime)
    assert dt1 == dt2
    assert dt1.astimezone(datetime.timezone.utc) == dt2.astimezone(
        datetime.timezone.utc
    )
    assert event1.start.value.isoformat() == "2022-05-01T22:00:00+02:00"
    assert event2.start.value.isoformat() == "2022-05-01T22:00:00+02:00"


def test_event_cancelled() -> None:
    """Exercise basic parsing of an event API response."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "status": "cancelled",
        }
    )
    assert event.id == "some-event-id"
    assert not event.summary
    assert event.description is None
    assert event.location is None
    assert event.status == EventStatusEnum.CANCELLED


def test_required_fields() -> None:
    """Exercise required fields for normal non-deleted events."""

    with pytest.raises(CalendarParseException):
        Event.parse_obj(
            {
                "id": "some-event-id",
                "status": "confirmed",
            }
        )


@pytest.mark.parametrize(
    "api_event_type,event_type",
    [
        ("default", EventTypeEnum.DEFAULT),
        ("focusTime", EventTypeEnum.FOCUS_TIME),
        ("outOfOffice", EventTypeEnum.OUT_OF_OFFICE),
        ("workingLocation", EventTypeEnum.WORKING_LOCATION),
        ("fromGmail", EventTypeEnum.FROM_GMAIL),
        ("birthday", EventTypeEnum.BIRTHDAY),
        ("some-event-type", EventTypeEnum.UNKNOWN),
    ],
)
def test_event_type(api_event_type: str, event_type: EventTypeEnum) -> None:
    """Exercise basic parsing of an event API response."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "eventType": api_event_type,
            "summary": "Event summary",
            "start": {
                "date": "2022-04-12",
            },
            "end": {
                "date": "2022-04-13",
            },
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.event_type == event_type


@pytest.mark.parametrize(
    "api_visibility,visibility",
    [
        ("default", VisibilityEnum.DEFAULT),
        ("public", VisibilityEnum.PUBLIC),
        ("private", VisibilityEnum.PRIVATE),
        ("confidential", VisibilityEnum.PRIVATE),
    ],
)
def test_visibility_enum(api_visibility: str, visibility: VisibilityEnum) -> None:
    """Exercise basic parsing of an event API response."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "visibility": api_visibility,
            "summary": "Event summary",
            "start": {
                "date": "2022-04-12",
            },
            "end": {
                "date": "2022-04-13",
            },
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.visibility == visibility


def test_attendees() -> None:
    """Test event attendees."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event summary",
            "start": {
                "date": "2022-04-12",
            },
            "end": {
                "date": "2022-04-13",
            },
            "creator": {
                "id": "creator-1",
                "email": "example0@example.com",
                "displayName": "Example 0",
                "self": "False",
            },
            "attendees": [
                {
                    "id": "attendee-id-1",
                    "email": "example1@example.com",
                    "displayName": "Example 1",
                    "comment": "comment 1",
                    "self": True,
                },
                {
                    "id": "attendee-id-2",
                    "email": "example2@example.com",
                    "displayName": "Example 2",
                    "responseStatus": "accepted",
                },
                {
                    "id": "attendee-id-3",
                    "email": "example3@example.com",
                    "displayName": "Example 3",
                    "responseStatus": "declined",
                },
            ],
        }
    )
    assert event.attendees == [
        Attendee(
            id="attendee-id-1",
            email="example1@example.com",
            displayName="Example 1",
            comment="comment 1",
            responseStatus=ResponseStatus.NEEDS_ACTION,
            is_self=True,
        ),
        Attendee(
            id="attendee-id-2",
            email="example2@example.com",
            displayName="Example 2",
            responseStatus=ResponseStatus.ACCEPTED,
            is_self=False,
        ),
        Attendee(
            id="attendee-id-3",
            email="example3@example.com",
            displayName="Example 3",
            responseStatus=ResponseStatus.DECLINED,
            is_self=False,
        ),
    ]


def test_recurring_event() -> None:
    """Test fields set for a recurring event."""

    event = Event.parse_obj(
        {
            "id": "a0033414ffas_20221012",
            "summary": "Event summary",
            "start": {
                "date": "2022-10-12",
            },
            "end": {
                "date": "2022-10-13",
            },
            "recurringEventId": "a0033414ffas",
            "originalStartTime": {"date": "2022-10-12"},
            "iCalUID": "a0033414ffas@google.com",
        }
    )
    assert event.id == "a0033414ffas_20221012"
    assert event.summary == "Event summary"
    assert event.recurring_event_id == "a0033414ffas"
    assert event.original_start_time
    assert event.original_start_time.date == datetime.date(2022, 10, 12)
    assert event.ical_uuid == "a0033414ffas@google.com"


@pytest.mark.parametrize(
    "event1_start,event1_end,event2_start,event2_end",
    [
        (
            datetime.date(2022, 9, 6),
            datetime.date(2022, 9, 7),
            datetime.date(2022, 9, 8),
            datetime.date(2022, 9, 10),
        ),
        (
            datetime.datetime(2022, 9, 6, 6, 0, 0),
            datetime.datetime(2022, 9, 6, 7, 0, 0),
            datetime.datetime(2022, 9, 6, 8, 0, 0),
            datetime.datetime(2022, 9, 6, 8, 30, 0),
        ),
        (
            datetime.datetime(2022, 9, 6, 6, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2022, 9, 6, 7, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2022, 9, 6, 8, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2022, 9, 6, 8, 30, 0, tzinfo=datetime.timezone.utc),
        ),
        (
            datetime.datetime(2022, 9, 6, 6, 0, 0, tzinfo=LOS_ANGELES),
            datetime.datetime(2022, 9, 6, 7, 0, 0, tzinfo=LOS_ANGELES),
            datetime.datetime(2022, 9, 7, 8, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2022, 9, 7, 8, 30, 0, tzinfo=datetime.timezone.utc),
        ),
        (
            datetime.datetime(2022, 9, 6, 6, 0, 0, tzinfo=LOS_ANGELES),
            datetime.datetime(2022, 9, 6, 7, 0, 0, tzinfo=LOS_ANGELES),
            datetime.datetime(2022, 9, 8, 8, 0, 0),
            datetime.datetime(2022, 9, 8, 8, 30, 0),
        ),
        (
            datetime.datetime(2022, 9, 6, 6, 0, 0, tzinfo=LOS_ANGELES),
            datetime.datetime(2022, 9, 6, 7, 0, 0, tzinfo=LOS_ANGELES),
            datetime.date(2022, 9, 8),
            datetime.date(2022, 9, 9),
        ),
        (
            datetime.date(2022, 9, 6),
            datetime.date(2022, 9, 7),
            datetime.datetime(2022, 9, 6, 8, 0, 0, tzinfo=datetime.timezone.utc),
            datetime.datetime(2022, 9, 6, 8, 30, 0, tzinfo=datetime.timezone.utc),
        ),
    ],
)
def test_comparisons(
    event1_start: datetime.datetime | datetime.date,
    event1_end: datetime.datetime | datetime.date,
    event2_start: datetime.datetime | datetime.date,
    event2_end: datetime.datetime | datetime.date,
) -> None:
    """Test event comparison methods."""
    event1 = Event(
        summary=SUMMARY,
        start=DateOrDatetime.parse(event1_start),
        end=DateOrDatetime.parse(event1_end),
    )
    event2 = Event(
        summary=SUMMARY,
        start=DateOrDatetime.parse(event2_start),
        end=DateOrDatetime.parse(event2_end),
    )
    assert event1 < event2
    assert event1 <= event2
    assert event2 >= event1
    assert event2 > event1

    assert event1 <= event2
    assert event2 >= event1
    assert event2 > event1


def test_invalid_rrule_until_format() -> None:
    """Test invalid RRULE parsing."""
    with pytest.raises(
        CalendarParseException, match=r"Recurrence rule had unexpected format.*"
    ):
        Event.parse_obj(
            {
                "summary": "Summary",
                "start": {"date_time": "2012-11-27T18:00:00"},
                "end": {"date_time": "2012-11-27T19:00:00"},
                "recurrence": ["RRULE:FREQ=WEEKLY;UNTIL;BYDAY=TU"],
            }
        )


def test_invalid_rrule_content_lines() -> None:
    """Test invalid RRULE parsing."""
    with pytest.raises(
        CalendarParseException,
        match=r"Failed to parse calendar EVENT component: Failed to parse recurrence",
    ):
        Event.parse_obj(
            {
                "summary": "Summary",
                "start": {"date_time": "2012-11-27T18:00:00"},
                "end": {"date_time": "2012-11-27T19:00:00"},
                "recurrence": ["RRULE;"],
            }
        )


def test_invalid_rrule_until_time() -> None:
    """Test invalid RRULE parsing."""
    with pytest.raises(
        CalendarParseException, match=r"Expected value to match DATE pattern.*"
    ):
        Event.parse_obj(
            {
                "summary": "Summary",
                "start": {"date_time": "2012-11-27T18:00:00"},
                "end": {"date_time": "2012-11-27T19:00:00"},
                "recurrence": ["RRULE:FREQ=WEEKLY;UNTIL=20220202T1234T;BYDAY=TU"],
            }
        )


def test_event_fields_mask() -> None:
    """Test that all fields in the pydantic model are specified in the field mask."""

    assert EVENT_FIELDS == ",".join(
        [
            field.alias
            for field in Event.__fields__.values()
            if field.alias not in EXCLUDED_FIELDS
        ]
    )


def test_event_recurrence_id_all_day() -> None:
    """Test creating a recurrence id for an all day event."""
    syn_id = SyntheticEventId("event-id", datetime.date(2022, 10, 2))
    assert syn_id.original_event_id == "event-id"
    assert syn_id.dtstart == datetime.date(2022, 10, 2)
    assert syn_id.event_id == SyntheticEventId.parse(syn_id.event_id).event_id


def test_event_recurrence_id_utc() -> None:
    """Test creating a recurrence id for an event in UTC."""
    syn_id = SyntheticEventId(
        "event-id",
        datetime.datetime(2022, 10, 2, 5, 32, 00, tzinfo=datetime.timezone.utc),
    )
    assert syn_id.original_event_id == "event-id"
    assert syn_id.dtstart == datetime.datetime(
        2022, 10, 2, 5, 32, 00, tzinfo=datetime.timezone.utc
    )
    assert syn_id.event_id == SyntheticEventId.parse(syn_id.event_id).event_id


def test_event_recurrence_id_tzinfo() -> None:
    """Test creating a recurrence id for an event with a specific timezone"""
    syn_id = SyntheticEventId(
        "event-id",
        datetime.datetime(
            2022, 10, 2, 5, 32, 00, tzinfo=zoneinfo.ZoneInfo("America/Regina")
        ),
    )
    assert syn_id.original_event_id == "event-id"
    assert syn_id.dtstart == datetime.datetime(
        2022, 10, 2, 5, 32, 00, tzinfo=zoneinfo.ZoneInfo("America/Regina")
    )
    assert syn_id.event_id == SyntheticEventId.parse(syn_id.event_id).event_id


def test_parse_event_missing_sentinal() -> None:
    """Validate an event id that is not recurring."""
    assert not SyntheticEventId.is_valid("event-id")


@pytest.mark.parametrize(
    "event_id",
    [
        f"event_id{ID_DELIM}",
        f"event-id{ID_DELIM}2022100",
        f"event_id{ID_DELIM}20221002T053200",
        f"event-id{ID_DELIM}20221002T053200Y",
        f"event_id{ID_DELIM}20221002053200",
        f"event_id{ID_DELIM}202q1002",
        f"event-id{ID_DELIM}20221002T05q200Z",
    ],
)
def test_invalid_event_id(event_id: str) -> None:
    """Test invalid event id values."""
    with pytest.raises(ValueError):
        SyntheticEventId.parse(event_id)


@pytest.mark.parametrize(
    "access_role,writer",
    [
        (AccessRole.FREE_BUSY_READER, False),
        (AccessRole.READER, False),
        (AccessRole.WRITER, True),
        (AccessRole.OWNER, True),
    ],
)
def test_access_role_writer(access_role: AccessRole, writer: bool) -> None:
    """Test that access roles are writers."""
    assert access_role.is_writer == writer


def test_event_timezone_with_offset() -> None:
    """Verify the time parsing for a timezone and a date time with an offset."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #1",
            "start": {
                "dateTime": "2022-11-24T19:45:00+01:00",
                "timeZone": "Europe/Rome",
            },
            "end": {
                "dateTime": "2022-11-24T20:00:00+01:00",
                "timeZone": "Europe/Rome",
            },
        }
    )
    assert event.start.date is None
    assert event.start.date_time == datetime.datetime(
        2022, 11, 24, 19, 45, tzinfo=zoneinfo.ZoneInfo("Europe/Rome")
    )
    assert event.start.value == datetime.datetime(
        2022, 11, 24, 19, 45, tzinfo=zoneinfo.ZoneInfo("Europe/Rome")
    )
    assert event.start.value.isoformat() == "2022-11-24T19:45:00+01:00"


def test_invalid_all_day_event_duration() -> None:
    """Verify that all day events with invalid durations are fixed."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #1",
            "start": {
                "date": "2022-11-24",
            },
            "end": {
                "date": "2022-11-24",  # Invalid end date
            },
        }
    )
    assert event.timespan.duration == datetime.timedelta(days=1)
    assert event.start.date == datetime.date(2022, 11, 24)
    assert event.start.value.isoformat() == "2022-11-24"
    assert event.end.date == datetime.date(2022, 11, 25)
    assert event.end.value.isoformat() == "2022-11-25"


def test_invalid_event_duration() -> None:
    """Verify that all day events with invalid durations are fixed."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event #1",
            "start": {
                "dateTime": "2022-04-12T16:30:00-08:00",
            },
            "end": {
                "dateTime": "2022-04-12T16:30:00-08:00",  # Invalid end date
            },
        }
    )
    assert event.id == "some-event-id"
    tzinfo = datetime.timezone(datetime.timedelta(hours=-8))

    assert event.start
    assert event.start.date is None
    assert event.start.date_time
    assert event.start.date_time == datetime.datetime(
        2022, 4, 12, 16, 30, 0, tzinfo=tzinfo
    )
    assert event.start.timezone is None
    assert event.start.value == datetime.datetime(2022, 4, 12, 16, 30, 0, tzinfo=tzinfo)

    assert event.end
    assert event.end.date is None
    assert event.end.date_time == datetime.datetime(
        2022, 4, 12, 17, 0, 0, tzinfo=tzinfo
    )
    assert event.end.timezone is None
    assert event.end.value == datetime.datetime(2022, 4, 12, 17, 0, 0, tzinfo=tzinfo)

    assert event.timespan.duration == datetime.timedelta(minutes=30)


def test_reminders() -> None:
    """Test event reminders."""

    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Event summary",
            "start": {
                "date": "2022-04-12",
            },
            "end": {
                "date": "2022-04-13",
            },
            "reminders": {
                "useDefault": True,
                "overrides": [
                    {
                        "method": "email",
                        "minutes": 5,
                    },
                    {
                        "method": "popup",
                        "minutes": 3,
                    },
                ],
            },
        }
    )
    assert event.reminders
    assert event.reminders.use_default
    assert event.reminders.overrides == [
        ReminderOverride(
            method=ReminderMethod.EMAIL,
            minutes=5,
        ),
        ReminderOverride(
            method=ReminderMethod.POPUP,
            minutes=3,
        ),
    ]
