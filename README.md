An asyncio python library for the [Google Calendar API](https://developers.google.com/calendar/api). This library provides a simplified
Google Calendar API that is lighter weight and more streamlined compared to using
aiogoogle, and increased reliability by supporting efficient sync and reading
from local storage. See the [API Documentation](https://allenporter.github.io/gcal_sync/).

The focus of this API is on making it simple to access the most relevant parts of Google
Calendar, for doing useful things. It may not support everything in the API however it
should be easy to extend to do more as needed.

# Quickstart

In order to use the library, you'll need to do some work yourself to get authentication
credentails. This depends a lot on the context (e.g. redirecting to use OAuth via web)
but should be easy to incorporate using Google's python authentication libraries. See
Google's [Authentication and authorization overview](https://developers.google.com/workspace/guides/auth-overview) for details.

You will implement `gcal_sync.AbstractAuth` to provide an access token. Your implementation
will handle any necessary refreshes. You can invoke the service with your auth implentation
to access the API.

```python
from gcal_sync.auth import AbstractAuth


class MyAuthImpl(gcal_sync.AbstractAuth):

    def __init__(self, websession: aiohttp.ClientSession) -> None:
        """Initialize MyAuthimpl."""
        super().__init__(websession)

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""
        return ...


service = GoogleCalendarService(MyAuthImpl(...))
calendar = await service.async_get_calendar("primary")
```

See `gcal_sync.api.GoogleCalendarService` for more details on API calls and see the
overall [documentation](https://allenporter.github.io/gcal_sync/)

# Fetching Events

Events can be fetched using the `gcal_sync.api.ListEventsRequest` which can filter
events based on time or search criteria. The `GoogleCalendarService` supports paging
through events using an aync generator like in this example below:

```python
from gcal_sync.api import ListEventsRequest

request = ListEventsRequest(
    calendar_id=calendar.id,
    search="Holiday",
)
result = await service.async_list_events(request)
async for result_page in result:
    for event in result_page.items:
        print(event.summary)
```

Using the async generator avoids the need to manually handle paging and page tokens,
but that is also available if needed. Recurring events are expanded on the server by
default, so you don't have to worry about handling them yourself.

# Synchronization

If you require a high read rate to the events, then it may be more efficient to
first sync down the calendar then query local events. Any recurring events are
expanded at query time by the local library by interpreting the recurrence rules
on the synced event.

```python
from gcal_sync.sync import CalendarListSyncManager

sync = CalendarEventSyncManager(service)
# Run when you want to sync down the latest set of events
await sync.run()

# Iterate over events in the local store
timeline = await sync.store_service.async_get_timeline()
for event in timeline:
    print(event.summary)
```

See `gcal_sync.sync` for more details.

# Development Environment

```bash
$ python3 -m venv venv
$ source venv/bin/activate
$ pip3 install -r requirements.txt

# Run tests
$ py.test

# Run tests with code coverage
$ py.test --cov-report=term-missing --cov=gcal_sync
```
