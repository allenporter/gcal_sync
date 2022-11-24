"""A Timeline is a set of events on a calendar.

A timeline can be used to iterate over all events, including expanded
recurring events. A timeline also supports methods to scan ranges of events
like returning all events happening today or after a specific date.
"""

from __future__ import annotations

import datetime
import logging
from collections.abc import Generator, Iterable, Iterator
from typing import TypeVar

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

from .model import DateOrDatetime, Event, EventStatusEnum, SyntheticEventId

__all__ = ["Timeline"]

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class Timeline(SortableItemTimeline[Event]):
    """A set of events on a calendar.

    A timeline is created by the local sync API and not instantiated directly.
    """

    def __init__(self, iterable: Iterable[SortableItem[Timespan, Event]]) -> None:
        super().__init__(iterable)


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

    def get(
        self, dtstart: datetime.datetime | datetime.date
    ) -> SortableItem[Timespan, Event]:
        """Return a lazy sortable item."""

        def build() -> Event:
            if not self._event.id:
                raise ValueError("Expected event to have event id")
            event_id = SyntheticEventId.of(self._event.id, dtstart)
            return self._event.copy(
                deep=True,
                update={
                    "start": DateOrDatetime.parse(dtstart),
                    "end": DateOrDatetime.parse(dtstart + self._event_duration),
                    "id": event_id.event_id,
                    "original_start_time": self._event.start,
                    "recurring_event_id": self._event.id,
                },
            )

        return LazySortableItem(
            Timespan.of(dtstart, dtstart + self._event_duration), build
        )


class FilteredIterable(Iterable[T]):
    """An iterable that excludes emits values except those excluded."""

    def __init__(self, func: Iterable[T], exclude: set[T] | None) -> None:
        self._func = func
        self._exclude = exclude

    def __iter__(self) -> Iterator[T]:
        """Return an iterator filtered by the exclusion set."""
        for value in self._func:
            if self._exclude is not None and value in self._exclude:
                continue
            yield value


def calendar_timeline(
    events: list[Event], tzinfo: datetime.tzinfo = datetime.timezone.utc
) -> Timeline:
    """Create a timeline for events on a calendar, including recurrence."""
    normal_events: list[Event] = []
    recurring: list[Event] = []
    recurring_skip: dict[str, set[datetime.date | datetime.datetime]] = {}
    for data in events:
        event = Event.parse_obj(data)
        if event.recurring_event_id and event.original_start_time:
            # The API returned a one-off instance of a recurring event. Keep track
            # of the original start time which is used to filter out from the
            # recurrence. The one-off is handled below.
            if event.recurring_event_id in recurring_skip:
                recurring_skip[event.recurring_event_id].add(
                    event.original_start_time.value
                )
            else:
                recurring_skip[event.recurring_event_id] = set(
                    [event.original_start_time.value]
                )

        if event.status == EventStatusEnum.CANCELLED:
            continue
        if event.recurrence:
            recurring.append(event)
        else:
            normal_events.append(event)

    def sortable_items() -> Generator[SortableItem[Timespan, Event], None, None]:
        nonlocal normal_events
        for event in normal_events:
            if event.status == EventStatusEnum.CANCELLED:
                continue
            yield SortableItemValue(event.timespan_of(tzinfo), event)

    iters: list[Iterable[SortableItem[Timespan, Event]]] = []
    iters.append(SortedItemIterable(sortable_items, tzinfo))
    for event in recurring:
        value_iter: Iterable[datetime.date | datetime.datetime] = event.rrule
        value_iter = FilteredIterable(value_iter, recurring_skip.get(event.id or ""))
        iters.append(RecurIterable(RecurAdapter(event).get, value_iter))

    return Timeline(MergedIterable(iters))
