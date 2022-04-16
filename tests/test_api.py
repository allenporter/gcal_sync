"""Tests for google calendar API library."""

import datetime
from unittest.mock import ANY, Mock, call

from freezegun import freeze_time
from gcal_sync.api import GoogleCalendarService, ListEventsRequest
from gcal_sync.model import Calendar, DateOrDatetime, Event

from .conftest import ApiResult


async def test_list_calendars(
    calendar_service: GoogleCalendarService, calendars_list: ApiResult
) -> None:
    """Test list calendars API."""

    calendars_list(
        {
            "items": [
                {
                    "id": "calendar-id-1",
                    "summary": "Calendar 1",
                },
                {
                    "id": "calendar-id-2",
                    "summary": "Calendar 2",
                },
            ]
        }
    )

    result = await calendar_service.async_list_calendars()
    assert result.items == [
        Calendar(id="calendar-id-1", summary="Calendar 1"),
        Calendar(id="calendar-id-2", summary="Calendar 2"),
    ]


async def test_list_calendars_empty_reply(
    calendar_service: GoogleCalendarService, calendars_list: ApiResult
) -> None:
    """Test list calendars API."""

    calendars_list({})

    result = await calendar_service.async_list_calendars()
    assert result.items == []


@freeze_time("2022-04-30 07:31:02", tz_offset=-6)
async def test_list_events(
    calendar_service: GoogleCalendarService,
    events_list: Mock,
) -> None:
    """Test list calendars API."""

    events_list.return_value.execute.return_value = {
        "items": [
            {
                "id": "some-event-id-1",
                "summary": "Event 1",
                "description": "Event description 1",
                "start": {
                    "date": "2022-04-13",
                },
                "end": {
                    "date": "2022-04-14",
                },
                "status": "confirmed",
                "transparency": "transparent",
            },
            {
                "id": "some-event-id-2",
                "summary": "Event 2",
                "description": "Event description 2",
                "start": {
                    "date": "2022-04-14",
                },
                "end": {
                    "date": "2022-04-20",
                },
                "transparency": "opaque",
            },
        ]
    }
    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id")
    )
    events_list.assert_called()
    calls = events_list.mock_calls
    assert len(calls) == 2  # API call and execute call
    events_list.assert_has_calls(
        [
            call(
                calendarId="some-calendar-id",
                timeMin="2022-04-30T01:31:02+00:00",
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
                fields=ANY,
            )
        ]
    )
    assert result.items == [
        Event(
            id="some-event-id-1",
            summary="Event 1",
            description="Event description 1",
            start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
            transparency="transparent",
        ),
        Event(
            id="some-event-id-2",
            summary="Event 2",
            description="Event description 2",
            start=DateOrDatetime(date=datetime.date(2022, 4, 14)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 20)),
            transparency="opaque",
        ),
    ]
    assert result.page_token is None
    assert result.sync_token is None


async def test_list_events_with_date_limit(
    calendar_service: GoogleCalendarService,
    events_list: Mock,
) -> None:
    """Test list calendars API with start/end datetimes."""

    # Test doesn't care about response
    events_list.return_value.execute.return_value = {"items": []}

    tzinfo = datetime.timezone(datetime.timedelta(hours=-6), "America/Regina")
    start = datetime.datetime(2022, 4, 13, 7, 30, 12, 345678, tzinfo)
    end = datetime.datetime(2022, 4, 13, 9, 30, 12, 345678, tzinfo)

    await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id", start_time=start, end_time=end),
    )
    events_list.assert_called()
    calls = events_list.mock_calls
    assert len(calls) == 2  # API call and execute call
    events_list.assert_has_calls(
        [
            call(
                calendarId="some-calendar-id",
                timeMin="2022-04-13T07:30:12-06:00",
                timeMax="2022-04-13T09:30:12-06:00",
                maxResults=100,
                singleEvents=True,
                orderBy="startTime",
                fields=ANY,
            )
        ]
    )


async def test_create_event_with_date(
    calendar_service: GoogleCalendarService, insert_event: Mock
) -> None:
    """Test create event API."""

    start_date = datetime.date(2022, 4, 15)
    end_date = start_date + datetime.timedelta(days=2)

    event = Event(
        summary="Summary",
        description="Description",
        start=DateOrDatetime(date=start_date),
        end=DateOrDatetime(date=end_date),
    )

    await calendar_service.async_create_event("calendar-id", event)
    insert_event.assert_called()
    assert insert_event.mock_calls[0] == call(
        calendarId="calendar-id",
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {"date": "2022-04-15"},
            "end": {"date": "2022-04-17"},
        },
    )


async def test_create_event_with_datetime(
    calendar_service: GoogleCalendarService, insert_event: Mock
) -> None:
    """Test create event API with date times."""

    start = datetime.datetime(2022, 4, 15, 7, 30, 12, 12345)
    end = start + datetime.timedelta(hours=2)

    event = Event(
        summary="Summary",
        description="Description",
        start=DateOrDatetime(date_time=start),
        end=DateOrDatetime(date_time=end),
    )

    await calendar_service.async_create_event("calendar-id", event)
    insert_event.assert_called()
    assert insert_event.mock_calls[0] == call(
        calendarId="calendar-id",
        body={
            "summary": "Summary",
            "description": "Description",
            # micros are stripped
            "start": {"dateTime": "2022-04-15T07:30:12"},
            "end": {"dateTime": "2022-04-15T09:30:12"},
        },
    )


async def test_create_event_with_timezone(
    calendar_service: GoogleCalendarService, insert_event: Mock
) -> None:
    """Test create event API with date times."""

    start = datetime.datetime(
        2022,
        4,
        15,
        7,
        30,
        tzinfo=datetime.timezone(datetime.timedelta(hours=-6), "America/Regina"),
    )
    end = start + datetime.timedelta(hours=2)

    event = Event(
        summary="Summary",
        description="Description",
        start=DateOrDatetime(date_time=start),
        end=DateOrDatetime(date_time=end),
    )

    await calendar_service.async_create_event("calendar-id", event)
    insert_event.assert_called()
    assert insert_event.mock_calls[0] == call(
        calendarId="calendar-id",
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {"dateTime": "2022-04-15T07:30:00-06:00"},
            "end": {"dateTime": "2022-04-15T09:30:00-06:00"},
        },
    )


async def test_event_missing_summary(
    calendar_service: GoogleCalendarService,
    events_list: Mock,
) -> None:
    """Test list calendars API."""

    events_list.return_value.execute.return_value = {
        "items": [
            {
                "id": "some-event-id-1",
                "description": "Event description 1",
                "start": {
                    "date": "2022-04-13",
                },
                "end": {
                    "date": "2022-04-14",
                },
                "status": "confirmed",
                "transparency": "transparent",
            },
        ]
    }

    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id")
    )
    assert result.items == [
        Event(
            id="some-event-id-1",
            summary="",
            description="Event description 1",
            start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
            transparency="transparent",
        )
    ]


async def test_list_events_page_token(
    calendar_service: GoogleCalendarService,
    events_list: Mock,
) -> None:
    """Test list calendars API."""

    events_list.return_value.execute.return_value = {
        "nextPageToken": "some-token",
        "items": [
            {
                "id": "some-event-id-1",
                "summary": "Event 1",
                "description": "Event description 1",
                "start": {
                    "date": "2022-04-13",
                },
                "end": {
                    "date": "2022-04-14",
                },
                "status": "confirmed",
                "transparency": "transparent",
            },
        ]
    }
    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id")
    )
    assert result.page_token == "some-token"
