"""Tests for iterating over events on a timeline."""

# pylint: disable=too-many-lines

from __future__ import annotations

import datetime
import zoneinfo
from itertools import islice

import pytest
from freezegun import freeze_time

from gcal_sync.model import DateOrDatetime, Event, SyntheticEventId
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
    """Test chronological iteration of timeline with all day/non-all day events."""
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
        id="event-id",
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


def test_recurrence_dst_tz_iteration() -> None:
    """Test recurrence rule across a dst boundary."""
    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Summary",
            "start": {
                "date_time": "2022-09-09T13:00:00+02:00",
                "timezone": "Europe/Budapest",
            },
            "end": {
                "date_time": "2022-09-09T14:00:00+02:00",
                "timezone": "Europe/Budapest",
            },
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=FR;COUNT=10"],
        }
    )
    timeline = calendar_timeline([event])
    assert [e.start.value.isoformat() for e in timeline] == [
        "2022-09-09T13:00:00+02:00",
        "2022-09-16T13:00:00+02:00",
        "2022-09-23T13:00:00+02:00",
        "2022-09-30T13:00:00+02:00",
        "2022-10-07T13:00:00+02:00",
        "2022-10-14T13:00:00+02:00",
        "2022-10-21T13:00:00+02:00",
        "2022-10-28T13:00:00+02:00",
        "2022-11-04T13:00:00+01:00",  # First event in dst
        "2022-11-11T13:00:00+01:00",
    ]


def test_recurrence_dst_tz_start_after() -> None:
    """Test reucrrence rule 'start_after' across a dst boundary."""
    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Summary",
            "start": {
                "date_time": "2022-09-09T13:00:00+02:00",
                "timezone": "Europe/Budapest",
            },
            "end": {
                "date_time": "2022-09-09T14:00:00+02:00",
                "timezone": "Europe/Budapest",
            },
            "recurrence": ["RRULE:FREQ=WEEKLY;BYDAY=FR;COUNT=10"],
        }
    )
    timeline = calendar_timeline([event])

    events = timeline.start_after(
        datetime.datetime(2022, 11, 4, 10, 00, 0, tzinfo=datetime.timezone.utc),
    )
    assert len(list(events)) == 2

    events = timeline.start_after(
        datetime.datetime(2022, 11, 4, 11, 59, 0, tzinfo=datetime.timezone.utc),
    )
    assert len(list(events)) == 2

    events = timeline.start_after(
        datetime.datetime(2022, 11, 4, 12, 0, 0, tzinfo=datetime.timezone.utc),
    )
    assert len(list(events)) == 1


def test_invalid_rrule_until_datetime() -> None:
    """Test recurrence rule with mismatched UNTIL value from google api."""
    event = Event.parse_obj(
        {
            "id": "event-id",
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


def test_invalid_rrule_until_datetime_exdate() -> None:
    """Test recurrence rule with mismatched EXDATE value from google api."""
    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {"date": "2012-11-27"},
            "end": {"date": "2012-11-28"},
            "recurrence": [
                "EXDATE;TZID=Europe/Helsinki:20121204T000000",
                "RRULE:FREQ=WEEKLY;UNTIL=20130225T000000Z;BYDAY=TU",
            ],
        }
    )
    timeline = calendar_timeline([event])
    assert [(e.start.value, e.end.value) for e in islice(timeline, 3)] == [
        (datetime.date(2012, 11, 27), datetime.date(2012, 11, 28)),
        (datetime.date(2012, 12, 11), datetime.date(2012, 12, 12)),
        (datetime.date(2012, 12, 18), datetime.date(2012, 12, 19)),
    ]


def test_invalid_rrule_until_datetime_rate() -> None:
    """Test recurrence rule with mismatched RDATE value from google api."""
    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {"date": "2012-11-27"},
            "end": {"date": "2012-11-28"},
            "recurrence": [
                "RDATE;TZID=Europe/Helsinki:20121203T000000",
                "RRULE:FREQ=WEEKLY;UNTIL=20130225T000000Z;BYDAY=TU",
            ],
        }
    )
    timeline = calendar_timeline([event])
    assert [(e.start.value, e.end.value) for e in islice(timeline, 3)] == [
        (datetime.date(2012, 11, 27), datetime.date(2012, 11, 28)),
        (datetime.date(2012, 12, 3), datetime.date(2012, 12, 4)),
        (datetime.date(2012, 12, 4), datetime.date(2012, 12, 5)),
    ]


def test_invalid_rrule_until_date() -> None:
    """Test recurrence rule with mismatched UNTIL value from google api."""
    event = Event.parse_obj(
        {
            "id": "event-id",
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
            "id": "event-id",
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


def test_invalid_rrule_until_spurious_date() -> None:
    """Test recurrence rule with mismatched UNTIL value from google api."""
    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {"date": "2023-08-02"},
            "end": {"date": "2023-08-01"},
            "recurrence": [
                "RRULE:DATE;TZID=Europe/Warsaw:20230818T020000,20230915T020000,20231013T020000,20231110T010000,20231208T010000"
            ],
        }
    )
    timeline = calendar_timeline([event])
    assert [(e.start.value, e.end.value) for e in islice(timeline, 6)] == [
        (datetime.date(2023, 8, 18), datetime.date(2023, 8, 19)),
        (datetime.date(2023, 9, 15), datetime.date(2023, 9, 16)),
        (datetime.date(2023, 10, 13), datetime.date(2023, 10, 14)),
        (datetime.date(2023, 11, 10), datetime.date(2023, 11, 11)),
        (datetime.date(2023, 12, 8), datetime.date(2023, 12, 9)),
    ]
    assert event.recurrence == [
        "RDATE;TZID=Europe/Warsaw:20230818T020000,20230915T020000,20231013T020000,20231110T010000,20231208T010000"
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
                    "id": "event-id-all-day",
                    "summary": "All Day Event",
                    "start": {"date": "2022-10-08"},
                    "end": {"date": "2022-10-09"},
                }
            ),
            Event.parse_obj(
                {
                    "id": "event-id-1",
                    "summary": "One",
                    "start": {"date_time": "2022-10-07T23:00:00+00:00"},
                    "end": {"date_time": "2022-10-07T23:30:00+00:00"},
                }
            ),
            Event.parse_obj(
                {
                    "id": "event-id-2",
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


def test_recurrence_fields() -> None:
    """Test recurrence rules for day frequency."""
    event = Event(
        id="event-id",
        summary="summary",
        start=DateOrDatetime.parse(
            datetime.datetime(
                2022, 8, 4, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
            )
        ),
        end=DateOrDatetime.parse(
            datetime.datetime(
                2022, 8, 4, 10, 00, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
            )
        ),
        recurrence=["RRULE:FREQ=DAILY;UNTIL=20220904T000000Z"],
    )
    timeline_iter = iter(calendar_timeline([event]))
    event1 = next(timeline_iter)
    assert event1.id
    assert event1.summary == "summary"
    sid = SyntheticEventId.parse(event1.id)
    assert sid.original_event_id == "event-id"
    assert sid.dtstart == datetime.datetime(
        2022, 8, 4, 16, 30, tzinfo=datetime.timezone.utc
    )
    assert event1.start == DateOrDatetime.parse(
        datetime.datetime(
            2022, 8, 4, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
        )
    )
    assert event1.original_start_time == DateOrDatetime.parse(
        datetime.datetime(
            2022, 8, 4, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
        )
    )

    event2 = next(timeline_iter)
    assert event2.summary == "summary"
    assert event2.id
    sid = SyntheticEventId.parse(event2.id)
    assert sid.original_event_id == "event-id"
    assert sid.dtstart == datetime.datetime(
        2022, 8, 5, 16, 30, tzinfo=datetime.timezone.utc
    )
    assert event2.start == DateOrDatetime.parse(
        datetime.datetime(
            2022, 8, 5, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
        )
    )
    assert event2.original_start_time == DateOrDatetime.parse(
        datetime.datetime(
            2022, 8, 4, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
        )
    )

    event3 = next(timeline_iter)
    assert event3.summary == "summary"
    assert event3.id
    sid = SyntheticEventId.parse(event3.id)
    assert sid.original_event_id == "event-id"
    assert sid.dtstart == datetime.datetime(
        2022, 8, 6, 16, 30, tzinfo=datetime.timezone.utc
    )
    assert event3.start == DateOrDatetime.parse(
        datetime.datetime(
            2022, 8, 6, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
        )
    )
    assert event3.original_start_time == DateOrDatetime.parse(
        datetime.datetime(
            2022, 8, 4, 9, 30, 0, tzinfo=zoneinfo.ZoneInfo("America/Los_Angeles")
        )
    )


def test_all_day_recurrence_fields() -> None:
    """Test recurrence rules for day frequency."""
    event = Event(
        id="event-id",
        summary="summary",
        start=DateOrDatetime.parse(datetime.date(2022, 8, 4)),
        end=DateOrDatetime.parse(datetime.date(2022, 8, 5)),
        recurrence=["RRULE:FREQ=DAILY;UNTIL=20220904"],
    )

    timeline_iter = iter(calendar_timeline([event]))
    event1 = next(timeline_iter)
    assert event1.summary == "summary"
    assert event1.id
    sid = SyntheticEventId.parse(event1.id)
    assert sid.original_event_id == "event-id"
    assert sid.dtstart == datetime.date(2022, 8, 4)
    assert event1.original_start_time == DateOrDatetime.parse(datetime.date(2022, 8, 4))

    event2 = next(timeline_iter)
    assert event2.summary == "summary"
    assert event2.id
    sid = SyntheticEventId.parse(event2.id)
    assert sid.original_event_id == "event-id"
    assert sid.dtstart == datetime.date(2022, 8, 5)
    assert event2.original_start_time == DateOrDatetime.parse(datetime.date(2022, 8, 4))

    event3 = next(timeline_iter)
    assert event3.summary == "summary"
    assert event3.id
    sid = SyntheticEventId.parse(event3.id)
    assert sid.original_event_id == "event-id"
    assert sid.dtstart == datetime.date(2022, 8, 6)
    assert event3.original_start_time == DateOrDatetime.parse(datetime.date(2022, 8, 4))


def test_missing_event_id() -> None:
    """Test an invalid event can't be used for recurring events."""
    event = Event(
        summary="summary",
        start=DateOrDatetime.parse(datetime.date(2022, 8, 4)),
        end=DateOrDatetime.parse(datetime.date(2022, 8, 5)),
        recurrence=["RRULE:FREQ=DAILY;UNTIL=20220904"],
    )
    timeline_iter = iter(calendar_timeline([event]))

    with pytest.raises(ValueError, match="Expected event to have event id"):
        next(timeline_iter)


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
        # Second event was originally in series above, modified as 2 hours earlier
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


def test_rdate_params() -> None:
    """Test recurrence rule with additional parameters unsupported by dateutil.rrule"""

    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {
                "date_time": "2022-07-14T10:00:00+00:00",
                "timezone": "Europe/Helsinki",
            },
            "end": {
                "date_time": "2022-07-14T11:00:00+00:00",
                "timezone": "Europe/Helsinki",
            },
            "recurrence": [
                "RDATE;TZID=Europe/Helsinki:20220210T130000,20220310T130000,20220414T130000",
                "RRULE:FREQ=MONTHLY;UNTIL=20230309T110000Z;INTERVAL=1;BYDAY=2TH",
            ],
        }
    )

    timeline = calendar_timeline([event], zoneinfo.ZoneInfo("UTC"))
    events = list(
        timeline.overlapping(
            datetime.date(2022, 2, 1),
            datetime.date(2022, 4, 5),
        )
    )
    assert len(events) == 2


def test_all_day_rrule_and_rdate() -> None:
    """Test recurrence rule with rdate and all day events."""

    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {
                "date": "2022-04-19",
            },
            "end": {
                "date": "2022-04-20",
            },
            "recurrence": [
                "RDATE;VALUE=DATE:20221115,20221120,20221125,20221205",
                "RRULE:FREQ=DAILY;UNTIL=20221030;INTERVAL=5",
            ],
        }
    )

    timeline = calendar_timeline([event], zoneinfo.ZoneInfo("UTC"))
    events = list(
        timeline.overlapping(
            datetime.date(2022, 4, 1),
            datetime.date(2022, 12, 30),
        )
    )
    starts = {event.start.value for event in events}
    assert datetime.date(2022, 4, 19) in starts
    assert datetime.date(2022, 4, 20) not in starts
    assert datetime.date(2022, 4, 24) in starts
    assert datetime.date(2022, 10, 29) not in starts
    assert datetime.date(2022, 11, 15) in starts
    assert datetime.date(2022, 11, 16) not in starts
    assert datetime.date(2022, 11, 20) in starts


def test_all_day_rrule_and_exdate() -> None:
    """Test recurrence rule with exdate."""

    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {
                "date": "2022-04-19",
            },
            "end": {
                "date": "2022-04-20",
            },
            "recurrence": [
                "EXDATE;VALUE=DATE:20220422,20220423",
                "RRULE:FREQ=DAILY;UNTIL=20220425",
            ],
        }
    )

    timeline = calendar_timeline([event], zoneinfo.ZoneInfo("UTC"))
    events = list(
        timeline.overlapping(
            datetime.date(2022, 4, 1),
            datetime.date(2022, 5, 30),
        )
    )
    starts = {event.start.value for event in events}
    assert datetime.date(2022, 4, 19) in starts
    assert datetime.date(2022, 4, 20) in starts
    assert datetime.date(2022, 4, 21) in starts
    assert datetime.date(2022, 4, 22) not in starts
    assert datetime.date(2022, 4, 23) not in starts
    assert datetime.date(2022, 4, 24) in starts
    assert datetime.date(2022, 4, 25) in starts
    assert datetime.date(2022, 4, 26) not in starts


def test_unknown_timezone() -> None:
    """Test timezone evaluation when the timezone returned from the API is not known."""

    event = Event.parse_obj(
        {
            "id": "event-id",
            "summary": "Summary",
            "start": {
                "date_time": "2022-11-12T10:00:00",
                "timezone": "GMT+02:00",
            },
            "end": {
                "date_time": "2022-11-12T11:00:00",
                "timezone": "GMT+02:00",
            },
        }
    )

    timeline = calendar_timeline([event], zoneinfo.ZoneInfo("UTC"))
    events = list(
        timeline.overlapping(
            datetime.date(2022, 11, 1),
            datetime.date(2022, 11, 30),
        )
    )
    assert len(events) == 1
    assert events[0].start.value == datetime.datetime(2022, 11, 12, 10, 00)
    assert events[0].end.value == datetime.datetime(2022, 11, 12, 11, 00)


def test_yearly_bymonthday_rrule() -> None:
    """Test FREQ=YEARLY rules returned from the API with BYMONTHDAY rules."""
    event = Event.parse_obj(
        {
            "id": "some-event-id",
            "summary": "Summary",
            "start": {"date": "2022-09-07"},
            "end": {
                "date": "2022-09-08",
            },
            "recurrence": ["RRULE:FREQ=YEARLY;BYMONTHDAY=7;COUNT=3"],
        }
    )
    timeline = calendar_timeline([event])
    assert [e.start.value.isoformat() for e in timeline] == [
        "2022-09-07",
        "2023-09-07",
        "2024-09-07",
    ]
