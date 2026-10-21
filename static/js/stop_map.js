/* Вибір координат зупинки на карті: клік по карті або перетягування маркера
   записує широту й довготу у поля форми. */
(function () {
    var element = document.getElementById("stop-picker");
    if (!element || typeof L === "undefined") return;

    var latInput = document.getElementById("id_latitude");
    var lonInput = document.getElementById("id_longitude");
    if (!latInput || !lonInput) return;

    var TILES = "https://tile.openstreetmap.de/{z}/{x}/{y}.png";
    var ATTRIBUTION =
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a> | Tiles by <a href="https://www.openstreetmap.de/">OSM DE</a>';

    var map = L.map(element, { scrollWheelZoom: true }).setView([49.02, 31.17], 6);
    L.tileLayer(TILES, { maxZoom: 19, attribution: ATTRIBUTION }).addTo(map);

    var marker = null;

    function isValid(lat, lon) {
        return (
            isFinite(lat) &&
            isFinite(lon) &&
            Math.abs(lat) <= 90 &&
            Math.abs(lon) <= 180
        );
    }

    function writeInputs(lat, lon) {
        latInput.value = lat.toFixed(6);
        lonInput.value = lon.toFixed(6);
    }

    function place(lat, lon, focus) {
        if (marker) {
            marker.setLatLng([lat, lon]);
        } else {
            marker = L.marker([lat, lon], { draggable: true }).addTo(map);
            marker.on("dragend", function () {
                var point = marker.getLatLng();
                writeInputs(point.lat, point.lng);
            });
        }
        if (focus) map.setView([lat, lon], Math.max(map.getZoom(), 15));
    }

    function clearMarker() {
        if (marker) {
            map.removeLayer(marker);
            marker = null;
        }
        latInput.value = "";
        lonInput.value = "";
    }

    map.on("click", function (event) {
        place(event.latlng.lat, event.latlng.lng, false);
        writeInputs(event.latlng.lat, event.latlng.lng);
    });

    // Координати, введені вручну, теж рухають маркер.
    function syncFromInputs() {
        var lat = parseFloat(latInput.value);
        var lon = parseFloat(lonInput.value);
        if (!isValid(lat, lon)) return;
        place(lat, lon, false);
    }

    latInput.addEventListener("change", syncFromInputs);
    lonInput.addEventListener("change", syncFromInputs);

    var reset = document.getElementById("stop-picker-reset");
    if (reset) reset.addEventListener("click", clearMarker);

    var lat = parseFloat(latInput.value);
    var lon = parseFloat(lonInput.value);
    if (isValid(lat, lon)) {
        place(lat, lon, true);
        map.setView([lat, lon], 16);
    }
})();
