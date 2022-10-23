"""A Timeline is a set of events on a calendar.

A timeline can be used to iterate over all events, including expanded
recurring events. A timeline also supports methods to scan ranges of events
like returning all events happening today or after a specific date.
"""

from __future__ import annotations

import datetime
import heapq
import logging
from collections.abc import Iterable, Iterator

from .iter import MergedIterable, RecurIterable
from .model import DateOrDatetime, Event
from .timespan import Timespan

_LOGGER = logging.getLogger(__name__)

__all__ = ["Timeline"]


class Timeline(Iterable[Event]):
    """A set of events on a calendar.

    A timeline is created by the local sync API and not instantiated directly.
    """

    def __init__(self, iterable: Iterable[Event], tzinfo: datetime.tzinfo) -> None:
        self._iterable = iterable
        self._tzinfo = tzinfo

    def __iter__(self) -> Iterator[Event]:
        """Return an iterator as a traversal over events in chronological order."""
        return iter(self._iterable)

    def overlapping(
        self,
        start: DateOrDatetime,
        end: DateOrDatetime,
    ) -> Iterator[Event]:
        """Return an iterator containing events active during the timespan.
        The end date is exclusive.
        """
        timespan = Timespan.of(start.normalize(), end.normalize())
        for event in self:
            timesp = event.timespan_of(timespan.tzinfo)
            if timesp.intersects(timespan):
                yield event
            elif timesp > timespan:
                break

    def start_after(self, instant: DateOrDatetime) -> Iterator[Event]:
        """Return an iterator containing events starting after the specified time."""
        value = instant.normalize(self._tzinfo)
        for event in self:
            timesp = event.timespan_of(value.tzinfo)
            if timesp.start > value:
                yield event

    def active_after(
        self,
        instant: DateOrDatetime,
    ) -> Iterator[Event]:
        """Return an iterator containing events active after the specified time."""
        value = instant.normalize(self._tzinfo)
        for event in self:
            timesp = event.timespan_of(value.tzinfo)
            if timesp.start > value or timesp.end > value:
                yield event

    def at_instant(
        self,
        instant: datetime.date | datetime.datetime,
    ) -> Iterator[Event]:  # pylint: disable
        """Return an iterator containing events starting after the specified time."""
        value = DateOrDatetime.parse(instant).normalize(self._tzinfo)
        timespan = Timespan.of(value, value)
        for event in self:
            timesp = event.timespan_of(timespan.tzinfo)
            if timesp.includes(timespan):
                yield event
            elif timesp > timespan:
                break

    def on_date(self, day: datetime.date) -> Iterator[Event]:  # pylint: disable
        """Return an iterator containing all events active on the specified day."""
        return self.overlapping(
            DateOrDatetime.parse(day),
            DateOrDatetime.parse(day + datetime.timedelta(days=1)),
        )

    def today(self) -> Iterator[Event]:
        """Return an iterator containing all events active on the specified day."""
        return self.on_date(datetime.date.today())

    def now(self) -> Iterator[Event]:
        """Return an iterator containing all events active on the specified day."""
        return self.at_instant(datetime.datetime.now())


class EventIterable(Iterable[Event]):
    """Iterable that returns events in sorted order.

    This iterable will ignore recurring events entirely.
    """

    def __init__(self, iterable: Iterable[Event], tzinfo: datetime.tzinfo) -> None:
        """Initialize timeline."""
        self._iterable = iterable
        self._tzinfo = tzinfo

    def __iter__(self) -> Iterator[Event]:
        """Return an iterator as a traversal over events in chronological order."""
        # Using a heap is faster than sorting if the number of events (n) is
        # much bigger than the number of events we extract from the iterator (k).
        # Complexity: O(n + k log n).
        heap: list[tuple[datetime.date | datetime.datetime, Event]] = []
        for event in iter(self._iterable):
            if event.recurrence:
                continue
            heapq.heappush(heap, (event.start.normalize(self._tzinfo), event))
        while heap:
            (_, event) = heapq.heappop(heap)
            yield event


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

    def get(self, dtstart: datetime.datetime | datetime.date) -> Event:
        """Return the next event in the recurrence."""
        if self._is_all_day and isinstance(dtstart, datetime.datetime):
            # Convert back to datetime.date if needed for the original event
            dtstart = datetime.date.fromordinal(dtstart.toordinal())
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


def calendar_timeline(
    events: list[Event], tzinfo: datetime.tzinfo = datetime.timezone.utc
) -> Timeline:
    """Create a timeline for events on a calendar, including recurrence."""
    iters: list[Iterable[Event]] = [EventIterable(events, tzinfo)]
    for event in events:
        if not event.recurrence:
            continue
        iters.append(RecurIterable(RecurAdapter(event).get, event.rrule))
    return Timeline(MergedIterable(iters), tzinfo)
