"""Tests for local storage."""

import pytest

from gcal_sync.store import CalendarStore, InMemoryCalendarStore, ScopedCalendarStore


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


async def test_scoped_store(store: CalendarStore) -> None:
    """Test scoped store operations."""
    await store.async_save(
        {
            "a": {
                "b": 2,
            },
            "c": {
                "d": 3,
            },
        }
    )
    scoped_store = ScopedCalendarStore(store, "a")
    assert await scoped_store.async_load() == {"b": 2}

    # Overwrite existing data in the store
    await scoped_store.async_save({"b": 4, "e": 5})

    # Verify scoped store values
    assert await scoped_store.async_load() == {"b": 4, "e": 5}

    # Verify original store values
    assert await store.async_load() == {
        "a": {
            "b": 4,
            "e": 5,
        },
        "c": {
            "d": 3,
        },
    }


async def test_multi_scoped_store(store: CalendarStore) -> None:
    """Test multiple scoped store operations."""
    await store.async_save(
        {
            "a": {
                "b": {
                    "c": 1,
                },
            },
        }
    )
    scoped_store = ScopedCalendarStore(store, "a")
    scoped_store2 = ScopedCalendarStore(scoped_store, "b")
    assert await scoped_store2.async_load() == {"c": 1}

    # Overwrite existing data in the store
    await scoped_store2.async_save({"d": 2})

    # Verify original store values
    assert await store.async_load() == {
        "a": {
            "b": {
                "d": 2,
            },
        },
    }
