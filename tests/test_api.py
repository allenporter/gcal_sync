"""Tests for google calendar API library."""

import datetime
from unittest.mock import ANY, Mock, call

from gcal_sync.api import GoogleCalendarService, ListEventsRequest
from gcal_sync.model import Calendar, Datetime, Event

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
                timeMin=ANY,
                timeMax=None,
                q=None,
                maxResults=100,
                pageToken=None,
                singleEvents=True,
                orderBy="startTime",
            )
        ]
    )
    assert result.items == [
        Event(
            id="some-event-id-1",
            summary="Event 1",
            description="Event description 1",
            start=Datetime(date=datetime.date(2022, 4, 13)),
            end=Datetime(date=datetime.date(2022, 4, 14)),
            transparency="transparent",
        ),
        Event(
            id="some-event-id-2",
            summary="Event 2",
            description="Event description 2",
            start=Datetime(date=datetime.date(2022, 4, 14)),
            end=Datetime(date=datetime.date(2022, 4, 20)),
            transparency="opaque",
        ),
    ]
    assert result.page_token is None
    assert result.sync_token is None


async def test_create_event(
    calendar_service: GoogleCalendarService, insert_event: Mock
) -> None:
    """Test create event API."""

    today = datetime.date.today()
    start_date = today + datetime.timedelta(days=1)
    end_date = today + datetime.timedelta(days=2)

    event = Event(
        summary="Summary",
        description="Description",
        start=Datetime(date=start_date),
        end=Datetime(date=end_date),
    )

    await calendar_service.async_create_event("calendar-id", event)
    insert_event.assert_called()
    assert insert_event.mock_calls[0] == call(
        calendarId="calendar-id",
        body={
            "summary": "Summary",
            "description": "Description",
            "start": {"date": start_date},
            "end": {"date": end_date},
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
            start=Datetime(date=datetime.date(2022, 4, 13)),
            end=Datetime(date=datetime.date(2022, 4, 14)),
            transparency="transparent",
        )
    ]
