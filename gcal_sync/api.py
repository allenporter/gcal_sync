"""Client library for talking to Google APIs."""

from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Any, Optional

from googleapiclient import discovery as google_discovery
from pydantic import BaseModel, Field, root_validator

from .auth import AbstractAuth
from .model import Calendar, Event, EVENT_FIELDS

_LOGGER = logging.getLogger(__name__)


EVENT_PAGE_SIZE = 100
# pylint: disable=line-too-long
EVENT_API_FIELDS = f"kind,nextPageToken,nextSyncToken,items({EVENT_FIELDS})"


class CalendarListResponse(BaseModel):
    """Api response containing a list of calendars."""

    items: list[Calendar] = []
    page_token: Optional[str] = Field(default=None, alias="nextPageToken")
    sync_token: Optional[str] = Field(default=None, alias="nextSyncToken")


def now() -> datetime.datetime:
    """Helper method to facilitate mocking in tests."""
    return datetime.datetime.now(datetime.timezone.utc)


class ListEventsRequest(BaseModel):
    """Api request to list events."""

    calendar_id: str = Field(alias="calendarId")
    start_time: datetime.datetime = Field(default_factory=now, alias="timeMin")
    end_time: Optional[datetime.datetime] = Field(default=None, alias="timeMax")
    search: Optional[str] = Field(default=None, alias="q")
    page_token: Optional[str] = Field(default=None, alias="pageToken")

    @root_validator
    def check_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        if start_time := values.get("start_time"):
            values["start_time"] = start_time.replace(microsecond=0)
        if end_time := values.get("end_time"):
            values["end_time"] = end_time.replace(microsecond=0)
        return values

    class Config:
        """Model configuration."""
        allow_population_by_field_name = True


class ListEventsResponse(BaseModel):
    """Api response containing a list of events."""

    items: list[Event] = Field(default=[], alias="items")
    sync_token: Optional[str] = Field(default=None, alias="nextSyncToken")
    page_token: Optional[str] = Field(default=None, alias="nextPageToken")


class GoogleCalendarService:
    """Calendar service interface to Google."""

    def __init__(
        self,
        loop: asyncio.AbstractEventLoop,
        auth: AbstractAuth,
    ) -> None:
        """Init the Google Calendar service."""
        self._loop = loop
        self._auth = auth

    async def _async_get_service(self) -> google_discovery.Resource:
        """Get the calendar service with valid credetnails."""
        creds = await self._auth.async_get_creds()

        def _build() -> google_discovery.Resource:
            return google_discovery.build(
                "calendar", "v3", credentials=creds, cache_discovery=False
            )

        return await self._loop.run_in_executor(None, _build)

    async def async_list_calendars(
        self,
    ) -> CalendarListResponse:
        """Return the list of calendars the user has added to their list."""
        service = await self._async_get_service()

        def _list_calendars() -> CalendarListResponse:
            cal_list = service.calendarList()
            result = cal_list.list().execute()
            _LOGGER.debug("List calendars response: %s", result)
            return CalendarListResponse.parse_obj(result)

        return await self._loop.run_in_executor(None, _list_calendars)

    async def async_create_event(
        self,
        calendar_id: str,
        event: Event,
    ) -> None:
        """Create an event on the specified calendar."""
        service = await self._async_get_service()

        def _create_event() -> None:
            events = service.events()
            body = json.loads(event.json(exclude_unset=True, by_alias=True))
            events.insert(calendarId=calendar_id, body=body).execute()

        return await self._loop.run_in_executor(None, _create_event)

    async def async_list_events(
        self,
        request: ListEventsRequest,
    ) -> ListEventsResponse:
        """Return the list of events."""
        service = await self._async_get_service()
        params = json.loads(request.json(exclude_none=True, by_alias=True))

        def _list_events() -> ListEventsResponse:
            events = service.events()
            result = events.list(
                **params,
                maxResults=EVENT_PAGE_SIZE,
                singleEvents=True,  # Flattens recurring events
                orderBy="startTime",
                fields=EVENT_API_FIELDS,
            ).execute()
            _LOGGER.debug("List event response: %s", result)
            return ListEventsResponse.parse_obj(result)

        return await self._loop.run_in_executor(None, _list_events)
