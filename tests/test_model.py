"""Tests for the data model."""

import datetime
import json

import pytest
from pydantic import ValidationError

from gcal_sync.model import Calendar, Event


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


def test_event_with_date() -> None:
    """Exercise basic parsing of an event API response."""

    event = Event.parse_obj(
        {
            "kind": "calendar#event",
            "id": "some-event-id",
            "status": "some-status",
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
            "status": "some-status",
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
        "status": "some-status",
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
            "status": "some-status",
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
            "status": "some-status",
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
