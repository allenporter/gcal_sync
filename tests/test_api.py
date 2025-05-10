"""Tests for google calendar API library."""

import datetime
from collections.abc import Awaitable, Callable

import pytest
from freezegun import freeze_time

from gcal_sync.api import (
    GoogleCalendarService,
    ListEventsRequest,
    LocalListEventsRequest,
    Range,
)
from gcal_sync.model import (
    EVENT_FIELDS,
    AccessRole,
    Calendar,
    CalendarBasic,
    DateOrDatetime,
    Event,
    ReminderMethod,
    ReminderOverride,
    Reminders,
)
from gcal_sync.sync import CalendarEventSyncManager

from .conftest import ApiRequest, ApiResult

EVENT_LIST_PARAMS = (
    "maxResults=1000&singleEvents=true&orderBy=startTime"
    f"&fields=kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"
)
EVENT_SYNC_PARAMS = (
    f"maxResults=1000&fields=kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"
)


async def test_get_calendar(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test list calendars API."""

    json_response(
        {
            "id": "calendar-id-1",
            "summary": "Calendar 1",
        },
    )
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_get_calendar("primary")
    assert result == CalendarBasic(
        id="calendar-id-1",
        summary="Calendar 1",
    )

    assert url_request() == ["/calendars/primary"]


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
                    "accessRole": "reader",
                },
                {
                    "id": "calendar-id-2",
                    "summary": "Calendar 2",
                    "accessRole": "owner",
                },
            ]
        }
    )
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_calendars()
    assert result.items == [
        Calendar(
            id="calendar-id-1", summary="Calendar 1", access_role=AccessRole.READER
        ),
        Calendar(
            id="calendar-id-2", summary="Calendar 2", access_role=AccessRole.OWNER
        ),
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


async def test_get_event(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test getting a single calendar event."""

    json_response(
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
        }
    )
    calendar_service = await calendar_service_cb()
    event = await calendar_service.async_get_event(
        "some-calendar-id", "some-event-id-1"
    )
    assert url_request() == ["/calendars/some-calendar-id/events/some-event-id-1"]
    assert event == Event(
        id="some-event-id-1",
        summary="Event 1",
        description="Event description 1",
        start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
        end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
        transparency="transparent",
    )


async def test_get_event_as_resource_calendar_all_day_event(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test getting a calendar event for a resource."""

    json_response(
        {
            "id": "some-event-id-1",
            "summary": "Event 1",
            "description": "Event description 1",
            "start": {
                # All day event incorrectly set as dateTime
                "dateTime": "2022-04-13T00:00:00+02:00",
                "timeZone": "Europe/Oslo",
            },
            "end": {"dateTime": "2022-04-14T00:00:00+02:00", "timeZone": "Europe/Oslo"},
            "status": "confirmed",
            "transparency": "transparent",
        }
    )
    calendar_service = await calendar_service_cb()
    event = await calendar_service.async_get_event(
        "some-calendar-id@resource.calendar.google.com", "some-event-id-1"
    )
    assert url_request() == [
        "/calendars/some-calendar-id@resource.calendar.google.com/events/some-event-id-1"
    ]
    assert event == Event(
        id="some-event-id-1",
        summary="Event 1",
        description="Event description 1",
        start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
        end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
        transparency="transparent",
    )


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
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"
        "&timeMin=2022-04-30T01:31:02%2B00:00"
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

    items = []
    async for result_page in result:
        items.extend(result_page.items)
    assert len(items) == 2


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
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"
        "&timeMin=2022-04-13T07:30:12-06:00&timeMax=2022-04-13T09:30:12-06:00"
    ]


@freeze_time("2022-04-30 07:31:02", tz_offset=-6)
async def test_list_events_with_all_day_event_in_resource_calendar(
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
                        "dateTime": "2022-04-13T00:00:00+02:00",
                        "timeZone": "Europe/Oslo",
                    },
                    "end": {
                        "dateTime": "2022-04-14T00:00:00+02:00",
                        "timeZone": "Europe/Oslo",
                    },
                    "status": "confirmed",
                    "transparency": "transparent",
                },
                {
                    "id": "some-event-id-2",
                    "summary": "Event 2",
                    "description": "Event description 2",
                    "start": {
                        "dateTime": "2022-04-14T00:00:00+02:00",
                        "timeZone": "Europe/Oslo",
                    },
                    "end": {
                        "dateTime": "2022-04-20T00:00:00+02:00",
                        "timeZone": "Europe/Oslo",
                    },
                    "transparency": "opaque",
                },
            ]
        }
    )
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id@resource.calendar.google.com")
    )
    assert url_request() == [
        f"/calendars/some-calendar-id@resource.calendar.google.com/events?{EVENT_LIST_PARAMS}"
        "&timeMin=2022-04-30T01:31:02%2B00:00"
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

    items = []
    async for result_page in result:
        items.extend(result_page.items)
    assert len(items) == 2


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


@freeze_time("2022-04-30 07:31:02", tz_offset=-6)
async def test_list_events_multiple_pages_with_iterator(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test list calendars API."""

    json_response(
        {
            "nextPageToken": "page-token-1",
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
    json_response(
        {
            "nextPageToken": "page-token-2",
            "items": [
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
            ],
        }
    )
    json_response(
        {
            "items": [],
        }
    )
    calendar_service = await calendar_service_cb()
    result = await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="some-calendar-id")
    )
    # Before iterating, page token is present
    assert result.page_token is not None

    # Consume all items
    items = []
    page_tokens = []
    async for result_page in result:
        items.extend(result_page.items)
        page_tokens.append(result_page.page_token)

    assert url_request() == [
        # Request #1
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"
        "&timeMin=2022-04-30T01:31:02%2B00:00",
        # Request #2
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"
        "&pageToken=page-token-1&timeMin=2022-04-30T01:31:02%2B00:00",
        # Request #3
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"
        "&pageToken=page-token-2&timeMin=2022-04-30T01:31:02%2B00:00",
    ]
    assert items == [
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
    assert page_tokens == ["page-token-1", "page-token-2", None]


@freeze_time("2022-04-30 07:31:02", tz_offset=-6)
async def test_list_event_url_encoding(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test list calendars API."""

    # Response is not interesting for this test, just url
    json_response({"items": []})

    calendar_service = await calendar_service_cb()
    await calendar_service.async_list_events(
        ListEventsRequest(calendar_id="en.usa#holiday@group.v.calendar.google.com")
    )
    assert url_request() == [
        f"/calendars/en.usa#holiday@group.v.calendar.google.com/events?{EVENT_LIST_PARAMS}"
        "&timeMin=2022-04-30T01:31:02%2B00:00"
    ]


async def test_delete_event(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    json_request: Callable[[], str],
) -> None:
    """Test deleting an event."""
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "iCalUID": "some-event-id-1@google.com",
                    "summary": "Event 1",
                    "start": {
                        "date": "2022-04-13",
                    },
                    "end": {
                        "date": "2022-04-14",
                    },
                    "status": "confirmed",
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    json_response({})
    sync = await event_sync_manager_cb()
    await sync.run()
    await sync.store_service.async_delete_event(ical_uuid="some-event-id-1@google.com")
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_SYNC_PARAMS}",
        "/calendars/some-calendar-id/events/some-event-id-1",
    ]
    assert json_request() == []


async def test_delete_recurring_event_instance(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    json_request: Callable[[], str],
) -> None:
    """Test deleting a single instance of a recurring event."""
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "iCalUID": "some-event-id-1@google.com",
                    "summary": "Event 1",
                    "start": {
                        "date": "2022-04-13",
                    },
                    "end": {
                        "date": "2022-04-14",
                    },
                    "status": "confirmed",
                    "recurrence": [
                        "RRULE:FREQ=WEEKLY;COUNT=5",
                    ],
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    json_response({})
    sync = await event_sync_manager_cb()
    await sync.run()

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-12 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-05-12 00:00:00"),
        )
    )
    event_iter = iter(result.events)
    event = next(event_iter)  # ignore first event
    event = next(event_iter)
    assert event.ical_uuid
    await sync.store_service.async_delete_event(
        ical_uuid=event.ical_uuid,
        event_id=event.id,
        recurrence_range=Range.NONE,
    )
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_SYNC_PARAMS}",
        "/calendars/some-calendar-id/events/some-event-id-1_20220420",
    ]
    assert json_request() == [
        {
            "id": "some-event-id-1_20220420",
            "status": "cancelled",
        }
    ]


async def test_delete_recurring_event_and_future(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    json_request: Callable[[], str],
) -> None:
    """Test deletinng future instances of a recurring event."""
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "iCalUID": "some-event-id-1@google.com",
                    "summary": "Event 1",
                    "start": {
                        "date": "2022-04-13",
                    },
                    "end": {
                        "date": "2022-04-14",
                    },
                    "status": "confirmed",
                    "recurrence": [
                        "RRULE:FREQ=WEEKLY;COUNT=5",
                    ],
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    json_response({})
    sync = await event_sync_manager_cb()
    await sync.run()

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-12 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-05-12 00:00:00"),
        )
    )
    event_iter = iter(result.events)
    event = next(event_iter)  # ignore first event
    event = next(event_iter)
    assert event.ical_uuid
    assert event.id == "some-event-id-1_20220420"
    await sync.store_service.async_delete_event(
        ical_uuid=event.ical_uuid,
        event_id=event.id,
        recurrence_range=Range.THIS_AND_FUTURE,
    )
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_SYNC_PARAMS}",
        "/calendars/some-calendar-id/events/some-event-id-1",
    ]
    assert json_request() == [
        {
            "id": "some-event-id-1",
            "recurrence": ["RRULE:FREQ=WEEKLY;UNTIL=20220419"],
        }
    ]


async def test_delete_recurring_event_series(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    json_request: Callable[[], str],
) -> None:
    """Test deleting an entire series of a recurring event."""
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "iCalUID": "some-event-id-1@google.com",
                    "summary": "Event 1",
                    "start": {
                        "date": "2022-04-13",
                    },
                    "end": {
                        "date": "2022-04-14",
                    },
                    "status": "confirmed",
                    "recurrence": [
                        "RRULE:FREQ=WEEKLY;COUNT=5",
                    ],
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    json_response({})
    sync = await event_sync_manager_cb()
    await sync.run()

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-12 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-05-12 00:00:00"),
        )
    )
    event_iter = iter(result.events)
    event = next(event_iter)  # ignore first event
    event = next(event_iter)
    assert event.ical_uuid
    await sync.store_service.async_delete_event(
        ical_uuid=event.ical_uuid,
    )
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_SYNC_PARAMS}",
        "/calendars/some-calendar-id/events/some-event-id-1",
    ]
    assert json_request() == []


async def test_delete_recurring_event_and_future_first_instance(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    json_request: Callable[[], str],
) -> None:
    """Test deleting future instances of the first instance of a recurring event."""
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "iCalUID": "some-event-id-1@google.com",
                    "summary": "Event 1",
                    "start": {
                        "date": "2022-04-13",
                    },
                    "end": {
                        "date": "2022-04-14",
                    },
                    "status": "confirmed",
                    "recurrence": [
                        "RRULE:FREQ=WEEKLY;COUNT=5",
                    ],
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    json_response({})
    sync = await event_sync_manager_cb()
    await sync.run()

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-12 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-05-12 00:00:00"),
        )
    )
    event_iter = iter(result.events)
    event = next(event_iter)
    assert event.ical_uuid
    await sync.store_service.async_delete_event(
        ical_uuid=event.ical_uuid,
        event_id=event.id,
        recurrence_range=Range.THIS_AND_FUTURE,
    )
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_SYNC_PARAMS}",
        "/calendars/some-calendar-id/events/some-event-id-1",
    ]
    assert json_request() == []


async def test_store_create_event_with_date(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_request: Callable[[], str],
    url_request: Callable[[], str],
    json_response: ApiResult,
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

    json_response({})
    sync = await event_sync_manager_cb()
    await sync.store_service.async_add_event(event)
    assert url_request() == [
        "/calendars/some-calendar-id/events",
    ]
    assert json_request() == [
        {
            "summary": "Summary",
            "description": "Description",
            "start": {"date": "2022-04-15"},
            "end": {"date": "2022-04-17"},
        }
    ]


async def test_delete_missing_event(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
) -> None:
    """Test delete api missing required fields"""

    sync = await event_sync_manager_cb()
    with pytest.raises(ValueError, match="Event does not exist"):
        await sync.store_service.async_delete_event(
            ical_uuid="some-event-id@google.com",
            event_id="some-event-id",
        )


async def test_create_event_with_reminder(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    json_request: ApiRequest,
) -> None:
    """Test create event API when setting a reminder."""

    start_date = datetime.date(2022, 4, 15)
    end_date = start_date + datetime.timedelta(days=2)

    event = Event(
        summary="Summary",
        description="Description",
        start=DateOrDatetime(date=start_date),
        end=DateOrDatetime(date=end_date),
        reminders=Reminders(
            overrides=[
                ReminderOverride(
                    method=ReminderMethod.POPUP,
                    minutes=7,
                )
            ],
        ),
    )

    calendar_service = await calendar_service_cb()
    await calendar_service.async_create_event("calendar-id", event)
    assert json_request() == [
        {
            "summary": "Summary",
            "description": "Description",
            "start": {"date": "2022-04-15"},
            "end": {"date": "2022-04-17"},
            "reminders": {"overrides": [{"method": "popup", "minutes": 7}]},
        }
    ]


async def test_api_self_response(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    json_request: Callable[[], str],
) -> None:
    """Test api responses with reserved keywords."""
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "iCalUID": "some-event-id-1@google.com",
                    "summary": "Event 1",
                    "start": {
                        "date": "2022-04-13",
                    },
                    "end": {
                        "date": "2022-04-14",
                    },
                    "status": "confirmed",
                    "attendees": [
                        {
                            "email": "example@example.com",
                            "self": True,
                            "responseStatus": "tentative",
                        }
                    ],
                }
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    json_response({})
    sync = await event_sync_manager_cb()
    await sync.run()
