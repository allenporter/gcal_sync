"""Library for handling local event sync.

This library implements the best practices for how to
[Synchronize resources](https://developers.google.com/calendar/api/guides/sync)
for a Google Calendar.

To use this library, you create an instance of a sync manager then run the
`run` method on a regular basis to pull down the latest information from the server. You
may then query the latest information from the local store service.
"""

# pylint: disable=duplicate-code
from __future__ import annotations

import datetime
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from .api import (
    CalendarEventStoreService,
    CalendarListRequest,
    CalendarListResponse,
    CalendarListStoreService,
    GoogleCalendarService,
    ListEventsRequest,
    SyncableRequest,
    SyncableResponse,
    SyncEventsRequest,
    _ListEventsResponseModel,
)
from .const import CALENDAR_LIST_SYNC, EVENT_SYNC, ITEMS, SYNC_TOKEN, SYNC_TOKEN_VERSION
from .exceptions import InvalidSyncTokenException
from .model import Event, EventStatusEnum
from .store import CalendarStore, InMemoryCalendarStore, ScopedCalendarStore

_LOGGER = logging.getLogger(__name__)


# Can be incremented to blow away existing store
VERSION = 2
MIN_SYNC_DATETIME = datetime.datetime(2006, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)


def _items_func(
    result: CalendarListResponse | _ListEventsResponseModel,
) -> dict[str, Any]:
    items = {}
    for item in result.items:
        if not item.id:
            continue
        if isinstance(item, Event) and item.status == EventStatusEnum.CANCELLED:
            # Convert to a minimal tombstone, stripping event content (summary,
            # description, attendees, etc.). Deleted non-recurring tombstones are
            # pruned after all pages complete; recurring exception tombstones are
            # kept only while their parent recurring event remains active.
            items[item.id] = item.model_dump(
                mode="json",
                include={"id", "status", "recurring_event_id", "original_start_time"},
                exclude_none=True,
            )
        else:
            items[item.id] = item.model_dump(mode="json", exclude_none=True)
    return items


def _prune_cancelled_events(stored_items: dict[str, Any]) -> None:
    """Remove cancelled events and orphaned recurring exceptions from the store.

    Cancelled exceptions of an active recurring event (those with both
    `recurring_event_id` and `original_start_time`) must be retained for the
    lifetime of the parent recurring event so timeline expansion can exclude
    those cancelled occurrences from the parent's recurrence rule. All other
    cancelled events and any children of a cancelled recurring master are
    removed.
    """
    to_delete: list[str] = []
    for item_id, data in stored_items.items():
        parent_id = data.get("recurring_event_id")
        parent = stored_items.get(parent_id) if parent_id else None
        if (
            parent is not None and parent.get("status") == EventStatusEnum.CANCELLED
        ) or (
            data.get("status") == EventStatusEnum.CANCELLED
            and not (parent is not None and data.get("original_start_time"))
        ):
            to_delete.append(item_id)
    for item_id in to_delete:
        del stored_items[item_id]


async def _run_sync[T: SyncableRequest, S: SyncableResponse](
    store_data: dict[str, Any],
    new_request: Callable[[str | None], T],
    api_call: Callable[[T], Awaitable[S]],
    items_func: Callable[[S], dict[str, Any]],
) -> dict[str, Any]:
    store_data.setdefault(ITEMS, {})

    # Invalid existing data in store if no longer valid
    sync_token_version = store_data.get(SYNC_TOKEN_VERSION)
    if sync_token_version and sync_token_version < VERSION:
        _LOGGER.debug(
            "Invaliding token with version %s, %s", sync_token_version, VERSION
        )
        store_data[SYNC_TOKEN] = None
        store_data[ITEMS] = {}

    # Load sync token from last execution if any
    sync_token = store_data.get(SYNC_TOKEN)

    request = new_request(sync_token)
    while True:
        try:
            result = await api_call(request)
        except InvalidSyncTokenException:
            _LOGGER.debug("Invalidating sync token")
            store_data[SYNC_TOKEN] = None
            store_data[ITEMS] = {}
            return await _run_sync(store_data, new_request, api_call, items_func)

        store_data[ITEMS].update(items_func(result))

        if not result.page_token:
            if not result.sync_token:
                raise InvalidSyncTokenException(
                    "Unexpected API response, missing sync_token"
                )
            store_data[SYNC_TOKEN] = result.sync_token
            store_data[SYNC_TOKEN_VERSION] = VERSION
            break
        request.page_token = result.page_token

    return store_data


class CalendarListSyncManager:
    """Manages synchronizing a calend arlist from API to local store."""

    def __init__(
        self, api: GoogleCalendarService, store: CalendarStore | None = None
    ) -> None:
        """Initialize CalendarListSyncManager."""
        self._api = api
        self._store = (
            ScopedCalendarStore(store, CALENDAR_LIST_SYNC)
            if store
            else InMemoryCalendarStore()
        )

    @property
    def store_service(self) -> CalendarListStoreService:
        """Return the local API for fetching events."""
        return CalendarListStoreService(self._store)

    @property
    def api(self) -> GoogleCalendarService:
        """Return the cloud API."""
        return self._api

    async def run(self) -> None:
        """Run the event sync manager."""

        def new_request(sync_token: str | None) -> CalendarListRequest:
            request = CalendarListRequest()
            if not sync_token:
                _LOGGER.debug("Performing full calendar sync for calendar list")
            else:
                _LOGGER.debug(
                    "Performing incremental sync for calendar list (%s)",
                    sync_token,
                )
                request.sync_token = sync_token
            return request

        store_data = await self._store.async_load() or {}
        store_data = await _run_sync(
            store_data, new_request, self._api.async_list_calendars, _items_func
        )
        await self._store.async_save(store_data)


class CalendarEventSyncManager:
    """Manages synchronizing events from API to local store."""

    def __init__(
        self,
        api: GoogleCalendarService,
        calendar_id: str | None = None,
        store: CalendarStore | None = None,
        request_template: SyncEventsRequest | None = None,
    ) -> None:
        """Initialize CalendarEventSyncManager."""
        self._api = api
        if request_template is None:
            if not calendar_id:
                raise ValueError("Required either calendar_id or request_template")
            self._request_template = SyncEventsRequest.model_validate(
                {"calendar_id": calendar_id}
            )
        else:
            self._request_template = request_template
        self._calendar_id = self._request_template.calendar_id
        self._store = (
            ScopedCalendarStore(
                ScopedCalendarStore(store, EVENT_SYNC), self._calendar_id
            )
            if store
            else InMemoryCalendarStore()
        )

    @property
    def store_service(self) -> CalendarEventStoreService:
        """Return the local API for fetching events."""
        return CalendarEventStoreService(self._store, self._calendar_id, self._api)

    @property
    def api(self) -> GoogleCalendarService:
        """Return the cloud API."""
        return self._api

    async def run(self) -> None:
        """Run the event sync manager."""

        def new_request(sync_token: str | None) -> ListEventsRequest:
            if not sync_token:
                _LOGGER.debug(
                    "Performing full calendar sync for calendar %s", self._calendar_id
                )
                return self._request_template.model_copy()
            _LOGGER.debug(
                "Performing incremental sync for calendar %s (%s)",
                self._calendar_id,
                sync_token,
            )
            return self._request_template.model_validate(
                {
                    **self._request_template.model_dump(include={"calendar_id"}),
                    "sync_token": sync_token,
                }
            )

        store_data = await self._store.async_load() or {}
        store_data = await _run_sync(
            store_data, new_request, self._api.async_list_events_page, _items_func
        )
        _prune_cancelled_events(store_data[ITEMS])
        await self._store.async_save(store_data)
