"""Library for local storage of calendar data."""

from __future__ import annotations

from abc import ABC
from typing import Any


class CalendarStore(ABC):
    """Interface for external calendar storage."""

    async def async_load(self) -> dict[str, Any] | None:
        """Load data."""

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data."""


class InMemoryCalendarStore(CalendarStore):
    """An in memory implementation of CalendarStore."""

    def __init__(self) -> None:
        self._data: dict[str, Any] | None = None

    async def async_load(self) -> dict[str, Any] | None:
        """Load data."""
        return self._data

    async def async_save(self, data: dict[str, Any]) -> None:
        """Save data."""
        self._data = data
