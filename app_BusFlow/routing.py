"""Побудова реального маршруту по вулицях та дані для карт.

Траса рахується публічним демо-сервером OSRM (OpenStreetMap): він повертає
геометрію доріг між зупинками, а не пряму лінію. Результат кешується в
таблиці route_path, тож зовнішній сервіс не опитується на кожному перегляді.
Якщо сервіс недоступний, показується приблизна (пряма) траса.
"""

import hashlib
import json
import sys
import urllib.error
import urllib.request

from django.conf import settings
from django.urls import reverse

from app_BusFlow.models import Route, RoutePath

OSRM_URL = getattr(
    settings, "OSRM_URL", "https://router.project-osrm.org/route/v1/driving/"
)
TIMEOUT = getattr(settings, "OSRM_TIMEOUT", 15)
USER_AGENT = "BusFlow/1.0 (+https://github.com/GarganKS/Zvit_3_Django_and_DB)"


def routing_enabled():
    """Чи можна звертатися до зовнішнього сервісу маршрутів.

    Під час тестів (`manage.py test`) зовнішні запити не потрібні: тести
    мають бути швидкими й не залежати від інтернету.
    """
    if not getattr(settings, "MAP_ROUTING_ENABLED", True):
        return False
    return "test" not in sys.argv


def stop_points(route):
    """Точки зупинок маршруту в порядку проходження: [(lat, lon), ...]."""
    links = sorted(route.stoponroute_set.all(), key=lambda link: link.stop_sequence)
    return [
        (float(link.stop.latitude), float(link.stop.longitude)) for link in links
    ]


def points_signature(points):
    """Відбиток набору координат - щоб зрозуміти, чи змінився маршрут."""
    raw = ";".join(f"{lat:.6f},{lon:.6f}" for lat, lon in points)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def fetch_osrm(points):
    """Питає OSRM і повертає геометрію траси. None - якщо сервіс не відповів."""
    if len(points) < 2 or not routing_enabled():
        return None
    coords = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    url = f"{OSRM_URL}{coords}?overview=full&geometries=geojson"
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        # Сервіс недоступний або відповів несподіваним форматом.
        return None
    if data.get("code") != "Ok":
        return None
    routes = data.get("routes") or []
    if not routes:
        return None
    route = routes[0]
    geometry = (route.get("geometry") or {}).get("coordinates") or []
    if not geometry:
        return None
    return {
        # OSRM віддає [довгота, широта], Leaflet очікує [широта, довгота].
        "points": [[lat, lon] for lon, lat in geometry],
        "distance_m": float(route.get("distance") or 0),
        "duration_s": float(route.get("duration") or 0),
    }


def get_route_path(route):
    """Траса маршруту: з кешу або щойно обчислена.

    Повертає None, якщо в маршруті менше двох зупинок.
    """
    points = stop_points(route)
    if len(points) < 2:
        return None
    signature = points_signature(points)
    cached = RoutePath.objects.filter(route=route).first()
    if cached and cached.signature == signature:
        try:
            geometry = json.loads(cached.geometry)
        except (TypeError, ValueError):
            geometry = []
        if geometry:
            return {
                "points": geometry,
                "distance_m": cached.distance_m,
                "duration_s": cached.duration_s,
                "source": "osrm",
            }
    result = fetch_osrm(points)
    if result is None:
        # Сервіс недоступний - показуємо пряму лінію, але не кешуємо її.
        return {
            "points": [[lat, lon] for lat, lon in points],
            "distance_m": 0.0,
            "duration_s": 0.0,
            "source": "straight",
        }
    RoutePath.objects.update_or_create(
        route=route,
        defaults={
            "signature": signature,
            "geometry": json.dumps(result["points"]),
            "distance_m": result["distance_m"],
            "duration_s": result["duration_s"],
        },
    )
    return {**result, "source": "osrm"}


def _stop_marker(link, main=False):
    stop = link.stop
    return {
        "name": stop.name,
        "address": stop.address,
        "lat": float(stop.latitude),
        "lon": float(stop.longitude),
        "seq": link.stop_sequence,
        "url": reverse("stop_detail", args=[stop.pk]),
        "main": main,
    }


def _path_data(route, path):
    return {
        "name": route.display_name,
        "url": reverse("route_detail", args=[route.pk]),
        "points": path["points"],
        "distance_km": round(path["distance_m"] / 1000, 1),
        "duration_min": round(path["duration_s"] / 60),
        "source": path["source"],
    }


def route_map_data(route):
    """Дані для карти маршруту: зупинки та реальна траса."""
    links = sorted(route.stoponroute_set.all(), key=lambda link: link.stop_sequence)
    stops = [_stop_marker(link) for link in links]
    paths = []
    path = get_route_path(route)
    if path:
        paths.append(_path_data(route, path))
    return {"stops": stops, "paths": paths}


def stop_map_data(stop):
    """Дані для карти зупинки: сама зупинка й маршрути, що через неї йдуть."""
    routes = []
    links = []
    for route in Route.objects.filter(stoponroute__stop=stop).distinct():
        route_links = sorted(
            route.stoponroute_set.all(), key=lambda link: link.stop_sequence
        )
        links.extend(route_links)
        path = get_route_path(route)
        if path:
            routes.append(_path_data(route, path))
    # Спершу сама зупинка (вона головна), потім - інші зупинки її маршрутів.
    stops = [
        {
            "name": stop.name,
            "address": stop.address,
            "lat": float(stop.latitude),
            "lon": float(stop.longitude),
            "seq": "",
            "url": reverse("stop_detail", args=[stop.pk]),
            "main": True,
        }
    ]
    seen = {stop.pk}
    for link in sorted(links, key=lambda link: (link.route_id, link.stop_sequence)):
        if link.stop_id in seen:
            continue
        seen.add(link.stop_id)
        stops.append(_stop_marker(link))
    return {"stops": stops, "paths": routes}
