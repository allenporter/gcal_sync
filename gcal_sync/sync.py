"""Library for handling local even sync."""
# pylint: disable=duplicate-code
from __future__ import annotations

import datetime
import logging
from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

from .api import (
    CalendarEventStoreService,
    CalendarListRequest,
    CalendarListResponse,
    CalendarListStoreService,
    GoogleCalendarService,
    ListEventsRequest,
    SyncableRequest,
    SyncableResponse,
    _ListEventsResponseModel,
)
from .const import CALENDAR_LIST_SYNC, EVENT_SYNC, ITEMS, SYNC_TOKEN, SYNC_TOKEN_VERSION
from .exceptions import InvalidSyncTokenException
from .store import CalendarStore, InMemoryCalendarStore, ScopedCalendarStore

_LOGGER = logging.getLogger(__name__)


# Can be incremented to blow away existing store
VERSION = 1


T = TypeVar("T", bound=SyncableRequest)
S = TypeVar("S", bound=SyncableResponse)


def _items_func(
    result: CalendarListResponse | _ListEventsResponseModel,
) -> dict[str, Any]:
    items = {}
    for item in result.items:
        if not item.id:
            continue
        items[item.id] = item
    return items


async def _run_sync(
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
            "Invaliding token with version {sync_token_version}, {TOKEN_VERSION}"
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
        calendar_id: str,
        store: CalendarStore | None = None,
    ) -> None:
        """Initialize CalendarEventSyncManager."""
        self._api = api
        self._calendar_id = calendar_id
        self._store = (
            ScopedCalendarStore(ScopedCalendarStore(store, EVENT_SYNC), calendar_id)
            if store
            else InMemoryCalendarStore()
        )

    @property
    def store_service(self) -> CalendarEventStoreService:
        """Return the local API for fetching events."""
        return CalendarEventStoreService(self._store)

    @property
    def api(self) -> GoogleCalendarService:
        """Return the cloud API."""
        return self._api

    async def run(self) -> None:
        """Run the event sync manager."""

        def new_request(sync_token: str | None) -> ListEventsRequest:
            request = ListEventsRequest(calendar_id=self._calendar_id)
            if not sync_token:
                _LOGGER.debug(
                    "Performing full calendar sync for calendar %s", self._calendar_id
                )
                # Sync at most 4 weeks of prior events
                request.start_time = datetime.datetime.now() - datetime.timedelta(
                    days=28
                )
            else:
                _LOGGER.debug(
                    "Performing incremental sync for calendar %s (%s)",
                    self._calendar_id,
                    sync_token,
                )
                request.sync_token = sync_token
            return request

        store_data = await self._store.async_load() or {}
        store_data = await _run_sync(
            store_data, new_request, self._api.async_list_events_page, _items_func
        )
        await self._store.async_save(store_data)
