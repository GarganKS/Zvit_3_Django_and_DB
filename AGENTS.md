# AGENTS.md

Django 6.1.2 report project ("BusFlow") on Python 3.14 with MySQL 8 (Docker). Passenger bus line management: routes, stops, trips, vehicles, tickets, client orders. All UI text, model choices and error messages are in Ukrainian. No README, no CI, no lint/typecheck config, no dependency manifest — `.venv` is the only source of truth for installed packages (Django + asgiref + sqlparse + PyMySQL + cryptography + python-dotenv; don't assume anything else is importable).

## Layout

- `project_BusFlow/` - project config. Root `urls.py` mounts `app_BusFlow.urls` at `""` plus `admin/`.
- `app_BusFlow/` - the single app:
  - `models.py` - mirrors the ERD (MySQL Workbench): `db_table` and PK column names (`trip_id`, ...) match the diagram; in code the PK is still `id`/`pk`. Models: `Stop`, `Route`, `StopOnRoute`, `RoutePath` (cache of the real road geometry of a route), `Vehicle`, `Trip`, `Ticket`, `Client` (login account via `user` OneToOne, `related_name="client"`), `Order`, proxy `Manager`.
  - `services.py` - automations: `sync_vehicle_status`, ticket generation, `refresh_trip_statuses` (time-based trip progress).
  - `routing.py` - real route geometry: asks the public OSRM demo server for the road path between the stops of a route and caches it in `RoutePath` (keyed by a hash of the stop coordinates, so a changed stop order invalidates the cache). Falls back to a straight line when the service is unavailable.
  - `signals.py` - hooks Trip/Order save/delete into `services.py` (this is what frees a vehicle when a trip is deleted).
  - `views.py`, `urls.py` - list/detail/create/edit/delete views, order actions, `RoleLoginView`.
  - `management/commands/` - `update_statuses` (run periodically), `seed_demo`.
  - `admin.py` - `Manager` proxy section (group assigned automatically), `User` admin with client inline.
- `templates/base.html`, `templates/_status.html`, `static/css/style.css` (spacing scale `--space-*`, `.cluster`, `.stack`, `.tile` dashboard cards), `static/js/route_form.js`, `static/js/trip_list.js` (клік по рядку списку рейсів відкриває деталі рейсу; `tr[data-trip-url]`).
- Maps: Leaflet 1.9.4 is vendored in `static/vendor/leaflet/` (no CDN, no build step). Tiles come from OSM DE (`tile.openstreetmap.de`, OSM data, no API key and no request blocking), so the browser needs internet. The tile URL and the attribution live in the `TILES`/`ATTRIBUTION` constants of the three JS files - switch provider there (`tile.openstreetmap.org` blocks apps that do not identify themselves; Carto basemaps need an API key now).
  - `static/js/map.js` - map for the detail pages (route, trip, stop): draws the road path and numbered stop markers. Data is passed as JSON by `app_BusFlow/templates/app_BusFlow/_map.html` (`map_data` -> `json_script`).
  - `static/js/stop_map.js` - map picker on the stop create/edit form: a click or a marker drag writes the coordinates into `id_latitude` / `id_longitude`.
  - `static/js/route_map.js` - live preview on the route form: draws the selected stops and asks OSRM from the browser for the road path.
- Status badge colors: `status_slug` filter in `templatetags/busflow_extras.py` + `.badge-<key>` in `style.css`. Adding a status means adding it to both.

## Business rules

- Vehicle status is derived by `sync_vehicle_status`: Repair/Decommissioned are manual and never overwritten; active order (Awaiting/Planned) -> Rented; trip In progress -> On route; otherwise Waiting.
- Order lifecycle: Нова -> (manager plans: vehicle+price) -> Очікує підтвердження -> (client confirms) -> Заплановано -> Завершено. Client may decline an awaiting order; manager may cancel awaiting/planned. Transitions live in `Order` methods (`plan`, `confirm`, `decline`, `reject`, `cancel`, `complete`).
- Trip creation generates `vehicle.capacity` free `Ticket`s; cancelling a trip cancels free tickets.
- Tickets are sold by managers only (no client purchase): `services.sell_ticket` takes one free ticket of a scheduled trip and stores `passenger_name`/`passenger_phone` (extension of the ERD); `return_ticket` frees it and clears the data. A trip with sold tickets cannot be deleted.
- Vehicle/Route/Stop deletion is `PROTECT`ed; delete views show a message instead of failing.
- Superusers are redirected from `/` and after login to `/admin/`.
- Route `name` is optional in the form: blank means "first - last stop" (max 45 chars).
- The map on the route/trip/stop detail pages shows the *real* road path (OSRM), not straight lines between the stops. The geometry is cached in `RoutePath`; when the service is down the page shows a straight line and says so.

## Database

MySQL 8 only (SQLite support was removed after the data migration).

```bash
docker compose up -d          # підняти БД (127.0.0.1:3307)
python manage.py migrate
python manage.py runserver
```

- `docker-compose.yml` runs MySQL 8 on `127.0.0.1:3307` (port 3306 on the host is taken by a system MariaDB), database `busflow`, user `busflow`, `utf8mb4` / `utf8mb4_0900_ai_ci`. Data lives in the named volume `busflow_mysql_data` (`docker compose down` keeps it, `down -v` deletes it).
- **No passwords in the repository.** `docker-compose.yml` reads `DB_PASSWORD` and `MYSQL_ROOT_PASSWORD` from `.env` (compose interpolates `.env` automatically) and refuses to start without them: `${DB_PASSWORD:?set DB_PASSWORD in .env}`. The same `.env` feeds Django through `python-dotenv`.
- The `busflow` user has `ALL` on `busflow.*` and on `test_busflow.*` (the test runner needs to create/drop it) and **no** global `CREATE`/`DROP`. The root account is only for administration (dumps, manual SQL) and is not used by the app.
- `DEBUG` is off by default and is enabled only via `DJANGO_DEBUG=1` in `.env`; `ALLOWED_HOSTS` defaults to `127.0.0.1,localhost`.
- Dependencies are pinned in `requirements.txt` (Django, PyMySQL, cryptography, python-dotenv); `.venv` remains the source of truth for what is actually installed.
- Connection settings come from the environment: `DB_NAME`, `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_PORT`, plus optional `DJANGO_DEBUG`, `ALLOWED_HOSTS`. `.env` is read by `python-dotenv` (`load_dotenv(BASE_DIR / ".env")` in `project_BusFlow/settings.py`); real environment variables win over the file (`override=False` by default). `.env` is in `.gitignore`; `.env.example` lists the expected keys.
- `SECRET_KEY` is **not** stored in the code: it is read from `DJANGO_SECRET_KEY` (`.env` or the environment) and the project refuses to start with `ImproperlyConfigured` if the variable is missing. Changing the key invalidates existing sessions and signed links (password hashes are unaffected).
- MySQL access goes through PyMySQL (`pymysql.install_as_MySQLdb()` in `project_BusFlow/__init__.py`). PyMySQL 1.2.3 already reports `version_info = (2, 2, 8)`, so Django's mysqlclient version check passes. `cryptography` is required for `caching_sha2_password`.
- The test runner creates the database `test_busflow`, so the `busflow` user needs `CREATE, DROP` (granted on `*.*`).
- The project directory lives on an NTFS (fuseblk) mount, so Unix file permissions are not supported there (`chmod 600 .env` has no effect). On a Linux filesystem set the permissions manually.
- The old SQLite database files (`db.sqlite3`, `db.sqlite3.bak-up`) were deleted after the migration; the data now lives only in MySQL. Keep regular `mysqldump` backups.

## Commands

```bash
python manage.py check          # always run after model changes
python manage.py makemigrations && python manage.py migrate
python manage.py test
python manage.py update_statuses  # trip progress by time (cron)
```

Time zone is `Europe/Kyiv`; on Windows install `tzdata` (`pip install tzdata`).

## Gotchas

- **`manage.py test` can print "System check identified no issues" and exit 0 while `check`, `runserver`, and `migrate` all abort with a `SystemCheckError`.** With zero tests the runner passes an empty database-alias set to the check framework, and `DecimalField`'s `max_digits`/`decimal_places` validation (fields.E135) only fires per database alias. Always run `manage.py check` after model changes.
- The three `ListView`s rely on default `ListView` template resolution, so each needs a template named after the _model_, not the view: `route_list.html`, `trip_list.html`, `vehicle_list.html`.
- `/orders/` is the client order list (the `Order` model exists); the order lifecycle actions live in `/orders/<pk>/plan|reject|complete|confirm|decline|cancel/`.
- Trip progress by time is `services.refresh_trip_statuses` - there is no `update_statuses` management command; call it from cron/shell or the signals.
- Tests must not depend on the internet: `routing.routing_enabled()` is False while `manage.py test` runs, so the map falls back to a straight line. Patch `app_BusFlow.routing.fetch_osrm` to test the real geometry.
- Map settings: `MAP_ROUTING_ENABLED` (turn the OSRM requests off), `OSRM_URL`, `OSRM_TIMEOUT` in `project_BusFlow/settings.py`.

## Style

Use `-` (hyphen) instead of `—` (em dash) in template text and page titles.

## Дизайн-система
- Стилі: `static/css/style.css` (CSS-змінні, світла/темна тема через `data-theme` на `<html>`). Кольори не хардкодити, брати з `:root`.
- Шрифт Onest (Google Fonts) та іконки Lucide підключаються з CDN у `templates/base.html`; іконки: `<i data-lucide="назва"></i>`. Для динамічно доданого HTML викликати `window.busflowIcons()`.
- `static/js/app.js`: тема, мобільне меню, сортування (`th[data-sort="text|num"]`, значення для сортування в `data-sort-value`) і швидкий пошук (`input[data-table-filter="id-таблиці"]`) для `table.data-table`.
- Таблиці списків мають клас `stack-table` і `data-label` у кожній комірці: на телефоні вони стають картками.
- Статуси: `{% include "_status.html" with status=... %}`, кольори в `.badge-*`.
