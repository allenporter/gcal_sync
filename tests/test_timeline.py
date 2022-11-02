"""Tests for iterating over events on a timeline."""

from __future__ import annotations

import datetime
import zoneinfo
from itertools import islice

import pytest
from freezegun import freeze_time

from gcal_sync.model import DateOrDatetime, Event
from gcal_sync.timeline import Timeline, calendar_timeline


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


def test_date_and_datetimes() -> None:
    """Test chronological iteration of a timeline with all day and non-all day events."""
    timeline = calendar_timeline(
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
                    "id": "some-event-id-1",
                    "summary": "first",
                    "start": {
                        "dateTime": "2000-01-01T12:00:00Z",
                    },
                    "end": {
                        "dateTime": "2000-01-01T12:30:00Z",
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
        ]
    )

    assert [e.summary for e in timeline] == [
        "first",
        "second",
        "third",
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
    assert [e.summary for e in timeline.overlapping(start, end)] == expected_events


def test_active_after(timeline: Timeline) -> None:
    """Test returning events on a particular day."""
    events = [e.summary for e in timeline.active_after(datetime.date(2000, 2, 15))]
    assert events == ["third", "fourth"]


@pytest.mark.parametrize(
    "at_datetime,expected_events",
    [
        (
            datetime.datetime(2000, 1, 1, 11, 15, tzinfo=datetime.timezone.utc),
            ["first"],
        ),
        (datetime.datetime(2000, 1, 1, 11, 59, tzinfo=datetime.timezone.utc), []),
        (
            datetime.datetime(2000, 1, 1, 12, 0, tzinfo=datetime.timezone.utc),
            ["second"],
        ),
        (
            datetime.datetime(2000, 1, 1, 12, 30, tzinfo=datetime.timezone.utc),
            ["second"],
        ),
        (
            datetime.datetime(2000, 1, 1, 12, 59, tzinfo=datetime.timezone.utc),
            ["second"],
        ),
        (datetime.datetime(2000, 1, 1, 13, 0, tzinfo=datetime.timezone.utc), []),
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
        (
            datetime.date(2022, 8, 1),
            datetime.date(2022, 8, 2),
            [
                "RRULE;X-EVOLUTION-ENDDATE=20220806T200000Z:FREQ=DAILY;COUNT=5",
            ],
            [
                (datetime.date(2022, 8, 1), datetime.date(2022, 8, 2)),
                (datetime.date(2022, 8, 2), datetime.date(2022, 8, 3)),
                (datetime.date(2022, 8, 3), datetime.date(2022, 8, 4)),
                (datetime.date(2022, 8, 4), datetime.date(2022, 8, 5)),
                (datetime.date(2022, 8, 5), datetime.date(2022, 8, 6)),
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
    local_tz = zoneinfo.ZoneInfo(tzname)
    timeline = calendar_timeline(
        [
            Event(
                summary="event",
                start=DateOrDatetime(date=datetime.date(2000, 2, 1)),
                end=DateOrDatetime(date=datetime.date(2000, 2, 2)),
            ),
        ],
        tzinfo=local_tz,
    )

    def start_after(dtstart: datetime.datetime) -> list[str]:
        nonlocal timeline
        return [e.summary for e in timeline.start_after(dtstart)]

    local_before = dt_before.astimezone(local_tz)
    assert start_after(local_before) == ["event"]

    local_after = dt_after.astimezone(local_tz)
    assert not start_after(local_after)


def test_invalid_rrule_until_datetime() -> None:
    """Test recurrence rule with mismatched UNTIL value from google api."""
    event = Event.parse_obj(
        {
            "summary": "Summary",
            "start": {"date": "2012-11-27"},
            "end": {"date": "2012-11-28"},
            "recurrence": ["RRULE:FREQ=WEEKLY;UNTIL=20130225T000000Z;BYDAY=TU"],
        }
    )
    timeline = calendar_timeline([event])
    assert [(e.start.value, e.end.value) for e in islice(timeline, 3)] == [
        (datetime.date(2012, 11, 27), datetime.date(2012, 11, 28)),
        (datetime.date(2012, 12, 4), datetime.date(2012, 12, 5)),
        (datetime.date(2012, 12, 11), datetime.date(2012, 12, 12)),
    ]


def test_invalid_rrule_until_date() -> None:
    """Test recurrence rule with mismatched UNTIL value from google api."""
    event = Event.parse_obj(
        {
            "summary": "Summary",
            "start": {"date_time": "2020-07-06T18:00:00-07:00"},
            "end": {"date_time": "2020-07-06T22:00:00-07:00"},
            "recurrence": ["RRULE:FREQ=DAILY;UNTIL=20200915"],
        }
    )
    timeline = calendar_timeline([event])
    tzinfo = datetime.timezone(datetime.timedelta(hours=-7))
    assert [(e.start.value, e.end.value) for e in islice(timeline, 3)] == [
        (
            datetime.datetime(2020, 7, 6, 18, 0, tzinfo=tzinfo),
            datetime.datetime(2020, 7, 6, 22, 0, tzinfo=tzinfo),
        ),
        (
            datetime.datetime(2020, 7, 7, 18, 0, tzinfo=tzinfo),
            datetime.datetime(2020, 7, 7, 22, 0, tzinfo=tzinfo),
        ),
        (
            datetime.datetime(2020, 7, 8, 18, 0, tzinfo=tzinfo),
            datetime.datetime(2020, 7, 8, 22, 0, tzinfo=tzinfo),
        ),
    ]


def test_invalid_rrule_until_local_datetime() -> None:
    """Test recurrence rule with mismatched UNTIL value from google api."""
    event = Event.parse_obj(
        {
            "summary": "Summary",
            "start": {"date_time": "2012-11-27T18:00:00"},
            "end": {"date_time": "2012-11-27T19:00:00"},
            "recurrence": ["RRULE:FREQ=WEEKLY;UNTIL=20130225T000000Z;BYDAY=TU"],
        }
    )
    timeline = calendar_timeline([event])
    assert [(e.start.value, e.end.value) for e in islice(timeline, 3)] == [
        (
            datetime.datetime(2012, 11, 27, 18, 0),
            datetime.datetime(2012, 11, 27, 19, 0),
        ),
        (datetime.datetime(2012, 12, 4, 18, 0), datetime.datetime(2012, 12, 4, 19, 0)),
        (
            datetime.datetime(2012, 12, 11, 18, 0),
            datetime.datetime(2012, 12, 11, 19, 0),
        ),
    ]


@pytest.mark.parametrize(
    "time_zone,event_order",
    [
        ("America/Los_Angeles", ["One", "Two", "All Day Event"]),
        ("America/Regina", ["One", "Two", "All Day Event"]),
        ("UTC", ["One", "All Day Event", "Two"]),
        ("Asia/Tokyo", ["All Day Event", "One", "Two"]),
    ],
)
async def test_all_day_iter_order(
    time_zone: str,
    event_order: list[str],
) -> None:
    """Test the sort order of an all day events depending on the time zone."""
    timeline = calendar_timeline(
        [
            Event.parse_obj(
                {
                    "summary": "All Day Event",
                    "start": {"date": "2022-10-08"},
                    "end": {"date": "2022-10-09"},
                }
            ),
            Event.parse_obj(
                {
                    "summary": "One",
                    "start": {"date_time": "2022-10-07T23:00:00+00:00"},
                    "end": {"date_time": "2022-10-07T23:30:00+00:00"},
                }
            ),
            Event.parse_obj(
                {
                    "summary": "Two",
                    "start": {"date_time": "2022-10-08T01:00:00+00:00"},
                    "end": {"date_time": "2022-10-08T02:00:00+00:00"},
                }
            ),
        ],
        zoneinfo.ZoneInfo(time_zone),
    )
    events = timeline.overlapping(
        datetime.datetime(2022, 10, 6, 0, 0, 0, tzinfo=datetime.timezone.utc),
        datetime.datetime(2022, 10, 9, 0, 0, 0, tzinfo=datetime.timezone.utc),
    )
    assert [event.summary for event in events] == event_order


def test_modified_recurrence() -> None:
    """Test a recurring event that was modified with a separate event from the API."""
    events = [
        Event.parse_obj(
            {
                "id": "event-id",
                "summary": "Summary",
                "start": {
                    "dateTime": "2022-06-26T16:00:00-07:00",
                    "timeZone": "America/Los_Angeles",
                },
                "end": {
                    "dateTime": "2022-06-26T19:30:00-07:00",
                    "timeZone": "America/Los_Angeles",
                },
                "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=SU;COUNT=20"],
                "iCalUID": "event-id@google.com",
                "sequence": 1,
            }
        ),
        # Second event was originally in the series above, modified to be 2 hours earlier
        Event.parse_obj(
            {
                "id": "event-id_20221030T230000Z",
                "summary": "Summary",
                "start": {
                    "dateTime": "2022-10-30T14:00:00-07:00",
                    "timeZone": "America/Los_Angeles",
                },
                "end": {
                    "dateTime": "2022-10-30T17:30:00-07:00",
                    "timeZone": "America/Los_Angeles",
                },
                "recurringEventId": "event-id",
                "originalStartTime": {
                    "dateTime": "2022-10-30T16:00:00-07:00",
                    "timeZone": "America/Los_Angeles",
                },
                "iCalUID": "event-id@google.com",
                "sequence": 2,
            }
        ),
    ]

    timeline = calendar_timeline(events)
    assert len(list(timeline)) == 20
    assert len(list(timeline)) == 20  # Ensure operation is repeatable

    events = list(
        timeline.overlapping(
            datetime.date(2022, 10, 29),
            datetime.date(2022, 10, 31),
        )
    )
    assert len(events) == 1


def test_cancelled_recurrence_instancee() -> None:
    """Test a recurring event with a single instance that was cancelled from the API."""
    events = [
        Event.parse_obj(
            {
                "id": "event-id",
                "summary": "Summary",
                "start": {
                    "date": "2022-10-30",
                },
                "end": {
                    "date": "2022-10-31",
                },
                "recurrence": [
                    "RRULE:FREQ=WEEKLY;WKST=SU;BYDAY=SU;COUNT=20",
                ],
                "iCalUID": "event-id@google.com",
                "sequence": 0,
            }
        ),
        # Second event was originally in the series above and was cancelled
        Event.parse_obj(
            {
                "id": "event-id_20221030",
                "status": "cancelled",
                "recurringEventId": "event-id",
                "originalStartTime": {
                    "date": "2022-10-30",
                },
            }
        ),
        Event.parse_obj(
            {
                "id": "event-id_2022113",
                "status": "cancelled",
                "recurringEventId": "event-id",
                "originalStartTime": {
                    "date": "2022-11-13",
                },
            }
        ),
    ]

    timeline = calendar_timeline(events)
    assert len(list(timeline)) == 18
    assert len(list(timeline)) == 18  # ensure operation is repeatable

    events = list(
        timeline.overlapping(
            datetime.date(2022, 10, 29),
            datetime.date(2022, 11, 7),
        )
    )

    assert len(events) == 1
    assert events[0].start.value == datetime.date(2022, 11, 6)

    # Ensure the operation is repeatable
    events = list(
        timeline.overlapping(
            datetime.date(2022, 10, 29),
            datetime.date(2022, 11, 7),
        )
    )
    assert len(events) == 1
