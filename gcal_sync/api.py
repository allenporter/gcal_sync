"""Client library for talking to Google APIs."""

from __future__ import annotations

import datetime
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, List, Optional
from urllib.request import pathname2url

from pydantic import BaseModel, Field, root_validator

from .auth import AbstractAuth
from .const import ITEMS
from .model import EVENT_FIELDS, Calendar, Event, EventStatusEnum
from .store import CalendarStore

_LOGGER = logging.getLogger(__name__)


EVENT_PAGE_SIZE = 100
# pylint: disable=line-too-long
EVENT_API_FIELDS = f"kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"

CALENDAR_ID = "calendarId"
CALENDAR_LIST_URL = "users/me/calendarList"
CALENDAR_GET_URL = "calendars/{calendar_id}"
CALENDAR_EVENTS_URL = "calendars/{calendar_id}/events"


class SyncableRequest(BaseModel):
    """Base class for a request that supports sync."""

    page_token: Optional[str] = Field(default=None, alias="pageToken")
    sync_token: Optional[str] = Field(default=None, alias="syncToken")


class SyncableResponse(BaseModel):
    """Base class for an API response that supports sync."""

    page_token: Optional[str] = Field(default=None, alias="nextPageToken")
    sync_token: Optional[str] = Field(default=None, alias="nextSyncToken")


class CalendarListRequest(SyncableRequest):
    """Api request to return a list of calendars."""


class CalendarListResponse(SyncableResponse):
    """Api response containing a list of calendars."""

    items: List[Calendar] = []
    page_token: Optional[str] = Field(default=None, alias="nextPageToken")
    sync_token: Optional[str] = Field(default=None, alias="nextSyncToken")


def now() -> datetime.datetime:
    """Helper method to facilitate mocking in tests."""
    return datetime.datetime.now(datetime.timezone.utc)


def _validate_datetime(values: dict[str, Any], key: str) -> dict[str, Any]:
    """Validate date/datetime request fields are set properly."""
    if time := values.get(key):
        values[key] = time.replace(microsecond=0)
    return values


def _validate_datetimes(values: dict[str, Any]) -> dict[str, Any]:
    """Validate the date or datetime fields are set properly."""
    values = _validate_datetime(values, "start_time")
    values = _validate_datetime(values, "end_time")
    return values


class ListEventsRequest(SyncableRequest):
    """Api request to list events."""

    calendar_id: str = Field(alias="calendarId")
    start_time: datetime.datetime = Field(default=None, alias="timeMin")
    end_time: Optional[datetime.datetime] = Field(default=None, alias="timeMax")
    search: Optional[str] = Field(default=None, alias="q")

    @root_validator
    def check_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        return _validate_datetimes(values)

    class Config:
        """Model configuration."""

        allow_population_by_field_name = True


class _ListEventsResponseModel(SyncableResponse):
    """Api response containing a list of events."""

    items: List[Event] = []


class ListEventsResponse:
    """Api response containing a list of events."""

    def __init__(
        self,
        model: _ListEventsResponseModel,
        get_next_page: Callable[[str | None], Awaitable[_ListEventsResponseModel]]
        | None = None,
    ) -> None:
        """initialize ListEventsResponse."""
        self._model = model
        self._get_next_page = get_next_page

    @property
    def items(self) -> list[Event]:
        """Return the calendar event items in the response."""
        return self._model.items

    @property
    def sync_token(self) -> str | None:
        """Return the sync token in the response."""
        return self._model.sync_token

    @property
    def page_token(self) -> str | None:
        """Return the page token in the response."""
        return self._model.page_token

    async def __aiter__(self) -> AsyncIterator[ListEventsResponse]:
        """Async iterator to traverse through pages of responses."""
        response = self
        while response is not None:
            yield response
            if not response.page_token or not self._get_next_page:
                break
            page_result = await self._get_next_page(response.page_token)
            response = ListEventsResponse(page_result)


class GoogleCalendarService:
    """Calendar service interface to Google."""

    def __init__(
        self,
        auth: AbstractAuth,
    ) -> None:
        """Init the Google Calendar service."""
        self._auth = auth

    async def async_list_calendars(
        self, request: CalendarListRequest | None = None
    ) -> CalendarListResponse:
        """Return the list of calendars the user has added to their list."""
        params = {}
        if request:
            params = json.loads(request.json(exclude_none=True, by_alias=True))
        result = await self._auth.get_json(CALENDAR_LIST_URL, params=params)
        return CalendarListResponse.parse_obj(result)

    async def async_get_calendar(self, calendar_id: str) -> Calendar:
        """Return the calendar with the specified id."""
        result = await self._auth.get_json(
            CALENDAR_GET_URL.format(calendar_id=calendar_id)
        )
        return Calendar.parse_obj(result)

    async def async_create_event(
        self,
        calendar_id: str,
        event: Event,
    ) -> None:
        """Create an event on the specified calendar."""
        body = json.loads(
            event.json(exclude_unset=True, by_alias=True, exclude={"calendar_id"})
        )
        await self._auth.post(
            CALENDAR_EVENTS_URL.format(calendar_id=pathname2url(calendar_id)), json=body
        )

    async def async_list_events(
        self,
        request: ListEventsRequest,
    ) -> ListEventsResponse:
        """Return the list of events."""

        async def get_next_page(page_token: str | None) -> _ListEventsResponseModel:
            if page_token is not None:
                request.page_token = page_token
            return await self.async_list_events_page(request)

        page_result = await get_next_page(None)
        result = ListEventsResponse(page_result, get_next_page)
        return result

    async def async_list_events_page(
        self,
        request: ListEventsRequest,
    ) -> _ListEventsResponseModel:
        """Return the list of events."""
        params = {
            "maxResults": EVENT_PAGE_SIZE,
            "singleEvents": "true",
            "orderBy": "startTime",
            "fields": EVENT_API_FIELDS,
        }
        if not request.start_time and not request.sync_token:
            request.start_time = now()
        params.update(
            json.loads(
                request.json(exclude_none=True, by_alias=True, exclude={"calendar_id"})
            )
        )
        result = await self._auth.get_json(
            CALENDAR_EVENTS_URL.format(calendar_id=pathname2url(request.calendar_id)),
            params=params,
        )
        _ListEventsResponseModel.update_forward_refs()
        return _ListEventsResponseModel.parse_obj(result)


class LocalCalendarListResponse(BaseModel):
    """Api response containing a list of calendars."""

    calendars: List[Calendar] = []


class LocalListEventsRequest(BaseModel):
    """Api request to list events."""

    start_time: datetime.datetime = Field(default_factory=now)
    end_time: Optional[datetime.datetime] = Field(default=None)

    @root_validator
    def check_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        return _validate_datetimes(values)

    class Config:
        """Model configuration."""

        allow_population_by_field_name = True


class LocalListEventsResponse(BaseModel):
    """Api response containing a list of events."""

    events: List[Event] = Field(default=[])


class CalendarListStoreService:
    """Performs calendar list lookups from the local store."""

    def __init__(self, store: CalendarStore) -> None:
        """Initialize CalendarEventStoreService."""
        self._store = store

    async def async_list_calendars(
        self,
    ) -> LocalCalendarListResponse:
        """Return the set of events matching the criteria."""
        store_data = await self._store.async_load() or {}
        store_data.setdefault(ITEMS, {})
        items = store_data.get(ITEMS, {})

        return LocalCalendarListResponse(
            calendars=[Calendar.parse_obj(item) for item in items.values()]
        )


class CalendarEventStoreService:
    """Performs event lookups from the local store."""

    def __init__(self, store: CalendarStore) -> None:
        """Initialize CalendarEventStoreService."""
        self._store = store

    async def async_list_events(
        self,
        request: LocalListEventsRequest,
    ) -> LocalListEventsResponse:
        """Return the set of events matching the criteria."""

        store_data = await self._store.async_load() or {}
        store_data.setdefault(ITEMS, {})
        events_data = store_data.get(ITEMS, {})

        events = []
        for event_data in events_data.values():
            event = Event.parse_obj(event_data)
            if event.status == EventStatusEnum.CANCELLED:
                continue
            if request.start_time:
                if event.end.date and request.start_time.date() > event.end.date:
                    continue
                if (
                    isinstance(event.end.value, datetime.datetime)
                    and request.start_time > event.end.value
                ):
                    continue
            if request.end_time:
                if event.start.date and request.end_time.date() < event.start.date:
                    continue
                if (
                    isinstance(event.start.value, datetime.datetime)
                    and request.end_time < event.start.value
                ):
                    continue
            events.append(event)
        return LocalListEventsResponse(events=events)
