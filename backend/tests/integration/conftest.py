import sys
from unittest import mock

from starlette.testclient import TestClient

sys.path.append("/code")

import pytest

from shapely import LineString, Point
from sqlmodel import Session, select
from thames_tide_times import app
from thames_tide_times.constants import engine
from thames_tide_times.models import Station, TideEvent


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
        for event in session.exec(select(TideEvent)):
            session.delete(event)
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

