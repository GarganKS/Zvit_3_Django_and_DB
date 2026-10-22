/* Карта BusFlow: показує зупинки та реальні траси маршрутів (лінії по вулицях).
   Дані приходять у <script type="application/json"> (див. _map.html). */
(function () {
    var element = document.getElementById("busflow-map");
    if (!element || typeof L === "undefined") return;

    var dataNode = document.getElementById(element.getAttribute("data-map-data"));
    if (!dataNode) return;

    var data;
    try {
        data = JSON.parse(dataNode.textContent);
    } catch (error) {
        return;
    }

    var stops = data.stops || [];
    var paths = data.paths || [];
    if (!stops.length && !paths.length) return;

    var TILES = "https://tile.openstreetmap.de/{z}/{x}/{y}.png";
    var ATTRIBUTION =
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> | Tiles by <a href="https://www.openstreetmap.de/">OSM DE</a>';

    function escapeHtml(text) {
        return String(text === undefined || text === null ? "" : text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;");
    }

    var map = L.map(element, { scrollWheelZoom: true });
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);

    var bounds = [];

    paths.forEach(function (path) {
        var points = path.points || [];
        if (points.length < 2) return;
        // Біла «підкладка» під лінією - так маршрут краще видно на карті.
        L.polyline(points, { color: "#ffffff", weight: 9, opacity: 0.85 }).addTo(map);
        L.polyline(points, { color: "#2f6bff", weight: 5, opacity: 0.95 }).addTo(map);
        points.forEach(function (point) {
            bounds.push(point);
        });
    });

    stops.forEach(function (stop, index) {
        var icon = L.divIcon({
            className:
                "map-marker" +
                (stop.main ? " is-main" : "") +
                (stops.length > 1 && index === 0 ? " is-start" : "") +
                (stops.length > 1 && index === stops.length - 1 ? " is-end" : ""),
            html: '<span class="map-marker-num">' + escapeHtml(stop.seq || "") + "</span>",
            iconSize: [28, 28],
            iconAnchor: [14, 14],
        });
        var marker = L.marker([stop.lat, stop.lon], { icon: icon, title: stop.name });
        marker.addTo(map);
        var html = "<strong>" + escapeHtml(stop.name) + "</strong>";
        if (stop.address) html += "<br>" + escapeHtml(stop.address);
        if (stop.url) html += '<br><a href="' + stop.url + '">Відкрити зупинку</a>';
        marker.bindPopup(html);
        bounds.push([stop.lat, stop.lon]);
    });

    if (bounds.length) {
        map.fitBounds(bounds, { padding: [30, 30] });
    }
})();
