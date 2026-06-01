from datetime import datetime
from enum import Enum

from sqlmodel import Field, Relationship, SQLModel


class Station(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    station_id: str = Field(unique=True, index=True)
    latitude: float
    longitude: float
    interp: float
    """0-1 value indicating how far along our thames path this station lies."""
    tide_events: list["TideEvent"] = Relationship(back_populates="station")


class TideType(str, Enum):
    HIGH = "high"
    LOW = "low"


class TideEvent(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    tide_type: TideType
    time: datetime

    station_id: int | None = Field(default=None, foreign_key="station.id")
    station: Station | None = Relationship(back_populates="tide_events")