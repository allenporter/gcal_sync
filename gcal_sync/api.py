"""Client library for talking to Google APIs."""

from __future__ import annotations

import asyncio
import datetime
from typing import Optional

from googleapiclient import discovery as google_discovery
from pydantic import BaseModel, Field

from .auth import AbstractAuth
from .model import Calendar, Event

EVENT_PAGE_SIZE = 100


def _api_time_format(date_time: datetime.datetime | None) -> str | None:
    """Convert a datetime to the api string format."""
    return date_time.isoformat("T") if date_time else None


class CalendarListResponse(BaseModel):
    """Api response containing a list of calendars."""

    items: list[Calendar] = []


class ListEventsRequest(BaseModel):
    """Api request to list events."""

    calendar_id: str
    start_time: Optional[datetime.datetime] = None
    end_time: Optional[datetime.datetime] = None
    search: Optional[str] = None
    page_token: Optional[str] = None


class ListEventsResponse(BaseModel):
    """Api response containing a list of events."""

    items: list[Event] = Field(default=[], alias="items")
    sync_token: Optional[str] = Field(default=None, alias="syncToken")
    page_token: Optional[str] = Field(default=None, alias="pageToken")


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
            body = event.dict(exclude_unset=True)
            events.insert(calendarId=calendar_id, body=body).execute()

        return await self._loop.run_in_executor(None, _create_event)

    async def async_list_events(
        self,
        request: ListEventsRequest,
    ) -> ListEventsResponse:
        """Return the list of events."""
        service = await self._async_get_service()

        def _list_events() -> ListEventsResponse:
            events = service.events()
            result = events.list(
                calendarId=request.calendar_id,
                timeMin=_api_time_format(
                    request.start_time
                    if request.start_time
                    else datetime.datetime.now()
                ),
                timeMax=_api_time_format(request.end_time),
                q=request.search,
                maxResults=EVENT_PAGE_SIZE,
                pageToken=request.page_token,
                singleEvents=True,  # Flattens recurring events
                orderBy="startTime",
            ).execute()
            return ListEventsResponse.parse_obj(result)

        return await self._loop.run_in_executor(None, _list_events)
