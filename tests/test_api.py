"""Tests for google calendar API library."""

import datetime
from collections.abc import Awaitable, Callable

from freezegun import freeze_time

from gcal_sync.api import GoogleCalendarService, ListEventsRequest
from gcal_sync.model import Calendar, DateOrDatetime, Event

from .conftest import ApiRequest, ApiResult


async def test_list_calendars(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
) -> None:
    """Test list calendars API."""

    json_response(
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
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_calendars()
    assert result.items == [
        Calendar(id="calendar-id-1", summary="Calendar 1"),
        Calendar(id="calendar-id-2", summary="Calendar 2"),
    ]


async def test_list_calendars_empty_reply(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
) -> None:
    """Test list calendars API."""

    json_response({})

    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_calendars()
    assert result.items == []


@freeze_time("2022-04-30 07:31:02", tz_offset=-6)
async def test_list_events(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test list calendars API."""

    json_response(
        {
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
    )
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id")
    )
    assert url_request() == [
        "/calendars/some-calendar-id/events?maxResult=100&singleEvents=true&orderBy=startTime"
        "&fields=kind,nextPageToken,nextSyncToken,items(id,summary,description,location,start"
        ",end,transparency)&timeMin=2022-04-30T01:31:02%2B00:00"
    ]
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
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test list calendars API with start/end datetimes."""

    # Test doesn't care about response
    json_response({"items": []})

    tzinfo = datetime.timezone(datetime.timedelta(hours=-6), "America/Regina")
    start = datetime.datetime(2022, 4, 13, 7, 30, 12, 345678, tzinfo)
    end = datetime.datetime(2022, 4, 13, 9, 30, 12, 345678, tzinfo)

    calendar_service = await calendar_service_cb()
    await calendar_service.async_list_events(
        ListEventsRequest(
            calendar_id="some-calendar-id", start_time=start, end_time=end
        ),
    )
    assert url_request() == [
        "/calendars/some-calendar-id/events?maxResult=100&singleEvents=true&orderBy=startTime"
        "&fields=kind,nextPageToken,nextSyncToken,items(id,summary,description,location,start,"
        "end,transparency)&timeMin=2022-04-13T07:30:12-06:00&timeMax=2022-04-13T09:30:12-06:00"
    ]


async def test_create_event_with_date(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_request: ApiRequest,
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

    calendar_service = await calendar_service_cb()
    await calendar_service.async_create_event("calendar-id", event)
    assert json_request() == [
        {
            "summary": "Summary",
            "description": "Description",
            "start": {"date": "2022-04-15"},
            "end": {"date": "2022-04-17"},
        }
    ]


async def test_create_event_with_datetime(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_request: ApiRequest,
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

    calendar_service = await calendar_service_cb()
    await calendar_service.async_create_event("calendar-id", event)
    assert json_request() == [
        {
            "summary": "Summary",
            "description": "Description",
            # micros are stripped
            "start": {"dateTime": "2022-04-15T07:30:12"},
            "end": {"dateTime": "2022-04-15T09:30:12"},
        }
    ]


async def test_create_event_with_timezone(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_request: ApiRequest,
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

    calendar_service = await calendar_service_cb()
    await calendar_service.async_create_event("calendar-id", event)
    assert json_request() == [
        {
            "summary": "Summary",
            "description": "Description",
            "start": {"dateTime": "2022-04-15T07:30:00-06:00"},
            "end": {"dateTime": "2022-04-15T09:30:00-06:00"},
        }
    ]


async def test_event_missing_summary(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
) -> None:
    """Test list calendars API."""

    json_response(
        {
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
    )

    calendar_service = await calendar_service_cb()
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
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
) -> None:
    """Test list calendars API."""

    json_response(
        {
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
            ],
        }
    )
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id")
    )
    assert result.page_token == "some-token"
