"""Library for handling local even sync."""
# pylint: disable=duplicate-code
import datetime
import logging
from typing import Any, List, Optional

from pydantic import BaseModel, Field, root_validator

from .api import GoogleCalendarService, ListEventsRequest
from .exceptions import InvalidSyncTokenException
from .model import Event, validate_datetimes
from .store import CalendarStore, ScopedCalendarStore

_LOGGER = logging.getLogger(__name__)

EVENT_SYNC = "event_sync"
EVENTS = "events"
TIMEZONE = "timezone"
SYNC_TOKEN = "sync_token"


def now() -> datetime.datetime:
    """Helper method to facilitate mocking in tests."""
    return datetime.datetime.now(datetime.timezone.utc)


class LookupEventsRequest(BaseModel):
    """Api request to list events."""

    start_time: datetime.datetime = Field(default_factory=now)
    end_time: Optional[datetime.datetime] = Field(default=None)

    @root_validator
    def check_datetime(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the date or datetime fields are set properly."""
        return validate_datetimes(values)

    class Config:
        """Model configuration."""

        allow_population_by_field_name = True


class LookupEventsResponse(BaseModel):
    """Api response containing a list of events."""

    events: List[Event] = Field(default=[])


class EventSyncManager:
    """Manages synchronizing events from API to local store."""

    def __init__(
        self, api: GoogleCalendarService, calendar_id: str, store: CalendarStore
    ) -> None:
        """Initialize EventSyncManager."""
        self._api = api
        self._store = ScopedCalendarStore(
            ScopedCalendarStore(store, EVENT_SYNC), calendar_id
        )
        self._calendar_id = calendar_id

    async def run(self) -> None:
        """Run the event sync manager."""

        store_data = await self._store.async_load() or {}
        store_data.setdefault(EVENTS, {})

        # Load sync token from last execution if any
        sync_token = store_data.get(SYNC_TOKEN)
        request = ListEventsRequest(calendar_id=self._calendar_id)
        if not sync_token:
            _LOGGER.debug(
                "Performing full calendar sync for calendar %s", self._calendar_id
            )
            # Sync at most 4 weeks of prior events
            request.start_time = datetime.datetime.now() - datetime.timedelta(days=28)
        else:
            _LOGGER.debug(
                "Performing incremental sync for calendar %s (%s)",
                self._calendar_id,
                sync_token,
            )
            request.sync_token = sync_token

        while True:
            try:
                result = await self._api.async_list_events(request)
            except InvalidSyncTokenException:
                _LOGGER.debug("Invalidating sync token")
                store_data[SYNC_TOKEN] = None
                store_data[EVENTS] = {}
                await self._store.async_save(store_data)
                await self.run()
                return

            store_data[EVENTS].update({item.id: item for item in result.items})

            if result.timezone:
                store_data[TIMEZONE] = result.timezone

            if not result.page_token:
                store_data[SYNC_TOKEN] = result.sync_token
                break
            request.page_token = result.page_token

        await self._store.async_save(store_data)

    async def async_lookup_events(
        self,
        request: LookupEventsRequest,
    ) -> LookupEventsResponse:
        """Return the set of events matching the criteria."""

        store_data = await self._store.async_load() or {}
        store_data.setdefault(EVENTS, {})
        events_data = store_data.get(EVENTS, {})

        events = []
        for event_data in events_data.values():
            event = Event.parse_obj(event_data)
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
        return LookupEventsResponse(events=events)
