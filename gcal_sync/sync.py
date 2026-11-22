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
from typing import Any, Protocol

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
from .model import Calendar, Event, EventStatusEnum
from .store import CalendarStore, InMemoryCalendarStore, ScopedCalendarStore

_LOGGER = logging.getLogger(__name__)


# Can be incremented to blow away existing store
VERSION = 2
MIN_SYNC_DATETIME = datetime.datetime(2006, 1, 1, 0, 0, 0, tzinfo=datetime.UTC)


def _serialize_item(item: Calendar | Event) -> dict[str, Any]:
    """Serialize a model item for local storage."""
    return item.model_dump(mode="json", exclude_defaults=True)


def _serialize_cancelled_exception(item: Event) -> dict[str, Any]:
    """Serialize only the fields needed to skip a cancelled recurring exception."""
    return item.model_dump(
        mode="json",
        include={"id", "status", "recurring_event_id", "original_start_time"},
        exclude_none=True,
    )


class _SyncItemUpdater[S: SyncableResponse](Protocol):
    """Applies synced response pages to local store items."""

    def reset(self) -> None:
        """Reset per-sync state before retrying a full sync."""

    def update(self, stored_items: dict[str, Any], result: S) -> None:
        """Apply a page of synced items to stored_items."""

    def finalize(self, stored_items: dict[str, Any]) -> None:
        """Finalize stored_items after all pages of a sync complete."""


class _CalendarListItemUpdater:
    """Applies calendar list sync pages to local store items."""

    def reset(self) -> None:
        """Reset per-sync state."""

    def update(
        self, stored_items: dict[str, Any], result: CalendarListResponse
    ) -> None:
        """Apply a page of synced calendars to stored_items."""
        for item in result.items:
            if not item.id:
                continue
            stored_items[item.id] = _serialize_item(item)

    def finalize(self, stored_items: dict[str, Any]) -> None:
        """Finalize stored_items after all pages complete."""


class _EventItemUpdater:
    """Applies event sync pages to local store items, pruning cancelled events."""

    def __init__(self) -> None:
        """Initialize per-sync tracking state."""
        self._cancelled_ids: set[str] = set()
        self._active_ids: set[str] = set()

    def reset(self) -> None:
        """Reset per-sync tracking state before retrying a full sync."""
        self._cancelled_ids.clear()
        self._active_ids.clear()

    def update(
        self, stored_items: dict[str, Any], result: _ListEventsResponseModel
    ) -> None:
        """Apply a page of synced events to stored_items."""
        for item in result.items:
            if not item.id:
                continue
            if item.status == EventStatusEnum.CANCELLED:
                if item.recurring_event_id and item.original_start_time:
                    # Keep minimal cancelled exception until finalize() checks
                    # whether its parent recurring event is still active.
                    stored_items[item.id] = _serialize_cancelled_exception(item)
                else:
                    stored_items.pop(item.id, None)
                    self._cancelled_ids.add(item.id)
                self._active_ids.discard(item.id)
            else:
                stored_items[item.id] = _serialize_item(item)
                self._active_ids.add(item.id)
                self._cancelled_ids.discard(item.id)

    def finalize(self, stored_items: dict[str, Any]) -> None:
        """Remove stale cancelled events and orphaned exceptions after all pages."""
        to_delete: list[str] = []
        for item_id, data in stored_items.items():
            recurring_event_id = data.get("recurring_event_id")
            parent = (
                stored_items.get(recurring_event_id) if recurring_event_id else None
            )
            if data.get("status") == EventStatusEnum.CANCELLED:
                if (
                    not recurring_event_id
                    or not data.get("original_start_time")
                    or parent is None
                    or parent.get("status") == EventStatusEnum.CANCELLED
                ):
                    to_delete.append(item_id)
            elif (
                recurring_event_id
                and item_id not in self._active_ids
                and (
                    recurring_event_id in self._cancelled_ids
                    or (
                        parent is not None
                        and parent.get("status") == EventStatusEnum.CANCELLED
                    )
                )
            ):
                to_delete.append(item_id)

        for item_id in to_delete:
            stored_items.pop(item_id, None)


async def _run_sync[T: SyncableRequest, S: SyncableResponse](
    store_data: dict[str, Any],
    new_request: Callable[[str | None], T],
    api_call: Callable[[T], Awaitable[S]],
    updater: _SyncItemUpdater[S],
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
            updater.reset()
            return await _run_sync(store_data, new_request, api_call, updater)

        updater.update(store_data[ITEMS], result)

        if not result.page_token:
            if not result.sync_token:
                raise InvalidSyncTokenException(
                    "Unexpected API response, missing sync_token"
                )
            updater.finalize(store_data[ITEMS])
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
            store_data,
            new_request,
            self._api.async_list_calendars,
            _CalendarListItemUpdater(),
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
            store_data,
            new_request,
            self._api.async_list_events_page,
            _EventItemUpdater(),
        )
        await self._store.async_save(store_data)
