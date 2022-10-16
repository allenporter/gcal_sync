"""Tests for the data model."""

from __future__ import annotations

import datetime
import json
import zoneinfo

import pytest
from pydantic import ValidationError

from gcal_sync.model import (
    Attendee,
    Calendar,
    DateOrDatetime,
    Event,
    EventStatusEnum,
    EventTypeEnum,
    ResponseStatus,
    VisibilityEnum,
)

SUMMARY = "test summary"
LOS_ANGELES = zoneinfo.ZoneInfo("America/Los_Angeles")


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
        }
    )
    assert calendar.id == "some-calendar-id"
    assert calendar.summary == "Calendar summary"
    assert calendar.description == "Calendar description"
    assert calendar.location == "Some location"
    assert calendar.timezone is None


def test_calendar_timezone() -> None:
    """Exercise basic parsing of a calendar API response."""

    calendar = Calendar.parse_obj(
        {
            "kind": "calendar#calendarListEntry",
            "id": "some-calendar-id",
            "summary": "Calendar summary",
            "timeZone": "America/Los_Angeles",
        }
    )
    assert calendar.id == "some-calendar-id"
    assert calendar.summary == "Calendar summary"
    assert calendar.description is None
    assert calendar.location is None
    assert calendar.timezone == "America/Los_Angeles"


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

    with pytest.raises(ValidationError):
        Event.parse_obj(
            {
                **base_event,
                "start": {},
            }
        )

    with pytest.raises(ValidationError):
        Event.parse_obj(
            {
                **base_event,
                "start": {"dateTime": "invalid-datetime"},
            }
        )

    with pytest.raises(ValidationError):
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


def test_event_timezone_comparison_zimetone_not_used() -> None:
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
                "dateTime": "2022-05-01T20:00:00Z",
                "timeZone": "Europe/Amsterdam",
            },
            "end": {
                "dateTime": "2022-05-01T21:00:00Z",
                "timeZone": "Europe/Amsterdam",
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

    with pytest.raises(ValidationError):
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
            "attendees": [
                {
                    "id": "attendee-id-1",
                    "email": "example1@example.com",
                    "displayName": "Example 1",
                    "comment": "comment 1",
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
        ),
        Attendee(
            id="attendee-id-2",
            email="example2@example.com",
            displayName="Example 2",
            responseStatus=ResponseStatus.ACCEPTED,
        ),
        Attendee(
            id="attendee-id-3",
            email="example3@example.com",
            displayName="Example 3",
            responseStatus=ResponseStatus.DECLINED,
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
