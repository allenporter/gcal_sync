"""Test fixtures for calendar API."""
from __future__ import annotations

import asyncio
import datetime
from collections.abc import Callable
from typing import Any, Generator, TypeVar
from unittest.mock import Mock, patch

import pytest
from google.oauth2.credentials import Credentials
from googleapiclient import discovery as google_discovery

from gcal_sync.api import GoogleCalendarService
from gcal_sync.auth import AbstractAuth

ApiResult = Callable[[dict[str, Any]], None]
_T = TypeVar("_T")
YieldFixture = Generator[_T, None, None]


@pytest.fixture(name="token_scopes")
def mock_token_scopes() -> list[str]:
    """Fixture for scopes used during test."""
    return ["https://www.googleapis.com/auth/calendar"]


@pytest.fixture(name="token_expiry")
def mock_token_expiry() -> datetime.datetime:
    """Expiration time for credentials used in the test."""
    return datetime.datetime.now() + datetime.timedelta(days=7)


@pytest.fixture(name="creds")
def mock_creds(token_scopes: list[str], token_expiry: datetime.datetime) -> Credentials:
    """Fixture that defines creds used in the test."""
    return Credentials(
        token="ACCESS_TOKEN",
        refresh_token="REFRESH_TOKEN",
        token_uri="http://example.com",
        client_id="client-id",
        client_secret="client-secret",
        scopes=token_scopes,
        expiry=token_expiry,
    )


class FakeAuth(AbstractAuth):  # pylint: disable=too-few-public-methods
    """Implementation of AbstractAuth for use in tests."""

    def __init__(self, creds: Credentials):
        """Initialize FakeAuth."""
        self._creds = creds

    async def async_get_creds(self) -> Credentials:
        """Return an OAuth credential for the calendar API."""
        return self._creds


@pytest.fixture(name="auth")
def mock_auth(creds: Credentials) -> AbstractAuth:
    """Fixture to fake out an auth implementation."""
    return FakeAuth(creds)


@pytest.fixture(autouse=True, name="calendar_resource")
def mock_calendar_resource() -> YieldFixture[google_discovery.Resource]:
    """Fixture to mock out the Google discovery API."""
    with patch("gcal_sync.api.google_discovery.build") as mock:
        yield mock


@pytest.fixture(name="calendar_service")
def mock_calendar_service(
    event_loop: asyncio.AbstractEventLoop,
    auth: AbstractAuth,
) -> GoogleCalendarService:
    """Fixture to fake out the api service."""
    return GoogleCalendarService(event_loop, auth)


@pytest.fixture(name="events_list")
def mock_events_list(
    calendar_resource: google_discovery.Resource,
) -> Callable[[dict[str, Any]], None]:
    """Fixture to construct a fake event list API response."""

    list_mock = Mock()
    calendar_resource.return_value.events.return_value.list = list_mock
    return list_mock


@pytest.fixture(name="calendars_list")
def mock_calendars_list(
    calendar_resource: google_discovery.Resource,
) -> ApiResult:
    """Fixture to construct a fake calendar list API response."""

    def _put_result(response: dict[str, Any]) -> None:
        # pylint: disable=line-too-long
        calendar_resource.return_value.calendarList.return_value.list.return_value.execute.return_value = (
            response
        )

    return _put_result


@pytest.fixture(name="insert_event")
def mock_insert_event(
    calendar_resource: google_discovery.Resource,
) -> Mock:
    """Fixture to create a mock to capture new events added to the API."""
    insert_mock = Mock()
    calendar_resource.return_value.events.return_value.insert = insert_mock
    return insert_mock
