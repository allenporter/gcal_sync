"""Library for data model for local calendar objects."""

from __future__ import annotations

import datetime
from typing import Any, Optional, Union

from pydantic import BaseModel, validator

DATE_STR_FORMAT = "%Y-%m-%d"


class Calendar(BaseModel):
    """Metadata associated with a calendar."""

    id: str
    summary: str
    description: Optional[str]
    location: Optional[str]
    timezone: Optional[str]


class Event(BaseModel):
    """A single event on a calendar."""

    id: str
    summary: str
    start: Union[datetime.datetime, datetime.date]
    end: Union[datetime.datetime, datetime.date]
    description: Optional[str]
    location: Optional[str]

    @validator("start", pre=True)
    def start_date_from_api(cls, v: Any) -> Union[datetime.date, datetime.datetime]:
        if not isinstance(v, dict):
            raise ValueError("Unexpected value was not dictionary")
        if "dateTime" in v:
            return datetime.datetime.fromisoformat(v["dateTime"])
        if "date" in v:
            return datetime.datetime.strptime(v["date"], DATE_STR_FORMAT).date()
        raise ValueError("Unexpected missing date or dateTime value")

    @validator("end", pre=True)
    def end_date_from_api(cls, v: Any) -> Union[datetime.date, datetime.datetime]:
        if not isinstance(v, dict):
            raise ValueError("Unexpected value was not dictionary")
        if "dateTime" in v:
            return datetime.datetime.fromisoformat(v["dateTime"])
        if "date" in v:
            return datetime.datetime.strptime(v["date"], DATE_STR_FORMAT).date()
        raise ValueError("Unexpected missing date or dateTime value")
