"""Test fixtures for calendar API."""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from json import JSONDecodeError
from typing import Any, Generator, List, TypeVar, cast

import aiohttp
import pytest
from aiohttp.test_utils import TestClient

from gcal_sync.api import GoogleCalendarService
from gcal_sync.auth import AbstractAuth

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
        json = await resp.json()
        assert isinstance(json["token"], str)
        return json["token"]


@pytest.fixture(name="event_loop")
def create_event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Fixture for producing event loop."""
    yield asyncio.get_event_loop()


async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
    """Handles the request, inserting response prepared by tests."""
    if request.method == "POST":
        try:
            request.app["request-json"].append(await request.json())
        except JSONDecodeError as err:
            print(err)
        request.app["request-post"].append(await request.post())
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
    app.router.add_get("/calendars/{calendarId}/events", handler)
    app.router.add_post("/calendars/{calendarId}/events", handler)
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


@pytest.fixture(name="json_response")
def mock_json_response(app: aiohttp.web.Application) -> ApiResult:
    """Fixture to construct a fake API response."""

    def _put_result(response: dict[str, Any]) -> None:
        app["response"].append(aiohttp.web.json_response(response))

    return _put_result


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
