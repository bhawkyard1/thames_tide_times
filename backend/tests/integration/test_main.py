from thames_tide_times.models import Station, TideEvent


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