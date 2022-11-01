"""Client library for talking to Google APIs.

This is the primary class to use when talking to Google. This library defines
the API service `GoogleCalendarService` as well as the request and response messages
for things like listing the available calendars, or events on a calendar.

This library also contains apis for local storage of calendars an events in
`CalendarListStoreService` and `CalendarEventStoreService`.  See the `sync`
library for more details on how to
async down calendars and events to local storage.

All of the request and response messages here use [pydantic](https://pydantic-docs.helpmanual.io/)
for parsing and valdation of the constraints of the API. The API fields in the request and
response methods are mirroring the Google Calendar API methods, so see the
[reference](https://developers.google.com/calendar/api/v3/reference) for details.
"""

from __future__ import annotations

import datetime
import enum
import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, List, Optional, cast
from urllib.request import pathname2url

from pydantic import BaseModel, Field, ValidationError, root_validator, validator

from .auth import AbstractAuth
from .const import ITEMS
from .exceptions import ApiException
from .model import EVENT_FIELDS, Calendar, Event
from .store import CalendarStore
from .timeline import Timeline, calendar_timeline

__all__ = [
    "GoogleCalendarService",
    "CalendarListStoreService",
    "CalendarEventStoreService",
    "CalendarListRequest",
    "CalendarListResponse",
    "ListEventsRequest",
    "SyncEventsRequest",
    "ListEventsResponse",
    "LocalCalendarListResponse",
    "LocalListEventsRequest",
    "LocalListEventsResponse",
    "Boolean",
]


_LOGGER = logging.getLogger(__name__)


EVENT_PAGE_SIZE = 1000
# pylint: disable=line-too-long
EVENT_API_FIELDS = f"kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"

CALENDAR_ID = "calendarId"
CALENDAR_LIST_URL = "users/me/calendarList"
CALENDAR_GET_URL = "calendars/{calendar_id}"
CALENDAR_EVENTS_URL = "calendars/{calendar_id}/events"


class SyncableRequest(BaseModel):
    """Base class for a request that supports sync."""

    page_token: Optional[str] = Field(default=None, alias="pageToken")
    """Token specifying which result page to return."""

    sync_token: Optional[str] = Field(default=None, alias="syncToken")
    """Token obtained from the last page of results of a previous request."""


class SyncableResponse(BaseModel):
    """Base class for an API response that supports sync."""

    page_token: Optional[str] = Field(default=None, alias="nextPageToken")
    """Token used to access the next page of this results."""

    sync_token: Optional[str] = Field(default=None, alias="nextSyncToken")
    """Token used at a later point in time to retrieve entries changed."""


class CalendarListRequest(SyncableRequest):
    """Api request to return a list of calendars."""


class CalendarListResponse(SyncableResponse):
    """Api response containing a list of calendars."""

    items: List[Calendar] = []
    """The calendars on the user's calendar list."""


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
    """Calendar identifier."""

    start_time: Optional[datetime.datetime] = Field(default=None, alias="timeMin")
    """Lower bound (exclusive) for an event's end time to filter by."""

    end_time: Optional[datetime.datetime] = Field(default=None, alias="timeMax")
    """Upper bound (exclusive) for an event's start time to filter by."""

    search: Optional[str] = Field(default=None, alias="q")
    """Free text search terms to find events that match these terms

    This matches the summary, description, location, attendee's displayName,
    attendee's email.
    """

    def to_request(self) -> _RawListEventsRequest:
        """Convert to the raw API request for sending to the API."""
        return _RawListEventsRequest(
            **json.loads(self.json(exclude_none=True, by_alias=True)),
            single_events=Boolean.TRUE,
            order_by=OrderBy.START_TIME,
        )

    @validator("start_time", always=True)
    def _default_start_time(cls, value: datetime.datetime | None) -> datetime.datetime:
        """Select a default start time value of not specified."""
        if value is None:
            return now()
        return value

    @root_validator
    def _check_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        return _validate_datetimes(values)

    class Config:
        """Pydantic model configuration."""

        allow_population_by_field_name = True


class SyncEventsRequest(ListEventsRequest):
    """Api request to list events when used in the context of sync.

    This differs from a normal ListEventsRequest in that it handles differences between
    initial sync and follow up syncs with a sync token (which has fewer fields allowed). This
    also does not expand recurring events into single events since the local event store
    handles this.
    """

    def to_request(self) -> _RawListEventsRequest:
        """Disables default value behavior."""
        return _RawListEventsRequest(
            **json.loads(self.json(exclude_none=True, by_alias=True))
        )

    @validator("start_time", always=True)
    def _default_start_time(cls, value: datetime.datetime) -> datetime.datetime:
        """Disables default value behavior."""
        return value


class OrderBy(str, enum.Enum):
    """Represents the order of events returned."""

    START_TIME = "startTime"
    """Order events by start time."""

    UPDATED = "updated"
    """Order by event update time."""


class Boolean(str, enum.Enum):
    "Hack to support custom json encoding in pydantic." ""

    TRUE = "true"
    FALSE = "false"


class _RawListEventsRequest(BaseModel):
    """Api request to list events.

    This is used internally to have separate validation between list event requests
    and sync requests.
    """

    calendar_id: str = Field(alias="calendarId")
    max_results: int = Field(default=EVENT_PAGE_SIZE, alias="maxResults")
    single_events: Optional[Boolean] = Field(alias="singleEvents")
    order_by: Optional[OrderBy] = Field(alias="orderBy")
    fields: str = Field(default=EVENT_API_FIELDS)
    page_token: Optional[str] = Field(default=None, alias="pageToken")
    sync_token: Optional[str] = Field(default=None, alias="syncToken")
    start_time: Optional[datetime.datetime] = Field(default=None, alias="timeMin")
    end_time: Optional[datetime.datetime] = Field(default=None, alias="timeMax")
    search: Optional[str] = Field(default=None, alias="q")

    def as_dict(self) -> dict[str, Any]:
        """Return the object as a json dict."""
        return cast(
            dict[str, Any],
            json.loads(
                self.json(exclude_none=True, by_alias=True, exclude={"calendar_id"})
            ),
        )

    @root_validator
    def check_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        return _validate_datetimes(values)

    @root_validator
    def check_sync_token_fields(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the set of fields present when using a sync token."""
        if not values.get("sync_token"):
            return values
        if (
            values.get("order_by")
            or values.get("search")
            or values.get("time_min")
            or values.get("time_max")
        ):
            raise ValueError(
                f"Specified request params not compatible with sync_token: {values}"
            )
        return values

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
    """Calendar service interface to Google.

    The `GoogleCalendarService` is the primary API service for this library. It supports
    operations like listing calendars, or events.
    """

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
        """Return the list of events.

        This is primarily intended to be an internal method used to page through
        events using the async generator provided by `async_list_events`.
        """
        params = request.to_request().as_dict()
        result = await self._auth.get_json(
            CALENDAR_EVENTS_URL.format(calendar_id=pathname2url(request.calendar_id)),
            params=params,
        )
        _ListEventsResponseModel.update_forward_refs()
        try:
            return _ListEventsResponseModel.parse_obj(result)
        except ValidationError as err:
            _LOGGER.debug("Unable to parse result: %s", result)
            raise ApiException("Error parsing API response") from err


class LocalCalendarListResponse(BaseModel):
    """Api response containing a list of calendars."""

    calendars: List[Calendar] = []
    """The list of calendars."""


class LocalListEventsRequest(BaseModel):
    """Api request to list events from the local event store."""

    start_time: datetime.datetime = Field(default_factory=now)
    """Lower bound (exclusive) for an event's end time to filter by."""

    end_time: Optional[datetime.datetime] = Field(default=None)
    """Upper bound (exclusive) for an event's start time to filter by."""

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
    """Events returned from the local store."""


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

        timeline = await self.async_get_timeline()

        if request.end_time:
            return LocalListEventsResponse(
                events=list(
                    timeline.overlapping(
                        request.start_time,
                        request.end_time,
                    )
                )
            )
        return LocalListEventsResponse(
            events=list(timeline.active_after(request.start_time))
        )

    async def async_get_timeline(
        self, tzinfo: datetime.tzinfo | None = None
    ) -> Timeline:
        """Get the timeline of events."""
        store_data = await self._store.async_load() or {}
        store_data.setdefault(ITEMS, {})
        events_data = store_data.get(ITEMS, {})
        _LOGGER.debug("Created timeline of %d events", len(events_data))
        return calendar_timeline(
            [Event.parse_obj(data) for data in events_data.values()],
            tzinfo if tzinfo else datetime.timezone.utc,
        )
