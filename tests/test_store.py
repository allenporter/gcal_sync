"""Tests for local storage."""

import pytest

from gcal_sync.store import CalendarStore, InMemoryCalendarStore


@pytest.fixture(name="store")
def fake_store() -> CalendarStore:
    """Fixture for a calendar store."""
    return InMemoryCalendarStore()


async def test_empty_store(store: CalendarStore) -> None:
    """Test state of an empty store."""
    assert not await store.async_load()


async def test_async_save(store: CalendarStore) -> None:
    """Test saving and loading data."""
    await store.async_save({"a": 1, "b": 2})
    assert await store.async_load() == {"a": 1, "b": 2}
