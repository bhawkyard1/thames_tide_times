from thames_tide_times.models import Station


def test_stations(client, mock_stations):
    result = client.get("/stations")
    json_data = result.json()
    assert len(json_data) == len(mock_stations)
    stations = [Station.model_validate(item) for item in json_data]
    assert stations == mock_stations
