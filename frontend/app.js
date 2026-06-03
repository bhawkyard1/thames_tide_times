var map = L.map('map').setView([51.505, -0.09], 13);
const attribution = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: attribution
}).addTo(map);


map.locate({setView: true, maxZoom: 16});

const tides_url = "http://localhost:8081";
var acccircle = L.circle([0, 0], 0).addTo(map);
var tide_popup = L.popup();


function formatTideDirection(tide_data) {
    const tide_date = new Date(`${tide_data["time"]}`);
    const tide_type = tide_data["tide_type"];
    const now = Date.now();
    if (tide_date < now && tide_type === "high") {
        return "Tide is going out."
    } else if (tide_date < now && tide_type === "low") {
        return "Tide is coming in."
    } else if (tide_date > now && tide_type === "high") {
        return "Tide is coming in."
    }
    return "Tide is going out."
}

function capitalizeFirstLetter(val) {
    return String(val).charAt(0).toUpperCase() + String(val).slice(1);
}

function formatTidePrediction(tide_data) {
    const tide_date = new Date(`${tide_data["time"]}`);
    const tide_height = Number(tide_data["height"]).toFixed(1);
    return capitalizeFirstLetter(
        `${tide_data["tide_type"]} tide expected at ${tide_date.toLocaleTimeString([], {hour: "2-digit", minute:"2-digit"})} (${tide_height} meters).`
    );
}

async function onLocationFound(e) {
    acccircle.setRadius(e.accuracy).setLatLng(e.latlng);

    const params = new URLSearchParams({
        lat: e.latlng.lat,
        lng: e.latlng.lng
    });

    const res = await fetch(`${tides_url}/next_tide_events_from_position?${params}`);
    const tide_data = await res.json();
    console.log(tide_data);

    const res_thames_point = await fetch(`${tides_url}/closest_point_on_thames?${params}`);
    const data_thames_point = await res_thames_point.json();

    const l = L.latLng(data_thames_point[0], data_thames_point[1]);
    tide_popup.setLatLng(l).setContent(
        `${formatTideDirection(tide_data[0])}<br>${formatTidePrediction(tide_data[0])}<br>${formatTidePrediction(tide_data[1])}`
    ).openOn(map);
}

map.on('locationfound', onLocationFound);

function onLocationError(e) {
    alert(e.message);
}

map.on('locationerror', onLocationError);

async function showStations() {
    const res = await fetch(`${tides_url}/stations`);
    const data = await res.json();
    data.forEach(element => {
        marker = new L.Marker([element["latitude"], element["longitude"]])
            .bindTooltip(element["name"],
                {
                    permanent: true,
                    direction: "right"
                }
            )
            .addTo(map);
    });
}

showStations();

setInterval(() => map.locate({maxZoom: 16}), 10_000);