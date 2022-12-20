"""Authentication library, providing base classes for users of the library.

In order to use `gcal_sync.api`, you need to implement `gcal_sync.AbstractAuth`
which provides an OAuth access token. See Google's
[Authentication and authorization overview][1] for general details on how to
use OAuth, which involves things like redirecting a user to a web flow, and
redirecting back with an access token.

An example implementation of `gcal_sync.AbstractAuth` would need to handle things like
passin in the access token and any other necessary OAuth token refreshes when the
access token has expired.

```python
from gcal_sync.auth import AbstractAuth

class MyAuthImpl(gcal_sync.AbstractAuth):

    def __init__(self, websession: aiohttp.ClientSession) -> None:
        super().__init__(websession)

    async def async_get_access_token(self) -> str:
        return ...
```

[1]: https://developers.google.com/workspace/guides/auth-overview

"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from http import HTTPStatus
from typing import Any, List, Mapping, Optional

import aiohttp
from aiohttp.client_exceptions import ClientError, ClientResponseError

from .exceptions import (
    ApiException,
    ApiForbiddenException,
    AuthException,
    InvalidSyncTokenException,
)

_LOGGER = logging.getLogger(__name__)

AUTHORIZATION_HEADER = "Authorization"
ERROR = "error"
STATUS = "status"
MESSAGE = "message"

API_BASE_URL = "https://www.googleapis.com/calendar/v3"


class AbstractAuth(ABC):  # pylint: disable=too-few-public-methods
    """Library for providing authentication credentials.

    You are expected to implement a subclass and implement the abstract
    methods when using the `gcal_sync.api` classes. The api library will
    invoke this class and ask for the access token on outgoing requests.
    """

    def __init__(self, websession: aiohttp.ClientSession, host: str | None = None):
        """Initialize the auth."""
        self._websession = websession
        self._host = host if host is not None else API_BASE_URL

    @abstractmethod
    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

    async def request(
        self, method: str, url: str, **kwargs: Optional[Mapping[str, Any]]
    ) -> aiohttp.ClientResponse:
        """Make a request."""
        try:
            access_token = await self.async_get_access_token()
        except ClientError as err:
            raise AuthException(f"Access token failure: {err}") from err
        headers = {AUTHORIZATION_HEADER: f"Bearer {access_token}"}
        if not (url.startswith("http://") or url.startswith("https://")):
            url = f"{self._host}/{url}"
        _LOGGER.debug("request[%s]=%s %s", method, url, kwargs.get("params"))
        if method != "get" and "json" in kwargs:
            _LOGGER.debug("request[post json]=%s", kwargs["json"])
        return await self._websession.request(method, url, **kwargs, headers=headers)

    async def get(
        self, url: str, **kwargs: Mapping[str, Any]
    ) -> aiohttp.ClientResponse:
        """Make a get request."""
        try:
            resp = await self.request("get", url, **kwargs)
        except ClientError as err:
            raise ApiException(f"Error connecting to API: {err}") from err
        return await AbstractAuth._raise_for_status(resp)

    async def get_json(self, url: str, **kwargs: Mapping[str, Any]) -> dict[str, Any]:
        """Make a get request and return json response."""
        resp = await self.get(url, **kwargs)
        try:
            result = await resp.json()
        except ClientError as err:
            raise ApiException("Server returned malformed response") from err
        if not isinstance(result, dict):
            raise ApiException(f"Server return malformed response: {result}")
        _LOGGER.debug("response=%s", result)
        return result

    async def post(
        self, url: str, **kwargs: Mapping[str, Any]
    ) -> aiohttp.ClientResponse:
        """Make a post request."""
        try:
            resp = await self.request("post", url, **kwargs)
        except ClientError as err:
            raise ApiException(f"Error connecting to API: {err}") from err
        return await AbstractAuth._raise_for_status(resp)

    async def post_json(self, url: str, **kwargs: Mapping[str, Any]) -> dict[str, Any]:
        """Make a post request and return a json response."""
        resp = await self.post(url, **kwargs)
        try:
            result = await resp.json()
        except ClientError as err:
            raise ApiException("Server returned malformed response") from err
        if not isinstance(result, dict):
            raise ApiException(f"Server returned malformed response: {result}")
        _LOGGER.debug("response=%s", result)
        return result

    @staticmethod
    async def _raise_for_status(resp: aiohttp.ClientResponse) -> aiohttp.ClientResponse:
        """Raise exceptions on failure methods."""
        detail = await AbstractAuth._error_detail(resp)
        try:
            resp.raise_for_status()
        except ClientResponseError as err:
            if err.status == HTTPStatus.FORBIDDEN:
                raise ApiForbiddenException(
                    f"Forbidden response from API: {err}"
                ) from err
            if err.status == HTTPStatus.UNAUTHORIZED:
                raise AuthException(f"Unable to authenticate with API: {err}") from err
            if err.status == HTTPStatus.GONE:
                raise InvalidSyncTokenException(
                    "Sync token invalidated by server"
                ) from err
            detail.append(err.message)
            raise ApiException(": ".join(detail)) from err
        except ClientError as err:
            raise ApiException(f"Error from API: {err}") from err
        return resp

    @staticmethod
    async def _error_detail(resp: aiohttp.ClientResponse) -> List[str]:
        """Resturns an error message string from the APi response."""
        if resp.status < 400:
            return []
        try:
            result = await resp.json()
            error = result.get(ERROR, {})
        except ClientError:
            return []
        message = ["Error from API", f"{resp.status}"]
        if STATUS in error:
            message.append(f"{error[STATUS]}")
        if MESSAGE in error:
            message.append(error[MESSAGE])
        return message
