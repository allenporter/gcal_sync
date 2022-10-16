"""Utility methods used by multiple components."""

from __future__ import annotations

import datetime
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

__all__ = [
    "use_local_timezone",
]


MIDNIGHT = datetime.time()
LOCAL_TZ = ContextVar[datetime.tzinfo]("_local_tz")


@contextmanager
def use_local_timezone(local_tz: datetime.tzinfo) -> Generator[None, None, None]:
    """Set the local timezone to use when converting a date to datetime.

    This is expected to be used as a context manager when the default timezone
    used by python is not the timezone to be used for calendar operations (the
    attendees local timezone).
    """
    orig_tz = LOCAL_TZ.set(local_tz)
    try:
        yield
    finally:
        LOCAL_TZ.reset(orig_tz)


def local_timezone() -> datetime.tzinfo:
    """Get the local timezone to use when converting date to datetime."""
    if local_tz := LOCAL_TZ.get(None):
        return local_tz
    if local_tz := datetime.datetime.now().astimezone().tzinfo:
        return local_tz
    return datetime.timezone.utc
