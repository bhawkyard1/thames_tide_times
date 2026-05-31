import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from shapely.geometry import Point, LineString, MultiLineString
from shapely.ops import nearest_points
from sqlmodel import Session, select, SQLModel

from thames_tide_times.constants import engine
from thames_tide_times.models import Station


@asynccontextmanager
async def lifespan(_: FastAPI):
    initialize_db()
    yield


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


@app.get("/closest_point_on_thames")
def closest_point_on_thames(lat: float, lon: float) -> tuple[float, float]:
    point = Point(lat, lon)
    nearest = nearest_points(point, thames_path)[1]
    return nearest.x, nearest.y


def initialize_db():
    SQLModel.metadata.create_all(engine)

    all_stations = [
        Station(
            name="Richmond Lock",
            station_id="0116",
            latitude=51.46222,
            longitude=-0.31722,
        ),
        Station(
            name="Kew Bridge",
            station_id="0115A",
            latitude=51.486978,
            longitude=-0.287419,
        ),
        Station(
            name="Hammersmith Bridge",
            station_id="0115",
            latitude=51.462496,
            longitude=-0.316761,
        ),
        Station(
            name="Albert Bridge",
            station_id="0114",
            latitude=51.482364,
            longitude=-0.166756,
        ),
        Station(
            name="Chelsea Bridge",
            station_id="0113A",
            latitude=51.484548,
            longitude=-0.149784,
        ),
        Station(
            name="Tower Pier",
            station_id="0113",
            latitude=51.506684,
            longitude=-0.079555,
        ),
        Station(
            name="North Woolwich",
            station_id="0112",
            latitude=51.504687,
            longitude=0.082693,
        ),
        Station(
            name="Erith",
            station_id="0111B",
            latitude=51.484911,
            longitude=0.186495,
        ),
    ]

    with Session(engine) as session:
        for station in all_stations:
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
