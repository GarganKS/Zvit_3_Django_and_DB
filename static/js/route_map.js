/* Попередній перегляд маршруту на сторінці редагування: показує вибрані
   зупинки й реальну трасу по вулицях (геометрію питає OSRM напряму з браузера). */
(function () {
    var element = document.getElementById("route-map");
    var list = document.getElementById("stop-list");
    var coordsNode = document.getElementById("route-stops-coords");
    if (!element || !list || !coordsNode || typeof L === "undefined") return;

    var stopsById = {};
    JSON.parse(coordsNode.textContent).forEach(function (stop) {
        stopsById[stop.id] = stop;
    });

    var TILES = "https://tile.openstreetmap.de/{z}/{x}/{y}.png";
    var ATTRIBUTION =
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> | Tiles by <a href="https://www.openstreetmap.de/">OSM DE</a>';
    var OSRM = "https://router.project-osrm.org/route/v1/driving/";

    var map = L.map(element, { scrollWheelZoom: true });
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);

    var lineLayer = null;
    var markerLayer = L.layerGroup().addTo(map);
    var request = null;
    var timer = null;

    function selectedStops() {
        var result = [];
        Array.prototype.forEach.call(
            list.querySelectorAll(".stop-row"),
            function (row) {
                if (row.classList.contains("is-deleted")) return;
                var select = row.querySelector('[name$="-stop"]');
                if (!select || !select.value) return;
                var stop = stopsById[select.value];
                if (stop) result.push(stop);
            }
        );
        return result;
    }

    function drawStraight(stops) {
        if (lineLayer) {
            map.removeLayer(lineLayer);
            lineLayer = null;
        }
        if (stops.length < 2) return;
        lineLayer = L.polyline(
            stops.map(function (stop) {
                return [stop.lat, stop.lon];
            }),
            { color: "#8aa4c8", weight: 3, dashArray: "6 6" }
        ).addTo(map);
    }

    function drawMarkers(stops) {
        markerLayer.clearLayers();
        stops.forEach(function (stop, index) {
            var icon = L.divIcon({
                className: "map-marker",
                html: '<span class="map-marker-num">' + (index + 1) + "</span>",
                iconSize: [26, 26],
                iconAnchor: [13, 13],
            });
            L.marker([stop.lat, stop.lon], { icon: icon, title: stop.name })
                .bindPopup("<strong>" + stop.name + "</strong>")
                .addTo(markerLayer);
        });
    }

    function drawRoad(stops) {
        if (request) request.abort();
        if (stops.length < 2) {
            drawStraight(stops);
            return;
        }
        var coords = stops
            .map(function (stop) {
                return stop.lon.toFixed(6) + "," + stop.lat.toFixed(6);
            })
            .join(";");
        request = new AbortController();
        fetch(OSRM + coords + "?overview=full&geometries=geojson", {
            signal: request.signal,
        })
            .then(function (response) {
                return response.json();
            })
            .then(function (data) {
                if (!data || data.code !== "Ok" || !data.routes.length) {
                    drawStraight(stops);
                    return;
                }
                var geometry = data.routes[0].geometry.coordinates;
                var points = geometry.map(function (point) {
                    return [point[1], point[0]];
                });
                if (lineLayer) map.removeLayer(lineLayer);
                L.polyline(points, { color: "#ffffff", weight: 9, opacity: 0.85 }).addTo(map);
                lineLayer = L.polyline(points, {
                    color: "#1f4e8c",
                    weight: 4,
                    opacity: 0.95,
                }).addTo(map);
            })
            .catch(function (error) {
                if (error.name !== "AbortError") drawStraight(stops);
            });
    }

    function refresh() {
        var stops = selectedStops();
        drawMarkers(stops);
        drawStraight(stops);
        drawRoad(stops);
        if (stops.length) {
            var bounds = stops.map(function (stop) {
                return [stop.lat, stop.lon];
            });
            map.fitBounds(bounds, { padding: [30, 30] });
        }
    }

    function scheduleRefresh() {
        if (timer) clearTimeout(timer);
        timer = setTimeout(refresh, 400);
    }

    list.addEventListener("change", scheduleRefresh);
    list.addEventListener("click", scheduleRefresh);

    refresh();
})();
