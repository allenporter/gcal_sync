"""Tests for the request client library."""

from typing import Awaitable, Callable

import aiohttp
import pytest

from gcal_sync.auth import AbstractAuth
from gcal_sync.exceptions import ApiException, ApiForbiddenException, AuthException


async def test_request(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test of basic request/response handling."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.path == "/path-prefix/some-path"
        assert request.headers["Authorization"] == "Bearer some-token"
        assert request.query == {"client_id": "some-client-id"}
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    resp = await auth.request(
        "get",
        "some-path",
        params={"client_id": "some-client-id"},
    )
    resp.raise_for_status()
    data = await resp.json()
    assert data == {"some-key": "some-value"}


async def test_get_json_response(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test of basic json response."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        assert request.query["client_id"] == "some-client-id"
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    data = await auth.get_json("some-path", params={"client_id": "some-client-id"})
    assert data == {"some-key": "some-value"}


async def test_get_json_response_unexpected(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test json response with wrong response type."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response(["value1", "value2"])

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.get_json("some-path")


async def test_get_json_response_unexpected_text(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test json response that was not json."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(text="body")

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.get_json("some-path")


async def test_post_json_response(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test post that returns json."""

    async def handler(request: aiohttp.web.Request) -> aiohttp.web.Response:
        body = await request.json()
        assert body == {"client_id": "some-client-id"}
        return aiohttp.web.json_response(
            {
                "some-key": "some-value",
            }
        )

    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    data = await auth.post_json("some-path", json={"client_id": "some-client-id"})
    assert data == {"some-key": "some-value"}


async def test_post_json_response_unexpected(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test post that returns wrong json type."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response(["value1", "value2"])

    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.post_json("some-path")


async def test_post_json_response_unexpected_text(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test post that returns unexpected format."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(text="body")

    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.post_json("some-path")


async def test_get_json_response_bad_request(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test error handling with detailed json response."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.json_response(
            {
                "error": {
                    "errors": [
                        {
                            "domain": "calendar",
                            "reason": "timeRangeEmpty",
                            "message": "The specified time range is empty.",
                            "locationType": "parameter",
                            "location": "timeMax",
                        }
                    ],
                    "code": 400,
                    "message": "The specified time range is empty.",
                }
            },
            status=400,
        )

    app.router.add_get("/path-prefix/some-path", handler)
    app.router.add_post("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")

    with pytest.raises(
        ApiException,
        match=r"Error from API: 400: The specified time range is empty.: Bad Request",
    ):
        await auth.get("some-path")

    with pytest.raises(
        ApiException,
        match=r"Error from API: 400: The specified time range is empty.: Bad Request",
    ):
        await auth.get_json("some-path")

    with pytest.raises(
        ApiException,
        match=r"Error from API: 400: The specified time range is empty.: Bad Request",
    ):
        await auth.post("some-path")

    with pytest.raises(
        ApiException,
        match=r"Error from API: 400: The specified time range is empty.: Bad Request",
    ):
        await auth.post_json("some-path")


async def test_auth_refresh_error(
    app: aiohttp.web.Application,
    refreshing_auth_client: Callable[[], Awaitable[AbstractAuth]],
) -> None:
    """Test an authentication token refresh error."""

    async def auth_handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=401)

    app.router.add_get("/refresh-auth", auth_handler)

    auth = await refreshing_auth_client()
    with pytest.raises(AuthException):
        await auth.get_json("some-path")


async def test_unavailable_error(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test of basic request/response handling."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=500)

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiException):
        await auth.get_json("some-path")


async def test_forbidden_error(
    app: aiohttp.web.Application, auth_client: Callable[[str], Awaitable[AbstractAuth]]
) -> None:
    """Test request/response handling for 403 status."""

    async def handler(_: aiohttp.web.Request) -> aiohttp.web.Response:
        return aiohttp.web.Response(status=403)

    app.router.add_get("/path-prefix/some-path", handler)

    auth = await auth_client("/path-prefix")
    with pytest.raises(ApiForbiddenException):
        await auth.get_json("some-path")
