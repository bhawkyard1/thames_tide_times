from datetime import datetime, timedelta
import sys
from unittest import mock

sys.path.append("/code")

from fastapi.testclient import TestClient
import pytest

from shapely import LineString, Point
from sqlmodel import Session, select
from thames_tide_times import app
from thames_tide_times.constants import engine
from thames_tide_times.models import Station, TideEvent, TideType


@pytest.fixture(scope="session")
def mock_ukho_tide_events():
    with mock.patch("thames_tide_times.app._get_ukho_tide_events") as m:
        m.return_value = []
        yield m


@pytest.fixture(scope="session")
def client(mock_ukho_tide_events):
    with TestClient(app.app) as client:
        yield client


@pytest.fixture(scope="session")
def mock_thames_path():
    orig_path = app.thames_path
    app.thames_path = LineString(
        [[50.0, -5.0], [50.0, 0.0], [50.0, 5.0]]
    )
    yield app.thames_path
    app.thames_path = orig_path


@pytest.fixture(scope="session")
def mock_stations(mock_thames_path):
    with Session(engine) as session:
        for station in session.exec(select(Station)):
            session.delete(station)
        stations = []
        for name, station_id, lat, lon in ([
            ["Westminster", "001", 50, -5],
            ["Greenwich", "002", 50, 0],
            ["Erith", "003", 50, 5],
        ]):
            interp = mock_thames_path.line_locate_point(Point(lat, lon), normalized=True)
            station = Station(
                name=name,
                station_id=station_id,
                latitude=lat,
                longitude=lon,
                interp=interp,
            )
            session.add(station)
            stations.append(station)
        session.commit()

        for station in stations:
            session.refresh(station)

        yield stations

        for station in stations:
            session.delete(station)
        session.commit()


@pytest.fixture(scope="session")
def mock_tide_events(mock_stations: list[Station]):
    with Session(engine) as session:
        for station in session.exec(select(TideEvent)):
            session.delete(station)

        events = []
        westminster, greenwich, erith = mock_stations
        now = datetime.now()
        for type_, time, height, station_id in ([
            [TideType.HIGH, now - timedelta(hours=1), 8, westminster.id],
            [TideType.LOW, now + timedelta(hours=11), 0, westminster.id],
            [TideType.HIGH, now + timedelta(hours=23), 7, westminster.id],
            [TideType.LOW, now + timedelta(hours=35), 1, westminster.id],
        ]):
            event = TideEvent(
                tide_type=type_,
                time=time,
                height=height,
                station_id=station_id,
            )
            events.append(event)
            session.add(event)
        session.commit()

        for event in events:
            session.refresh(event)

        yield events

        for event in events:
            session.delete(event)
        session.commit()
