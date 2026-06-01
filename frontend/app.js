var map = L.map('map').setView([51.505, -0.09], 13);
const attribution = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: attribution
}).addTo(map);


map.locate({setView: true, maxZoom: 16});

const tides_url = "http://localhost:8081";
var acccircle = L.circle([0, 0], 0).addTo(map);

async function onLocationFound(e) {
    acccircle.setRadius(e.accuracy).setLatLng(e.latlng);

    const params = new URLSearchParams({
        lat: e.latlng.lat,
        lon: e.latlng.lng
    });
    const res = await fetch(`${tides_url}/get_tide_interp?${params}`);
    const data = await res.json();
    console.log(data);
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