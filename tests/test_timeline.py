"""Tests for iterating over events on a timeline."""

from __future__ import annotations

import datetime
import zoneinfo

import pytest
from freezegun import freeze_time

from gcal_sync.model import DateOrDatetime, Event
from gcal_sync.timeline import Timeline, calendar_timeline
from gcal_sync.util import use_local_timezone


@pytest.fixture(name="timeline")
def mock_timeline() -> Timeline:
    """Fixture of list of all day events to use in tests."""
    return calendar_timeline(
        [
            Event.parse_obj(
                {
                    "id": "some-event-id-2",
                    "summary": "second",
                    "start": {
                        "date": "2000-2-1",
                    },
                    "end": {
                        "date": "2000-2-2",
                    },
                }
            ),
            Event.parse_obj(
                {
                    "id": "some-event-id-4",
                    "summary": "fourth",
                    "start": {
                        "date": "2000-4-1",
                    },
                    "end": {
                        "date": "2000-4-2",
                    },
                },
            ),
            Event.parse_obj(
                {
                    "id": "some-event-id-3",
                    "summary": "third",
                    "start": {
                        "date": "2000-3-1",
                    },
                    "end": {
                        "date": "2000-3-2",
                    },
                },
            ),
            Event.parse_obj(
                {
                    "id": "some-event-id-1",
                    "summary": "first",
                    "start": {
                        "date": "2000-1-1",
                    },
                    "end": {
                        "date": "2000-1-2",
                    },
                },
            ),
        ]
    )


@pytest.fixture(name="calendar_times")
def mock_calendar_times() -> Timeline:
    """Fixture calendar with datetime based events to use in tests."""
    return calendar_timeline(
        [
            Event.parse_obj(
                {
                    "id": "some-event-id-1",
                    "summary": "first",
                    "start": {
                        "dateTime": "2000-01-01T11:00:00",
                    },
                    "end": {
                        "dateTime": "2000-01-01T11:30:00",
                    },
                },
            ),
            Event.parse_obj(
                {
                    "id": "some-event-id-2",
                    "summary": "second",
                    "start": {
                        "dateTime": "2000-01-01T12:00:00",
                    },
                    "end": {
                        "dateTime": "2000-01-01T13:00:00",
                    },
                }
            ),
            Event.parse_obj(
                {
                    "id": "some-event-id-3",
                    "summary": "third",
                    "start": {
                        "dateTime": "2000-01-02T12:00:00",
                    },
                    "end": {
                        "dateTime": "2000-01-02T13:00:00",
                    },
                }
            ),
        ]
    )


def test_iteration(timeline: Timeline) -> None:
    """Test chronological iteration of a timeline."""
    assert [e.summary for e in timeline] == [
        "first",
        "second",
        "third",
        "fourth",
    ]


@pytest.mark.parametrize(
    "when,expected_events",
    [
        (datetime.date(2000, 1, 1), ["first"]),
        (datetime.date(2000, 2, 1), ["second"]),
        (datetime.date(2000, 3, 1), ["third"]),
    ],
)
def test_on_date(
    timeline: Timeline, when: datetime.date, expected_events: list[str]
) -> None:
    """Test returning events on a particular day."""
    assert [e.summary for e in timeline.on_date(when)] == expected_events


@pytest.mark.parametrize(
    "start,end,expected_events",
    [
        (datetime.date(2000, 2, 3), datetime.date(2000, 2, 4), []),
        (datetime.date(2000, 1, 31), datetime.date(2000, 2, 2), ["second"]),
        (
            datetime.datetime(2000, 1, 31, 12, 0),
            datetime.datetime(2000, 2, 2, 12, 00),
            ["second"],
        ),
        (
            datetime.datetime(2000, 2, 1, 12, 0),
            datetime.datetime(2000, 2, 1, 12, 30),
            ["second"],
        ),
    ],
)
def test_overlap(
    timeline: Timeline,
    start: datetime.date | datetime.datetime,
    end: datetime.date | datetime.datetime,
    expected_events: list[str],
) -> None:
    """Test returning events on a particular day."""
    assert [
        e.summary
        for e in timeline.overlapping(
            DateOrDatetime.parse(start), DateOrDatetime.parse(end)
        )
    ] == expected_events


def test_active_after(timeline: Timeline) -> None:
    """Test returning events on a particular day."""
    events = [
        e.summary
        for e in timeline.active_after(DateOrDatetime.parse(datetime.date(2000, 2, 15)))
    ]
    assert events == ["third", "fourth"]


@pytest.mark.parametrize(
    "at_datetime,expected_events",
    [
        (datetime.datetime(2000, 1, 1, 11, 15), ["first"]),
        (datetime.datetime(2000, 1, 1, 11, 59), []),
        (datetime.datetime(2000, 1, 1, 12, 0), ["second"]),
        (datetime.datetime(2000, 1, 1, 12, 30), ["second"]),
        (datetime.datetime(2000, 1, 1, 12, 59), ["second"]),
        (datetime.datetime(2000, 1, 1, 13, 0), []),
    ],
)
def test_at_instant(
    calendar_times: Timeline, at_datetime: datetime.datetime, expected_events: list[str]
) -> None:
    """Test returning events at a specific time."""
    assert [
        e.summary for e in calendar_times.at_instant(at_datetime)
    ] == expected_events


@freeze_time("2000-01-01 12:30:00")
def test_now(calendar_times: Timeline) -> None:
    """Test events happening at the current time."""
    assert [e.summary for e in calendar_times.now()] == ["second"]


@freeze_time("2000-01-01 13:00:00")
def test_now_no_match(calendar_times: Timeline) -> None:
    """Test no events happening at the current time."""
    assert [e.summary for e in calendar_times.now()] == []


@freeze_time("2000-01-01 12:30:00")
def test_today(calendar_times: Timeline) -> None:
    """Test events active today."""
    assert [e.summary for e in calendar_times.today()] == ["first", "second"]


@pytest.mark.parametrize(
    "start,end,rrules,expected",
    [
        (
            datetime.date(2022, 8, 1),
            datetime.date(2022, 8, 2),
            ["RRULE:FREQ=DAILY;UNTIL=20220804"],
            [
                (datetime.date(2022, 8, 1), datetime.date(2022, 8, 2)),
                (datetime.date(2022, 8, 2), datetime.date(2022, 8, 3)),
                (datetime.date(2022, 8, 3), datetime.date(2022, 8, 4)),
                (datetime.date(2022, 8, 4), datetime.date(2022, 8, 5)),
            ],
        ),
        (
            datetime.date(2022, 8, 1),
            datetime.date(2022, 8, 2),
            ["RRULE:FREQ=DAILY;UNTIL=20220804;INTERVAL=2"],
            [
                (datetime.date(2022, 8, 1), datetime.date(2022, 8, 2)),
                (datetime.date(2022, 8, 3), datetime.date(2022, 8, 4)),
            ],
        ),
        (
            datetime.date(2022, 8, 1),
            datetime.date(2022, 8, 2),
            ["RRULE:FREQ=DAILY;COUNT=3"],
            [
                (datetime.date(2022, 8, 1), datetime.date(2022, 8, 2)),
                (datetime.date(2022, 8, 2), datetime.date(2022, 8, 3)),
                (datetime.date(2022, 8, 3), datetime.date(2022, 8, 4)),
            ],
        ),
        (
            datetime.date(2022, 8, 1),
            datetime.date(2022, 8, 2),
            ["RRULE:FREQ=DAILY;INTERVAL=2;COUNT=3"],
            [
                (datetime.date(2022, 8, 1), datetime.date(2022, 8, 2)),
                (datetime.date(2022, 8, 3), datetime.date(2022, 8, 4)),
                (datetime.date(2022, 8, 5), datetime.date(2022, 8, 6)),
            ],
        ),
        (
            datetime.date(2022, 8, 1),
            datetime.date(2022, 8, 2),
            [
                "EXDATE;VALUE=DATE:20220803",
                "RRULE:FREQ=DAILY;INTERVAL=2;COUNT=3",
            ],
            [
                (datetime.date(2022, 8, 1), datetime.date(2022, 8, 2)),
                (datetime.date(2022, 8, 5), datetime.date(2022, 8, 6)),
            ],
        ),
        (
            datetime.datetime(2022, 8, 1, 9, 30, 0),
            datetime.datetime(2022, 8, 1, 10, 0, 0),
            ["RRULE:FREQ=DAILY;UNTIL=20220804T093000"],
            [
                (
                    datetime.datetime(2022, 8, 1, 9, 30, 0),
                    datetime.datetime(2022, 8, 1, 10, 0, 0),
                ),
                (
                    datetime.datetime(2022, 8, 2, 9, 30, 0),
                    datetime.datetime(2022, 8, 2, 10, 0, 0),
                ),
                (
                    datetime.datetime(2022, 8, 3, 9, 30, 0),
                    datetime.datetime(2022, 8, 3, 10, 0, 0),
                ),
                (
                    datetime.datetime(2022, 8, 4, 9, 30, 0),
                    datetime.datetime(2022, 8, 4, 10, 0, 0),
                ),
            ],
        ),
    ],
)
def test_day_iteration(
    start: datetime.datetime | datetime.date,
    end: datetime.datetime | datetime.date,
    rrules: list[str],
    expected: list[tuple[datetime.date, datetime.date]],
) -> None:
    """Test recurrence rules for day frequency."""
    event = Event(
        summary="summary",
        start=DateOrDatetime.parse(start),
        end=DateOrDatetime.parse(end),
        recurrence=rrules,
    )
    timeline = calendar_timeline([event])
    assert [(e.start.value, e.end.value) for e in timeline] == expected


@pytest.mark.parametrize(
    "tzname,dt_before,dt_after",
    [
        (
            "America/Los_Angeles",  # UTC-8 in Feb
            datetime.datetime(2000, 2, 1, 7, 59, 59, tzinfo=datetime.timezone.utc),
            datetime.datetime(2000, 2, 1, 8, 0, 0, tzinfo=datetime.timezone.utc),
        ),
        (
            "America/Regina",  # UTC-6 all year round
            datetime.datetime(2000, 2, 1, 5, 59, 59, tzinfo=datetime.timezone.utc),
            datetime.datetime(2000, 2, 1, 6, 0, 0, tzinfo=datetime.timezone.utc),
        ),
        (
            "CET",  # UTC-1 in Feb
            datetime.datetime(2000, 1, 31, 22, 59, 59, tzinfo=datetime.timezone.utc),
            datetime.datetime(2000, 1, 31, 23, 0, 0, tzinfo=datetime.timezone.utc),
        ),
    ],
)
def test_all_day_with_local_timezone(
    tzname: str, dt_before: datetime.datetime, dt_after: datetime.datetime
) -> None:
    """Test iteration of all day events using local timezone override."""
    timeline = calendar_timeline(
        [
            Event(
                summary="event",
                start=DateOrDatetime(date=datetime.date(2000, 2, 1)),
                end=DateOrDatetime(date=datetime.date(2000, 2, 2)),
            ),
        ]
    )

    def start_after(dtstart: datetime.datetime) -> list[str]:
        nonlocal timeline
        return [
            e.summary for e in timeline.start_after(DateOrDatetime(date_time=dtstart))
        ]

    with use_local_timezone(zoneinfo.ZoneInfo(tzname)):
        assert start_after(dt_before) == ["event"]
        assert not start_after(dt_after)
