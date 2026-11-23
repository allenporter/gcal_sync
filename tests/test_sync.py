"""Tests for event sync library."""

from __future__ import annotations

import datetime
import zoneinfo
from collections.abc import Awaitable, Callable
from typing import Any
from unittest.mock import patch

import aiohttp
import pytest
from freezegun import freeze_time

from gcal_sync.api import (
    GoogleCalendarService,
    LocalListEventsRequest,
    SyncEventsRequest,
)
from gcal_sync.const import EVENT_SYNC, ITEMS, SYNC_TOKEN, SYNC_TOKEN_VERSION
from gcal_sync.exceptions import ApiException, InvalidSyncTokenException
from gcal_sync.model import EVENT_FIELDS, AccessRole, Calendar, DateOrDatetime, Event
from gcal_sync.store import CalendarStore
from gcal_sync.sync import VERSION, CalendarEventSyncManager, CalendarListSyncManager

from .conftest import CALENDAR_ID, ApiResult, ResponseResult

SYNC_TIME = "2006-01-01T00:00:00%2B00:00"
EVENT_LIST_PARAMS = (
    f"maxResults=1000&fields=kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"
)
EVENT_PAGE_PARAMS = (
    f"maxResults=1000&fields=kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"
)


async def test_calendar_list_sync_failure(
    calendar_list_sync_manager_cb: Callable[[], Awaitable[CalendarListSyncManager]],
    response: ResponseResult,
) -> None:
    """Test list calendars API."""

    response(aiohttp.web.Response(status=500))

    sync = await calendar_list_sync_manager_cb()
    with pytest.raises(ApiException):
        await sync.run()


async def test_list_calendars(
    calendar_list_sync_manager_cb: Callable[[], Awaitable[CalendarListSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
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
            ],
            "nextSyncToken": "example-token",
        }
    )
    sync = await calendar_list_sync_manager_cb()
    await sync.run()
    assert url_request() == ["/users/me/calendarList"]

    result = await sync.store_service.async_list_calendars()
    assert result.calendars == [
        Calendar(
            id="calendar-id-1", summary="Calendar 1", access_role=AccessRole.READER
        ),
        Calendar(
            id="calendar-id-2", summary="Calendar 2", access_role=AccessRole.OWNER
        ),
    ]


async def test_list_calendars_pages(
    calendar_list_sync_manager_cb: Callable[[], Awaitable[CalendarListSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test list calendars API."""

    json_response(
        {
            "items": [
                {
                    "id": "calendar-id-1",
                    "summary": "Calendar 1",
                    "access_role": "reader",
                },
            ],
            "nextPageToken": "page-token-1",
        }
    )
    json_response(
        {
            "items": [
                {
                    "id": "calendar-id-2",
                    "summary": "Calendar 2",
                    "access_role": "owner",
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    sync = await calendar_list_sync_manager_cb()
    await sync.run()
    assert url_request() == [
        "/users/me/calendarList",
        "/users/me/calendarList?pageToken=page-token-1",
    ]

    json_response(
        {
            "items": [
                {
                    "id": "calendar-id-3",
                    "summary": "Calendar 3",
                    "access_role": "writer",
                },
            ],
            "nextSyncToken": "page-token-2",
        }
    )
    await sync.run()
    assert url_request() == [
        "/users/me/calendarList",
        "/users/me/calendarList?pageToken=page-token-1",
        "/users/me/calendarList?syncToken=sync-token-1",
    ]

    result = await sync.store_service.async_list_calendars()
    assert result.calendars == [
        Calendar(
            id="calendar-id-1", summary="Calendar 1", access_role=AccessRole.READER
        ),
        Calendar(
            id="calendar-id-2", summary="Calendar 2", access_role=AccessRole.OWNER
        ),
        Calendar(
            id="calendar-id-3", summary="Calendar 3", access_role=AccessRole.WRITER
        ),
    ]


async def test_event_sync_failure(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    response: ResponseResult,
) -> None:
    """Test failure response when syncing."""

    response(aiohttp.web.Response(status=500))

    sync = await event_sync_manager_cb()
    with pytest.raises(ApiException):
        await sync.run()


@freeze_time("2022-04-05 07:31:02", tz_offset=-7)
async def test_event_lookup_items(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
) -> None:
    """Test lookup events API."""

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
                        "date": "2022-04-15",
                    },
                    "end": {
                        "date": "2022-04-20",
                    },
                    "transparency": "opaque",
                },
            ],
            "nextSyncToken": "example-token",
        }
    )

    sync = await event_sync_manager_cb()
    await sync.run()
    assert url_request() == [f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"]

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-12 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-04-16 00:00:00"),
        )
    )
    assert result.events == [
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
            start=DateOrDatetime(date=datetime.date(2022, 4, 15)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 20)),
            transparency="opaque",
        ),
    ]

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-13 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-04-14 00:00:00"),
        )
    )
    assert result.events == [
        Event(
            id="some-event-id-1",
            summary="Event 1",
            description="Event description 1",
            start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
            transparency="transparent",
        ),
    ]
    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-15 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-04-17 00:00:00"),
        )
    )
    assert result.events == [
        Event(
            id="some-event-id-2",
            summary="Event 2",
            description="Event description 2",
            start=DateOrDatetime(date=datetime.date(2022, 4, 15)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 20)),
            transparency="opaque",
        ),
    ]

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-05 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-04-07 00:00:00"),
        )
    )
    assert not result.events

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-21 00:00:00"),
            end_time=datetime.datetime.fromisoformat("2022-04-22 00:00:00"),
        )
    )
    assert not result.events


@freeze_time("2022-04-05 07:31:02", tz_offset=-7)
async def test_event_sync_date_pages(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test lookup events API."""

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
            ],
            "nextPageToken": "page-token-1",
        }
    )
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-2",
                    "summary": "Event 2",
                    "description": "Event description 2",
                    "start": {
                        "date": "2022-04-15",
                    },
                    "end": {
                        "date": "2022-04-20",
                    },
                    "transparency": "opaque",
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )

    sync = await event_sync_manager_cb()
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}",
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}&pageToken=page-token-1",
    ]
    request_reset()

    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-3",
                    "summary": "Event 3",
                    "description": "Event description 3",
                    "start": {
                        "date": "2022-04-16",
                    },
                    "end": {
                        "date": "2022-04-27",
                    },
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_PAGE_PARAMS}&syncToken=sync-token-1",
    ]


@freeze_time("2022-04-05 07:31:02", tz_offset=-7)
async def test_event_sync_datetime_pages(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test lookup events API."""

    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "summary": "Event 1",
                    "description": "Event description 1",
                    "start": {
                        "dateTime": "2022-04-13T03:00:00",
                    },
                    "end": {
                        "dateTime": "2022-04-13T04:00:00",
                    },
                    "status": "confirmed",
                    "transparency": "transparent",
                },
            ],
            "nextPageToken": "page-token-1",
        }
    )
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-2",
                    "summary": "Event 2",
                    "description": "Event description 2",
                    "start": {
                        "dateTime": "2022-04-13T05:00:00",
                    },
                    "end": {
                        "dateTime": "2022-04-13T06:00:00",
                    },
                    "transparency": "opaque",
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )

    sync = await event_sync_manager_cb()
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}",
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}&pageToken=page-token-1",
    ]
    request_reset()

    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-3",
                    "summary": "Event 3",
                    "description": "Event description 3",
                    "start": {
                        "dateTime": "2022-04-13T05:30:00",
                    },
                    "end": {
                        "dateTime": "2022-04-13T06:00:00",
                    },
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_PAGE_PARAMS}&syncToken=sync-token-1",
    ]


@freeze_time("2022-04-05 07:31:02", tz_offset=-7)
async def test_event_invalidated_sync_token(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    response: ResponseResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test lookup events API."""

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
                },
                {
                    "id": "some-event-id-2",
                    "summary": "Event 2",
                    "description": "Event description 2",
                    "start": {
                        "date": "2022-04-15",
                    },
                    "end": {
                        "date": "2022-04-20",
                    },
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )

    sync = await event_sync_manager_cb()
    await sync.run()
    assert url_request() == [f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"]

    result = await sync.store_service.async_list_events(LocalListEventsRequest())
    assert result.events == [
        Event(
            id="some-event-id-1",
            summary="Event 1",
            description="Event description 1",
            start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
        ),
        Event(
            id="some-event-id-2",
            summary="Event 2",
            description="Event description 2",
            start=DateOrDatetime(date=datetime.date(2022, 4, 15)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 20)),
        ),
    ]

    request_reset()
    response(aiohttp.web.Response(status=410))  # Token invalid
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-3",
                    "summary": "Event 3",
                    "description": "Event description 3",
                    "start": {
                        "date": "2022-04-12",
                    },
                    "end": {
                        "date": "2022-04-13",
                    },
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_PAGE_PARAMS}&syncToken=sync-token-1",
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}",
    ]
    result = await sync.store_service.async_list_events(LocalListEventsRequest())
    assert result.events == [
        Event(
            id="some-event-id-3",
            summary="Event 3",
            description="Event description 3",
            start=DateOrDatetime(date=datetime.date(2022, 4, 12)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 13)),
        ),
    ]


@freeze_time("2022-04-05 07:31:02", tz_offset=-7)
async def test_event_token_version_invalidation(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test lookup events API."""

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
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    sync = await event_sync_manager_cb()
    await sync.run()
    assert url_request() == [f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"]

    result = await sync.store_service.async_list_events(LocalListEventsRequest())
    assert len(result.events) == 1
    assert result.events[0].id == "some-event-id-1"

    request_reset()
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-2",
                    "summary": "Event 2",
                    "description": "Event description 2",
                    "start": {
                        "date": "2022-04-15",
                    },
                    "end": {
                        "date": "2022-04-20",
                    },
                    "transparency": "opaque",
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )

    with patch("gcal_sync.sync.VERSION", VERSION + 1):
        await sync.run()

    assert url_request() == [f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}"]
    result = await sync.store_service.async_list_events(LocalListEventsRequest())
    assert len(result.events) == 1
    assert result.events[0].id == "some-event-id-2"


@freeze_time("2022-04-05 07:31:02", tz_offset=-7)
async def test_canceled_events(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    store: CalendarStore,
    json_response: ApiResult,
) -> None:
    """Test lookup events API."""

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
                },
                {
                    "id": "some-event-id-2",
                    "summary": "Event 2",
                    "description": "Event description 2",
                    "start": {
                        "date": "2022-04-15",
                    },
                    "end": {
                        "date": "2022-04-20",
                    },
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )

    sync = await event_sync_manager_cb()
    await sync.run()
    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2001-01-01T00:00:00"),
        )
    )
    assert result.events == [
        Event(
            id="some-event-id-1",
            summary="Event 1",
            description="Event description 1",
            start=DateOrDatetime(date=datetime.date(2022, 4, 13)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 14)),
        ),
        Event(
            id="some-event-id-2",
            summary="Event 2",
            description="Event description 2",
            start=DateOrDatetime(date=datetime.date(2022, 4, 15)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 20)),
        ),
    ]
    json_response(
        {
            "items": [
                {
                    "id": "some-event-id-1",
                    "status": "cancelled",
                },
                {
                    "id": "never-cached-event-id",
                    "status": "cancelled",
                },
                {
                    "id": "some-event-id-3",
                    "summary": "Event 3",
                    "description": "Event description 3",
                    "start": {
                        "date": "2022-04-21",
                    },
                    "end": {
                        "date": "2022-04-22",
                    },
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )
    await sync.run()
    assert set(await _stored_events(store)) == {"some-event-id-2", "some-event-id-3"}

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2001-01-01T00:00:00"),
        )
    )
    assert result.events == [
        Event(
            id="some-event-id-2",
            summary="Event 2",
            description="Event description 2",
            start=DateOrDatetime(date=datetime.date(2022, 4, 15)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 20)),
        ),
        Event(
            id="some-event-id-3",
            summary="Event 3",
            description="Event description 3",
            start=DateOrDatetime(date=datetime.date(2022, 4, 21)),
            end=DateOrDatetime(date=datetime.date(2022, 4, 22)),
        ),
    ]

    # Exercise the timeline and dependencies on the timezone
    timeline = await sync.store_service.async_get_timeline(
        zoneinfo.ZoneInfo("America/Regina")
    )
    assert [event.summary for event in timeline] == ["Event 2", "Event 3"]

    event_iter = timeline.start_after(
        datetime.datetime(
            2022, 4, 20, 23, 0, 0, tzinfo=zoneinfo.ZoneInfo("America/Regina")
        )
    )
    assert [event.summary for event in event_iter] == ["Event 3"]

    event_iter = timeline.start_after(
        datetime.datetime(
            2022, 4, 21, 1, 0, 0, tzinfo=zoneinfo.ZoneInfo("America/Regina")
        )
    )
    assert [event.summary for event in event_iter] == []


async def _stored_events(store: CalendarStore) -> dict[str, Any]:
    """Return raw stored event items for CALENDAR_ID."""
    store_data = await store.async_load()
    assert store_data is not None
    return store_data[EVENT_SYNC][CALENDAR_ID][ITEMS]  # type: ignore[no-any-return]


async def test_cancelled_recurring_events_in_store(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    store: CalendarStore,
    json_response: ApiResult,
) -> None:
    """Test cancelled recurring exceptions, multi-page ordering, and standalone instances."""
    # Page 1: cancelled exception arrives before its master on Page 2
    json_response(
        {
            "items": [
                {
                    "id": "recurring-1_20220420",
                    "status": "cancelled",
                    "recurringEventId": "recurring-1",
                    "originalStartTime": {"date": "2022-04-20"},
                    "summary": "Details that should be stripped",
                    "description": "Long description",
                },
            ],
            "nextPageToken": "page-1",
        }
    )
    json_response(
        {
            "items": [
                {
                    "id": "recurring-1",
                    "iCalUID": "recurring-1@google.com",
                    "summary": "Weekly Event",
                    "start": {"date": "2022-04-13"},
                    "end": {"date": "2022-04-14"},
                    "recurrence": ["RRULE:FREQ=WEEKLY;COUNT=3"],
                    "status": "confirmed",
                },
                {
                    "id": "recurring-1_20220427",
                    "iCalUID": "recurring-1@google.com",
                    "summary": "Modified Weekly Event",
                    "start": {"date": "2022-04-28"},
                    "end": {"date": "2022-04-29"},
                    "recurringEventId": "recurring-1",
                    "originalStartTime": {"date": "2022-04-27"},
                    "status": "confirmed",
                },
                {
                    "id": "other-master_20220420",
                    "iCalUID": "other-master@google.com",
                    "summary": "Invite-Only Standalone Instance",
                    "start": {"date": "2022-04-21"},
                    "end": {"date": "2022-04-22"},
                    "recurringEventId": "other-master",
                    "originalStartTime": {"date": "2022-04-20"},
                    "status": "confirmed",
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )

    sync = await event_sync_manager_cb()
    await sync.run()

    stored_items = await _stored_events(store)
    assert set(stored_items) == {
        "recurring-1",
        "recurring-1_20220420",
        "recurring-1_20220427",
        "other-master_20220420",
    }
    assert stored_items["recurring-1_20220420"] == {
        "id": "recurring-1_20220420",
        "status": "cancelled",
        "recurring_event_id": "recurring-1",
        "original_start_time": {"date": "2022-04-20"},
    }
    assert None not in stored_items["recurring-1"].values()

    result = await sync.store_service.async_list_events(
        LocalListEventsRequest(
            start_time=datetime.datetime.fromisoformat("2022-04-01T00:00:00"),
        )
    )
    assert [event.start.value for event in result.events] == [
        datetime.date(2022, 4, 13),
        datetime.date(2022, 4, 21),
        datetime.date(2022, 4, 28),
    ]

    # Cancel master on Page 1; exception of that master and cancelled standalone instance on Page 2
    json_response(
        {
            "items": [{"id": "recurring-1", "status": "cancelled"}],
            "nextPageToken": "page-2",
        }
    )
    json_response(
        {
            "items": [
                {
                    "id": "recurring-1_20220427",
                    "status": "cancelled",
                    "recurringEventId": "recurring-1",
                    "originalStartTime": {"date": "2022-04-27"},
                },
                {
                    "id": "other-master_20220420",
                    "status": "cancelled",
                    "recurringEventId": "other-master",
                    "originalStartTime": {"date": "2022-04-20"},
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )
    await sync.run()
    assert await _stored_events(store) == {}


async def test_legacy_store_cancelled_events_cleaned_without_full_resync(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    store: CalendarStore,
    json_response: ApiResult,
    url_request: Callable[[], list[str]],
) -> None:
    """Test pre-existing cancelled events in a legacy store are cleaned up in place."""
    await store.async_save(
        {
            EVENT_SYNC: {
                CALENDAR_ID: {
                    SYNC_TOKEN: "sync-token-1",
                    SYNC_TOKEN_VERSION: VERSION,
                    ITEMS: {
                        "active-1": {
                            "id": "active-1",
                            "summary": "Active Event",
                            "start": {"date": "2022-04-13"},
                            "end": {"date": "2022-04-14"},
                            "status": "confirmed",
                        },
                        "legacy-cancelled-single": {
                            "id": "legacy-cancelled-single",
                            "status": "cancelled",
                        },
                        "legacy-cancelled-master": {
                            "id": "legacy-cancelled-master",
                            "status": "cancelled",
                        },
                        "legacy-cancelled-master_20220420": {
                            "id": "legacy-cancelled-master_20220420",
                            "recurring_event_id": "legacy-cancelled-master",
                            "original_start_time": {"date": "2022-04-20"},
                            "status": "cancelled",
                        },
                        "legacy-cancelled-master_20220427": {
                            "id": "legacy-cancelled-master_20220427",
                            "recurring_event_id": "legacy-cancelled-master",
                            "original_start_time": {"date": "2022-04-27"},
                            "status": "confirmed",
                        },
                        "orphan-cancelled-exception": {
                            "id": "orphan-cancelled-exception",
                            "recurring_event_id": "missing-master",
                            "original_start_time": {"date": "2022-04-20"},
                            "status": "cancelled",
                        },
                        "cancelled-exception-no-ost": {
                            "id": "cancelled-exception-no-ost",
                            "recurring_event_id": "active-master",
                            "status": "cancelled",
                        },
                        "active-master": {
                            "id": "active-master",
                            "summary": "Active Recurring",
                            "start": {"date": "2022-04-13"},
                            "end": {"date": "2022-04-14"},
                            "recurrence": ["RRULE:FREQ=WEEKLY;COUNT=3"],
                            "status": "confirmed",
                        },
                        "active-master_20220420": {
                            "id": "active-master_20220420",
                            "recurring_event_id": "active-master",
                            "original_start_time": {"date": "2022-04-20"},
                            "status": "cancelled",
                        },
                    },
                }
            }
        }
    )

    json_response({"items": [], "nextSyncToken": "sync-token-2"})

    sync = await event_sync_manager_cb()
    await sync.run()

    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_PAGE_PARAMS}&syncToken=sync-token-1"
    ]
    assert set(await _stored_events(store)) == {
        "active-1",
        "active-master",
        "active-master_20220420",
    }


async def test_event_sync_recover_failure(
    calendar_list_sync_manager_cb: Callable[[], Awaitable[CalendarListSyncManager]],
    json_response: ApiResult,
    response: ResponseResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test list calendars API."""
    json_response(
        {
            "items": [
                {
                    "id": "calendar-id-1",
                    "summary": "Calendar 1",
                    "accessRole": "writer",
                },
            ],
            "nextSyncToken": "sync-token-1",
        }
    )
    sync = await calendar_list_sync_manager_cb()
    await sync.run()
    assert url_request() == ["/users/me/calendarList"]

    response(aiohttp.web.Response(status=500))
    with pytest.raises(ApiException):
        await sync.run()
    assert url_request() == [
        "/users/me/calendarList",
        "/users/me/calendarList?syncToken=sync-token-1",
    ]
    request_reset()

    result = await sync.store_service.async_list_calendars()
    assert result.calendars == [
        Calendar(
            id="calendar-id-1", summary="Calendar 1", access_role=AccessRole.WRITER
        ),
    ]

    json_response(
        {
            "items": [
                {
                    "id": "calendar-id-2",
                    "summary": "Calendar 2",
                    "accessRole": "writer",
                },
            ],
            "nextSyncToken": "sync-token-2",
        }
    )

    await sync.run()
    assert url_request() == [
        "/users/me/calendarList?syncToken=sync-token-1",
    ]
    result = await sync.store_service.async_list_calendars()
    assert result.calendars == [
        Calendar(
            id="calendar-id-1", summary="Calendar 1", access_role=AccessRole.WRITER
        ),
        Calendar(
            id="calendar-id-2", summary="Calendar 2", access_role=AccessRole.WRITER
        ),
    ]


async def test_event_sync_invalid_api_response(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]],
    json_response: ApiResult,
) -> None:
    """Test invalid server api response during sync."""
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
            ],
            # No nextSyncToken
        }
    )

    sync = await event_sync_manager_cb()
    with pytest.raises(InvalidSyncTokenException):
        await sync.run()


async def test_event_sync_with_search(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    store: CalendarStore,
    json_response: ApiResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test syncing events with a minimum time of events to return."""
    service = await calendar_service_cb()
    sync = CalendarEventSyncManager(
        service,
        store=store,
        request_template=SyncEventsRequest(calendar_id=CALENDAR_ID, search="trash"),
    )

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
            ],
            "nextSyncToken": "sync-token-1",
        },
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}&q=trash"
    ]
    request_reset()

    json_response(
        {
            "items": [],
            "nextSyncToken": "sync-token-2",
        },
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_PAGE_PARAMS}&syncToken=sync-token-1"
    ]


async def test_sync_required_fields(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    store: CalendarStore,
) -> None:
    """Test syncing events with a search string."""
    service = await calendar_service_cb()
    with pytest.raises(ValueError):
        CalendarEventSyncManager(service, store=store)


async def test_event_sync_min_time(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    store: CalendarStore,
    json_response: ApiResult,
    url_request: Callable[[], str],
    request_reset: Callable[[], str],
) -> None:
    """Test syncing events with a minimum time of events to return."""
    service = await calendar_service_cb()
    sync = CalendarEventSyncManager(
        service,
        store=store,
        request_template=SyncEventsRequest(
            calendar_id=CALENDAR_ID, start_time=datetime.datetime(2022, 1, 1, 0, 0, 0)
        ),
    )

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
            ],
            "nextSyncToken": "sync-token-1",
        },
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_LIST_PARAMS}&timeMin=2022-01-01T00:00:00"
    ]
    request_reset()

    json_response(
        {
            "items": [],
            "nextSyncToken": "sync-token-2",
        },
    )
    await sync.run()
    assert url_request() == [
        f"/calendars/some-calendar-id/events?{EVENT_PAGE_PARAMS}&syncToken=sync-token-1"
    ]
