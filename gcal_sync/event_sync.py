"""Library for handling local even sync."""
# pylint: disable=duplicate-code
import datetime
import logging

from .api import CalendarEventStoreService, GoogleCalendarService, ListEventsRequest
from .const import EVENT_SYNC, ITEMS, SYNC_TOKEN, SYNC_TOKEN_VERSION, TIMEZONE
from .exceptions import InvalidSyncTokenException
from .store import CalendarStore, ScopedCalendarStore

_LOGGER = logging.getLogger(__name__)


# Can be incremented to blow away existing store
VERSION = 1


class CalendarEventSyncManager:
    """Manages synchronizing events from API to local store."""

    def __init__(
        self, api: GoogleCalendarService, calendar_id: str, store: CalendarStore
    ) -> None:
        """Initialize CalendarEventSyncManager."""
        self._api = api
        self._store = ScopedCalendarStore(
            ScopedCalendarStore(store, EVENT_SYNC), calendar_id
        )
        self._calendar_id = calendar_id

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

        store_data = await self._store.async_load() or {}
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
                store_data[ITEMS] = {}
                await self._store.async_save(store_data)
                await self.run()
                return

            store_data[ITEMS].update({item.id: item for item in result.items})

            if result.timezone:
                store_data[TIMEZONE] = result.timezone

            if not result.page_token:
                store_data[SYNC_TOKEN] = result.sync_token
                store_data[SYNC_TOKEN_VERSION] = VERSION
                break
            request.page_token = result.page_token

        await self._store.async_save(store_data)
