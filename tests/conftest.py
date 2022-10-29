"""Test fixtures for calendar API."""
from __future__ import annotations

import asyncio
import datetime
import json
from collections.abc import Awaitable, Callable
from json import JSONDecodeError
from typing import Any, Generator, List, TypeVar, cast

import aiohttp
import pytest
from aiohttp.test_utils import TestClient

from gcal_sync.api import GoogleCalendarService, LocalListEventsRequest
from gcal_sync.auth import AbstractAuth
from gcal_sync.store import CalendarStore, InMemoryCalendarStore
from gcal_sync.sync import CalendarEventSyncManager, CalendarListSyncManager

CALENDAR_ID = "some-calendar-id"


ResponseResult = Callable[[aiohttp.web.Response], None]
ApiResult = Callable[[dict[str, Any]], None]
ApiRequest = Callable[[], list[dict[str, Any]]]
_T = TypeVar("_T")
YieldFixture = Generator[_T, None, None]


class FakeAuth(AbstractAuth):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractAuth for use in tests."""

    async def async_get_access_token(self) -> str:
        """Return an OAuth credential for the calendar API."""
        return "some-token"


class RefreshingAuth(AbstractAuth):
    """Implementaiton of AbstractAuth for sending RPCs."""

    def __init__(self, test_client: TestClient) -> None:
        super().__init__(cast(aiohttp.ClientSession, test_client), "")

    async def async_get_access_token(self) -> str:
        resp = await self._websession.request("get", "/refresh-auth")
        resp.raise_for_status()
        json_value = await resp.json()
        assert isinstance(json_value["token"], str)
        return json_value["token"]


@pytest.fixture(name="event_loop")
def create_event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Fixture for producing event loop."""
    yield asyncio.get_event_loop()


async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Handles the request, inserting response prepared by tests."""
    if request.method != "GET":
        try:
            request.app["request-json"].append(await request.json())
        except JSONDecodeError as err:
            print(err)
        request.app["request-post"].append(dict(await request.post()))
    response = aiohttp.web.json_response()
    if len(request.app["response"]) > 0:
        response = request.app["response"].pop(0)
    url = request.url.path
    if request.query_string:
        url += f"?{request.query_string}"
    request.app["request"].append(url)
    return response


@pytest.fixture
async def request_handler() -> Callable[
    [aiohttp.web.Request], Awaitable[aiohttp.web.Response]
]:
    """A fake request handler."""
    return handler


@pytest.fixture(name="app")
def mock_app() -> aiohttp.web.Application:
    """Fixture to create the fake web app."""
    app = aiohttp.web.Application()
    app["response"] = []
    app["request"] = []
    app["request-json"] = []
    app["request-post"] = []

    app.router.add_get("/users/me/calendarList", handler)
    app.router.add_get("/calendars/{calendarId}", handler)

    app.router.add_get("/calendars/{calendarId}/events", handler)
    app.router.add_post("/calendars/{calendarId}/events", handler)

    app.router.add_get("/calendars/{calendarId}/events/{eventId}", handler)
    app.router.add_put("/calendars/{calendarId}/events/{eventId}", handler)
    app.router.add_patch("/calendars/{calendarId}/events/{eventId}", handler)
    app.router.add_delete("/calendars/{calendarId}/events/{eventId}", handler)
    return app


@pytest.fixture(name="test_client")
def cli_cb(
    event_loop: asyncio.AbstractEventLoop,
    app: aiohttp.web.Application,
    aiohttp_client: Callable[[aiohttp.web.Application], Awaitable[TestClient]],
) -> Callable[[], Awaitable[TestClient]]:
    """Creates a fake aiohttp client."""

    async def func() -> TestClient:
        return await aiohttp_client(app)

    return func


@pytest.fixture(name="auth_client")
def mock_auth_client(
    test_client: Callable[[], Awaitable[TestClient]]
) -> Callable[[str], Awaitable[FakeAuth]]:
    """Fixture to fake out the auth library."""

    async def func(host: str) -> FakeAuth:
        client = await test_client()
        return FakeAuth(cast(aiohttp.ClientSession, client), host)

    return func


@pytest.fixture(name="refreshing_auth_client")
async def mock_refreshing_auth_client(
    test_client: Callable[[], Awaitable[TestClient]],
) -> Callable[[], Awaitable[AbstractAuth]]:
    """Fixture to run an auth client that sends rpcs."""

    async def _make_auth() -> AbstractAuth:
        return RefreshingAuth(await test_client())

    return _make_auth


@pytest.fixture(name="calendar_service_cb")
def mock_calendar_service(
    auth_client: Callable[[str], Awaitable[FakeAuth]]
) -> Callable[[], Awaitable[GoogleCalendarService]]:
    """Fixture to fake out the api service."""

    async def func() -> GoogleCalendarService:
        auth = await auth_client("")
        return GoogleCalendarService(auth)

    return func


@pytest.fixture(name="response")
def mock_response(app: aiohttp.web.Application) -> ResponseResult:
    """Fixture to construct a fake API response."""

    def _put_result(response: aiohttp.web.Response) -> None:
        app["response"].append(response)

    return _put_result


@pytest.fixture(name="json_response")
def mock_json_response(response: ResponseResult) -> ApiResult:
    """Fixture to construct a fake API response."""

    def _put_result(data: dict[str, Any]) -> None:
        response(aiohttp.web.json_response(data))

    return _put_result


@pytest.fixture(name="request_reset")
def mock_request_reset(app: aiohttp.web.Application) -> Callable[[], None]:
    """Reset the request/response fixtures."""

    def _reset() -> None:
        app["request"].clear()
        app["response"].clear()
        app["request-json"].clear()
        app["request-post"].clear()

    return _reset


@pytest.fixture(name="url_request")
def mock_url_request(app: aiohttp.web.Application) -> Callable[[], list[str]]:
    """Fixture to return the requested url."""

    def _get_request() -> list[str]:
        return cast(List[str], app["request"])

    return _get_request


@pytest.fixture(name="json_request")
def mock_json_request(app: aiohttp.web.Application) -> ApiRequest:
    """Fixture to return the received request."""

    def _get_request() -> list[dict[str, Any]]:
        return cast(List[dict[str, Any]], app["request-json"])

    return _get_request


@pytest.fixture(name="post_body")
def mock_post_body(app: aiohttp.web.Application) -> Callable[[], list[str]]:
    """Fixture to return the recieved post body."""

    def _get_request() -> list[str]:
        return cast(List[str], app["request-post"])

    return _get_request


class JsonStore(CalendarStore):
    """Store that asserts objects can be serialized as json."""

    def __init__(self) -> None:
        self._data = "{}"

    async def async_load(self) -> dict[str, Any] | None:
        """Load data."""
        return cast(dict[str, Any], json.loads(self._data))

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data."""
        self._data = json.dumps(data)


@pytest.fixture(
    name="store",
    params=["json", "in-memory"],
    ids=["json-store", "in-memory-store"],
)
def fake_store(request: Any) -> CalendarStore:
    """Fixture that sets up the configuration used for the test."""
    if request.param == "json":
        return JsonStore()
    return InMemoryCalendarStore()


@pytest.fixture(name="calendar_list_sync_manager_cb")
def fake_calendar_list_sync_manager(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    store: CalendarStore,
) -> Callable[[], Awaitable[CalendarListSyncManager]]:
    """Fixture for an event sync manager."""

    async def func() -> CalendarListSyncManager:
        service = await calendar_service_cb()
        return CalendarListSyncManager(service, store)

    return func


@pytest.fixture(name="event_sync_manager_cb")
def fake_event_sync_manager(
    calendar_service_cb: Callable[[], Awaitable[GoogleCalendarService]],
    store: CalendarStore,
) -> Callable[[], Awaitable[CalendarEventSyncManager]]:
    """Fixture for an event sync manager."""

    async def func() -> CalendarEventSyncManager:
        service = await calendar_service_cb()
        return CalendarEventSyncManager(service, CALENDAR_ID, store)

    return func


@pytest.fixture(name="fetch_events")
async def mock_fetch_events(
    event_sync_manager_cb: Callable[[], Awaitable[CalendarEventSyncManager]]
) -> Callable[..., Awaitable[list[dict[str, Any]]]]:
    """Fixture to return events on the calendar."""
    sync = await event_sync_manager_cb()

    async def _func(keys: set[str] | None = None) -> list[dict[str, Any]]:
        items = await sync.store_service.async_list_events(
            LocalListEventsRequest(
                start_time=datetime.datetime.fromisoformat("2000-01-01 00:00:00"),
                end_time=datetime.datetime.fromisoformat("2025-12-31 00:00:00"),
            )
        )
        result = []
        for event in items.events:
            data = event.dict()
            for key, _ in list(event.dict().items()):
                if keys and key not in keys:
                    del data[key]
            result.append(data)
        return result

    return _func
