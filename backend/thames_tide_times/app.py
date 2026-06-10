import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import timedelta, datetime
from pathlib import Path

import redis
import requests
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy import func
from sqlmodel import Session, select, SQLModel, and_

from thames_tide_times.constants import engine
from thames_tide_times.models import Station, TideEvent, TideType, TideData


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    yield
    red.close()


logger = logging.getLogger("uvicorn.error")
red = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)

thames_path_path = Path(__file__).parent / "thames_path.json"
thames_path = LineString(json.loads(thames_path_path.read_text()))

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://tides.hawkyard.xyz"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/stations")
@limiter.limit("10/minute")
def stations(request: Request) -> list[Station]:
    """Return all tide measuring stations."""
    with Session(engine) as session:
        statement = select(Station)
        results = session.exec(statement)
        return list(results)


def _get_ukho_tide_events(station: Station) -> list[dict]:
    """For a given station, retrieve the relevant tide events from the UKHO api."""
    url = f"https://admiraltyapi.azure-api.net/uktidalapi/api/V1/Stations/{station.station_id}/TidalEvents"
    res = requests.get(
        url,
        params={
            "duration": 7,
            "subscription-key": Path("/run/secrets/tidal_api_key").read_text().strip()
        }
    )
    res.raise_for_status()
    return res.json()


def _retrieve_tide_events():
    """Retrieve tide events from the uk hydrographic office api and put them in our database. Clean up old events with
    a time of less than a day ago.
    """
    with Session(engine) as session:
        for station in session.exec(select(Station)).all():
            # We've still got tide events predictions in the future for this station?
            # Skip it, avoid hitting the API again.
            if station.tide_events and station.tide_events[-1].time > datetime.now():
                continue

            logger.info("Querying tide events from UKHO API...")
            data = _get_ukho_tide_events(station)
            tide_events_new = [TideEvent.from_tides_api(station=station, data=item) for item in data]
            session.add_all(tide_events_new)

        # Delete old tide events, we don't care about these.
        for tide_event in session.exec(
                select(TideEvent).where(TideEvent.time < datetime.now() - timedelta(days=1))
        ).all():
            session.delete(tide_event)

        session.commit()


def _next_tide_event(station: Station, tide_type: TideType | None = None) -> TideEvent:
    if tide_type is None:
        logger.info(f"Looking for next tide at {station.name}")
    else:
        logger.info(f"Looking for next {tide_type} tide at {station.name}")

    redis_key = f"next_tide_event:{station.id=},{tide_type=}"
    cached = red.get(redis_key)
    if cached:
        result = TideEvent.model_validate(json.loads(cached))
        logger.info(f"Found cached {result}")
        return result

    if tide_type is None:
        conditions = TideEvent.station_id == station.id, TideEvent.time > datetime.now()
    else:
        conditions = TideEvent.station_id == station.id, TideEvent.tide_type == tide_type, TideEvent.time > datetime.now()
    with Session(engine) as session:
        event = session.exec(
            select(TideEvent)
            .where(
                and_(*conditions)
            )
            .order_by(TideEvent.time)
        ).first()
        if not isinstance(event, TideEvent):
            raise ValueError(
                f"Could not find a future TideEvent at {station.name} after {datetime.now()}. Expected a TideEvent, "
                f"got {event!r}. Is the tide event database being populated correctly?"
            )

    red.set(redis_key, event.model_dump_json())
    logger.info(f"Found {event}")
    logger.info(f"Setting expiry at {event.time}")
    red.expireat(redis_key, event.time)
    return event


def _closest_tide_event(station: Station, time: datetime, event_type: TideType) -> TideEvent:
    """Given a station id, a datetime, and a tide type, find the closest tide event at this station to `time`, of
    `event_type`. This may be before or after `time`."""
    logger.info(f"Looking for a {event_type} tide at {station.name} close to {time}...")
    with Session(engine) as session:
        diff = func.extract("epoch", TideEvent.time - time)
        result = session.exec(
            select(TideEvent)
            .where(
                and_(TideEvent.station_id == station.id, TideEvent.tide_type == event_type)
            )
            .order_by(func.abs(diff))
            .limit(1)
        ).one()
    logger.info(f"Got {result.tide_type} tide at {result.time}")
    return result


class _LatLng(BaseModel):
    latlng: tuple[float, float]


def _closest_point_on_thames(lat: float, lng: float):
    redis_key = f"closest_point_on_thames:{lat=},{lng=}"
    cached = red.get(redis_key)
    if cached:
        red.expire(redis_key, 60)
        return _LatLng(latlng=json.loads(cached)).latlng

    point = Point(lat, lng)
    nearest_on_thames = nearest_points(point, thames_path)[1]
    red.set(redis_key, json.dumps((nearest_on_thames.x, nearest_on_thames.y)))
    red.expire(redis_key, 60)
    return point.x, point.y


@app.get("/closest_point_on_thames")
@limiter.limit("100/minute")
def closest_point_on_thames(lat: float, lng: float, request: Request) -> tuple[float, float]:
    return _closest_point_on_thames(lat, lng)


def _find_next_tide_pair(
        station_a: Station,
        station_b: Station,
        tide_type: TideType | None = None
) -> tuple[TideEvent, TideEvent]:
    """We want to find matching tide events at two tide measuring stations and interpolate before them to arrive at
    our prediction. Given two stations, a and b, and optionally a desired tide type, we'll query the next tide events
    at each station. We will take the closest of the two, and find the closest tide event of the same type, at the
    other station. This should return us two TideEvents that we can interpolate between.
    """
    a_next_event = _next_tide_event(station_a, tide_type)
    b_next_event = _next_tide_event(station_b, tide_type)

    if a_next_event.time < b_next_event.time:
        logger.info(f"{a_next_event} sooner, looking for closest {a_next_event.tide_type} at {station_b.name}")
        b_matching_event = _closest_tide_event(
            station=station_b,
            time=a_next_event.time,
            event_type=a_next_event.tide_type,
        )
        return a_next_event, b_matching_event
    logger.info(f"{b_next_event} sooner, looking for closest {b_next_event.tide_type} at {station_a.name}")
    a_matching_event = _closest_tide_event(
        station=station_a,
        time=b_next_event.time,
        event_type=b_next_event.tide_type,
    )
    return a_matching_event, b_next_event


@app.get("/next_tide_events_at_station")
@limiter.limit("10/minute")
def next_tide_events_at_station(station_id: int, request: Request) -> tuple[TideEvent, TideEvent]:
    with Session(engine) as session:
        station = session.exec(select(Station).where(Station.id == station_id)).one()
    next_tide = _next_tide_event(station)
    if next_tide.tide_type == TideType.HIGH:
        return next_tide, _next_tide_event(station, TideType.LOW)
    return next_tide, _next_tide_event(station, TideType.HIGH)


@app.get("/next_tide_events_from_position")
@limiter.limit("50/minute")
def next_tide_events_from_position(lat: float, lng: float, request: Request) -> tuple[TideData, TideData]:
    """Return the next two inflection points of the tide, at the closest point in the thames to lat/lng.
    To do this, we:
    * Given lat, lng representing our current position, find the closest location on the path of the thames.
    * Find the thames tide station before our closest-thames-location, and the thames tide station after.
    * Work the interpolation, that our closest-thames-location is at, relative to the previous and next
    station, zero to one, zero being the previous station location, and one being the next station location.
    * Using this value, interpolate the time of the next expected low tide and high tide.

    The expected tide times are sourced from the uk hydrographic office api. This is trickier than it might first
    appear, because we might encounter cases where a tide inflection has already occurred at one of our prev/next
    tide stations, but not yet propagated to the other one, meaning we might not get values out of the hydrographic
    API that we can safely interpolate between. The hydrographic office api doesn't let us query historical tide
    event predictions, so we store these in our database.
    """
    redis_key = f"next_tide_event_from_position:{lat=},{lng=}"
    cached = red.get(redis_key)
    if cached:
        loaded = json.loads(cached)
        return TideData.model_validate(loaded[0]), TideData.model_validate(loaded[1])

    _retrieve_tide_events()

    nearest_on_thames = Point(*_closest_point_on_thames(lat, lng))
    interp = thames_path.line_locate_point(nearest_on_thames, normalized=True)
    with Session(engine) as session:
        prev_station = session.exec(
            select(Station)
            .where(Station.interp < interp)
            .order_by(Station.interp.desc())
            .limit(1)
        ).one()
        next_station = session.exec(
            select(Station)
            .where(Station.interp > interp)
            .order_by(Station.interp)
            .limit(1)
        ).one()

    relative_interp = (interp - prev_station.interp) / (next_station.interp - prev_station.interp)

    first_tides = _find_next_tide_pair(prev_station, next_station)
    if first_tides[0].tide_type == TideType.HIGH:
        second_tides_type = TideType.LOW
    else:
        second_tides_type = TideType.HIGH
    second_tides = _find_next_tide_pair(prev_station, next_station, second_tides_type)

    first_tide_interp = TideEvent.lerp(first_tides[0], first_tides[1], relative_interp)
    second_tide_interp = TideEvent.lerp(second_tides[0], second_tides[1], relative_interp)

    red.set(redis_key, f"[{first_tide_interp.model_dump_json()},{second_tide_interp.model_dump_json()}]")
    red.expireat(redis_key, min(first_tide_interp.time, second_tide_interp.time))

    return first_tide_interp, second_tide_interp


def initialize_db():
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        for name, station_id, lat, lon in ([
            ["Richmond Lock", "0116", 51.46222, -0.31722],
            ["Kew Bridge", "0115A", 51.486978, -0.287419],
            ["Hammersmith Bridge", "0115", 51.462496, -0.316761],
            ["Albert Bridge", "0114", 51.482364, -0.166756],
            ["Chelsea Bridge", "0113A", 51.484548, -0.149784],
            ["Tower Pier", "0113", 51.506684, -0.079555],
            ["North Woolwich", "0112", 51.504687, 0.082693],
            ["Erith", "0111B", 51.484911, 0.186495],
        ]):
            interp = thames_path.line_locate_point(Point(lat, lon), normalized=True)
            station = Station(
                name=name,
                station_id=station_id,
                latitude=lat,
                longitude=lon,
                interp=interp,
            )
            statement = select(Station).where(Station.station_id == station.station_id)
            results = session.exec(statement)
            existing_station = results.one_or_none()
            if existing_station:
                existing_station.name = station.name
                existing_station.station_id = station.station_id
                existing_station.latitude = station.latitude
                existing_station.longitude = station.longitude
                session.add(existing_station)
            else:
                session.add(station)
        session.commit()

    _retrieve_tide_events()
