var map = L.map('map').setView([51.505, -0.09], 13);
const attribution = '© <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: attribution
}).addTo(map);