from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class WorkEntryPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    start_time: str = Field(alias="in", serialization_alias="in")
    end_time: str = Field(alias="out", serialization_alias="out")
    counts: bool | None = None
    leave: bool = False

    @field_validator("start_time", "end_time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        try:
            parsed = datetime.strptime(value, "%H:%M")
        except ValueError as exc:
            raise ValueError("time must use HH:MM") from exc
        if parsed.strftime("%H:%M") != value:
            raise ValueError("time must use HH:MM")
        return value

    @model_validator(mode="after")
    def validate_order(self) -> "WorkEntryPayload":
        if self.leave:
            return self
        start = datetime.strptime(self.start_time, "%H:%M")
        end = datetime.strptime(self.end_time, "%H:%M")
        if end <= start:
            raise ValueError("end time must be later than start time")
        return self


class PreferencesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Literal["cool", "teal"]


def validate_work_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD") from exc
    if parsed.isoformat() != value:
        raise ValueError("date must use YYYY-MM-DD")
    return value
