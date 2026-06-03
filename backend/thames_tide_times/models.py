from datetime import datetime
from enum import Enum
from typing import Self, Literal

from pydantic import BaseModel
from sqlmodel import Field, Relationship, SQLModel


class Station(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    """The name of the station, in plain text, suitable for display."""
    station_id: str = Field(unique=True, index=True)
    """The id of the station as defined by the uk hydrographic office. This wires up our station to a station in their 
    API.
    """
    latitude: float
    """The latitude of the station in decimal degrees."""
    longitude: float
    """The longitude of the station in decimal degrees."""
    interp: float
    """0-1 value indicating how far along our thames path this station lies."""
    tide_events: list["TideEvent"] = Relationship(back_populates="station")


class TideType(str, Enum):
    HIGH = "high"
    LOW = "low"


class _TideEventRaw(BaseModel):
    EventType: Literal["HighWater", "LowWater"]
    DateTime: datetime
    Height: float


class TideEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tide_type: TideType
    time: datetime
    height: float

    station_id: int = Field(default=None, foreign_key="station.id")
    station: Station = Relationship(back_populates="tide_events")

    @classmethod
    def from_tides_api(cls, station: Station, data: dict) -> Self:
        raw = _TideEventRaw.model_validate(data)
        return cls(
            tide_type=TideType.HIGH if raw.EventType == "HighWater" else TideType.LOW,
            time=raw.DateTime,
            height=raw.Height,
            station_id=station.id,
        )

    @classmethod
    def lerp(cls, event_1: Self, event_2: Self, interp: float) -> Self:
        if event_1.tide_type != event_2.tide_type:
            raise ValueError(f"Cannot interpolate between {event_1} and {event_2} as they have different tide_types!")
        return cls(
            tide_type=event_1.tide_type,
            time=event_1.time + (event_2.time - event_1.time) * interp,
            height=event_1.height + (event_2.height - event_1.height) * interp,
        )
