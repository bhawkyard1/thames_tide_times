from datetime import datetime, timedelta

from thames_tide_times.models import Station, TideEvent, TideData, TideType


def test_stations(client, mock_stations):
    result = client.get("/stations")
    json_data = result.json()
    assert len(json_data) == len(mock_stations)
    stations = [Station.model_validate(item) for item in json_data]
    assert stations == mock_stations


def test_closest_point_on_thames(client, mock_thames_path):
    assert client.get("/closest_point_on_thames", params={"lat": 50.0, "lng": -5.0}).json() == [50.0, -5.0]
    assert client.get("/closest_point_on_thames", params={"lat": 50.0, "lng": 0.0}).json() == [50.0, 0.0]
    assert client.get("/closest_point_on_thames", params={"lat": 50.0, "lng": 5.0}).json() == [50.0, 5.0]

    assert client.get("/closest_point_on_thames", params={"lat": 40.0, "lng": -15.0}).json() == [50.0, -5.0]
    assert client.get("/closest_point_on_thames", params={"lat": 40.0, "lng": 0.0}).json() == [50.0, 0.0]


def test_next_tide_events_at_station(client, mock_stations, mock_tide_events):
    westminster, greenwich, erith = mock_stations
    data = client.get(
        "/next_tide_events_at_station", params={"station_id": westminster.id}
    ).json()
    tides = [TideEvent.model_validate(item) for item in data]
    assert len(tides) == 2
    assert tides[0] == mock_tide_events[1]
    assert tides[1] == mock_tide_events[2]


def test_next_tide_events_from_position(client, mock_now, mock_tide_events):
    data = client.get(
        "/next_tide_events_from_position", params={"lat": 50.0, "lng": -2.5}
    ).json()
    tides = [TideData.model_validate(item) for item in data]
    assert len(tides) == 2
    assert tides[0] == TideData(
        tide_type=TideType.LOW,
        time=mock_now() + timedelta(hours=10, minutes=30),
        height=0.5,
    )
    assert tides[1] == TideData(
        tide_type=TideType.HIGH,
        time=mock_now() + timedelta(hours=22, minutes=30),
        height=7.5,
    )

    mock_now.return_value = datetime(2000, 1, 1, 10, 30)

    data = client.get(
        "/next_tide_events_from_position", params={"lat": 50.0, "lng": -2.5}
    ).json()
    tides = [TideData.model_validate(item) for item in data]
    assert len(tides) == 2
    assert tides[0] == TideData(
        tide_type=TideType.LOW,
        time=mock_now(),
        height=0.5,
    )
    assert tides[1] == TideData(
        tide_type=TideType.HIGH,
        time=mock_now() + timedelta(hours=12),
        height=7.5,
    )
