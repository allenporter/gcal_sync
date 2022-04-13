"""Tests for the data model."""

import datetime

from google_calendar_sync.model import Calendar, Event


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
        }
    )
    assert event.id == "some-event-id"
    assert event.summary == "Event summary"
    assert event.description == "Event description"
    assert event.location == "Event location"
    assert event.start == datetime.date(2022, 4, 12)
    assert event.end == datetime.date(2022, 4, 13)


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
    tz = datetime.timezone(datetime.timedelta(hours=-8))
    assert isinstance(event.start, datetime.datetime)
    assert event.start == datetime.datetime(2022, 4, 12, 16, 30, 0, tzinfo=tz)
    assert isinstance(event.end, datetime.datetime)
    assert event.end == datetime.datetime(2022, 4, 12, 17, 0, 0, tzinfo=tz)
