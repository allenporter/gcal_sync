"""A Timeline is a set of events on a calendar.

A timeline can be used to iterate over all events, including expanded
recurring events. A timeline also supports methods to scan ranges of events
like returning all events happening today or after a specific date.
"""

from __future__ import annotations

import datetime
from collections.abc import Generator, Iterable

from ical.iter import (
    LazySortableItem,
    MergedIterable,
    RecurIterable,
    SortableItem,
    SortableItemTimeline,
    SortableItemValue,
    SortedItemIterable,
)
from ical.timespan import Timespan

from .model import DateOrDatetime, Event

__all__ = ["Timeline"]


class Timeline(SortableItemTimeline[Event]):
    """A set of events on a calendar.

    A timeline is created by the local sync API and not instantiated directly.
    """

    def __init__(self, iterable: Iterable[SortableItem[Timespan, Event]]) -> None:
        super().__init__(iterable)


def _event_iterable(
    iterable: list[Event], tzinfo: datetime.tzinfo
) -> Iterable[SortableItem[Timespan, Event]]:
    """Create a sorted iterable from the list of events."""

    def sortable_items() -> Generator[SortableItem[Timespan, Event], None, None]:
        for event in iterable:
            if event.recurrence:
                continue
            yield SortableItemValue(event.timespan_of(tzinfo), event)

    return SortedItemIterable(sortable_items, tzinfo)


class RecurAdapter:
    """An adapter that expands an Event instance for a recurrence rule.

    This adapter is given an event, then invoked with a specific date/time instance
    that the event occurs on due to a recurrence rule. The event is copied with
    necessary updated fields to act as a flattened instance of the event.
    """

    def __init__(self, event: Event):
        """Initialize the RecurAdapter."""
        self._event = event
        self._event_duration = event.computed_duration
        self._is_all_day = not isinstance(self._event.start.value, datetime.datetime)

    def get(
        self, dtstart: datetime.datetime | datetime.date
    ) -> SortableItem[Timespan, Event]:
        """Return a lazy sortable item."""
        if self._is_all_day and isinstance(dtstart, datetime.datetime):
            # Convert back to datetime.date if needed for the original event
            dtstart = datetime.date.fromordinal(dtstart.toordinal())

        def build() -> Event:
            return self._event.copy(
                deep=True,
                update={
                    "start": DateOrDatetime.parse(dtstart),
                    "end": DateOrDatetime.parse(dtstart + self._event_duration),
                    "id": dtstart.isoformat(),
                    "original_start_time": self._event.start,
                    "recurring_event_id": self._event.id,
                },
            )

        return LazySortableItem(
            Timespan.of(dtstart, dtstart + self._event_duration), build
        )


def calendar_timeline(
    events: list[Event], tzinfo: datetime.tzinfo = datetime.timezone.utc
) -> Timeline:
    """Create a timeline for events on a calendar, including recurrence."""
    iters: list[Iterable[SortableItem[Timespan, Event]]] = [
        _event_iterable(events, tzinfo=tzinfo)
    ]
    for event in events:
        if not event.recurrence:
            continue
        iters.append(RecurIterable(RecurAdapter(event).get, event.rrule))
    return Timeline(MergedIterable(iters))
