"""Library for local storage of calendar data."""

from __future__ import annotations

from abc import ABC


class CalendarStore(ABC):
    """Interface for external calendar storage."""

    async def async_load(self) -> dict | None:
        """Load data."""

    async def async_save(self, data: dict) -> None:
        """Save data."""


class InMemoryCalendarStore(CalendarStore):
    """An in memory implementation of CalendarStore."""

    def __init__(self) -> None:
        self._data: dict | None = None

    async def async_load(self) -> dict | None:
        """Load data."""
        return self._data

    async def async_save(self, data: dict) -> None:
        """Save data."""
        self._data = data
