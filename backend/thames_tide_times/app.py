import json
import os
from contextlib import asynccontextmanager
from datetime import timedelta
from pathlib import Path

import redis
import requests
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from sqlmodel import Session, select, SQLModel

from thames_tide_times.constants import engine
from thames_tide_times.models import Station, TideEvent


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    yield
    red.close()


red = redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
tide_prediction_max_diff_minutes = 120
"""From time to time the predicted time of a tide event in the hydrographic API may change. If we are pulling tide 
events from the API and putting them in our database and we encounter a tide in our database and a tide in the API 
of the same type, with less than this number of minutes between them, we consider them the same tide and update the 
existing one."""
app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this in production
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/stations")
def stations() -> list[Station]:
    """Return all tide measuring stations."""
    with Session(engine) as session:
        statement = select(Station)
        results = session.exec(statement)
        return list(results)


thames_path_path = Path(__file__).parent / "thames_path.json"
thames_path = LineString(json.loads(thames_path_path.read_text()))
@app.post("/retrieve_tide_events")
def retrieve_tide_events():
    """Retrieve tide events from the uk hydrographic office api and put them in our database."""
    with Session(engine) as session:
        statement = select(Station)
        for station in session.exec(statement).all():
            url = f"https://admiraltyapi.azure-api.net/uktidalapi/api/V1/Stations/{station.station_id}/TidalEvents"
            res = requests.get(
                url,
                params={
                    "duration": 14,
                    "subscription-key": Path("/run/secrets/tidal_api_key").read_text()
                }
            )
            res.raise_for_status()
            tide_events_new = [TideEvent.from_tides_api(item) for item in res.json()]

            for tide_event_new in tide_events_new:
                tide_statement = select(TideEvent).where(TideEvent.station_id == station.station_id)
                existing_tide_event: TideEvent | None = None
                for tide_event in session.exec(tide_statement).all():
                    if tide_event.tide_type != tide_event_new.tide_type:
                        continue
                    earlier = min(tide_event.time, tide_event_new.time)
                    later = max(tide_event.time, tide_event_new.time)
                    if (later - earlier) < timedelta(minutes=tide_prediction_max_diff_minutes):
                        existing_tide_event = tide_event
                        existing_tide_event.time = tide_event_new.time
                        existing_tide_event.height = tide_event_new.height
                        break

                if existing_tide_event is None:
                    existing_tide_event = tide_event_new

                session.add(existing_tide_event)

        session.commit()



class StationInterp(BaseModel):
    previous_station: Station
    next_station: Station
    interp: float


@app.get("/get_tide_interp")
def get_tide_interp(lat: float, lon: float) -> StationInterp:
    """Given a lat/lng point on our map, find the closest point on the thames, then from that point, the ids of the
    two stations that our point lies between, and the interpolation between them."""
    redis_key = f"get_tide_interp:{lat=},{lon=}"
    cached = red.get(redis_key)
    if cached:
        red.expire(redis_key, 60)
        raw = json.loads(cached)
        return StationInterp(**raw)

    point = Point(lat, lon)
    nearest_on_thames = nearest_points(point, thames_path)[1]
    interp = thames_path.line_locate_point(nearest_on_thames, normalized=True)
    with Session(engine) as session:
        prev_station = session.exec(
            select(Station).where(Station.interp < interp).order_by(Station.interp.desc())
        ).first()
        next_station = session.exec(
            select(Station).where(Station.interp > interp).order_by(Station.interp)
        ).first()
    station_interp = StationInterp(
        previous_station=prev_station,
        next_station=next_station,
        interp=(interp - prev_station.interp) / (next_station.interp - prev_station.interp),
    )
    red.set(redis_key, station_interp.model_dump_json())
    red.expire(redis_key, 60)
    return station_interp


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
