# AGENTS.md

Django 6.1.2 + SQLite report project ("BusFlow") on Python 3.14. Passenger bus line management: routes, stops, trips, vehicles, tickets, client orders. All UI text, model choices and error messages are in Ukrainian. No README, no CI, no lint/typecheck config, no dependency manifest — `.venv` is the only source of truth for installed packages (Django + asgiref + sqlparse only; don't assume anything else is importable).

## Layout

- `project_BusFlow/` - project config. Root `urls.py` mounts `app_BusFlow.urls` at `""` plus `admin/`.
- `app_BusFlow/` - the single app:
  - `models.py` - mirrors the ERD (MySQL Workbench): `db_table` and PK column names (`trip_id`, ...) match the diagram; in code the PK is still `id`/`pk`. Models: `Stop`, `Route`, `StopOnRoute`, `Vehicle`, `Trip`, `Ticket`, `Client` (login account via `user` OneToOne, `related_name="client"`), `Order`, proxy `Manager`.
  - `services.py` - automations: `sync_vehicle_status`, ticket generation, `refresh_trip_statuses` (time-based trip progress).
  - `signals.py` - hooks Trip/Order save/delete into `services.py` (this is what frees a vehicle when a trip is deleted).
  - `views.py`, `urls.py` - list/detail/create/edit/delete views, order actions, `RoleLoginView`.
  - `management/commands/` - `update_statuses` (run periodically), `seed_demo`.
  - `admin.py` - `Manager` proxy section (group assigned automatically), `User` admin with client inline.
- `templates/base.html`, `templates/_status.html`, `static/css/style.css` (spacing scale `--space-*`, `.cluster`, `.stack`, `.tile` dashboard cards), `static/js/route_form.js`.
- Status badge colors: `status_slug` filter in `templatetags/busflow_extras.py` + `.badge-<key>` in `style.css`. Adding a status means adding it to both.

## Business rules

- Vehicle status is derived by `sync_vehicle_status`: Repair/Decommissioned are manual and never overwritten; active order (Awaiting/Planned) -> Rented; trip In progress -> On route; otherwise Waiting.
- Order lifecycle: Нова -> (manager plans: vehicle+price) -> Очікує підтвердження -> (client confirms) -> Заплановано -> Завершено. Client may decline an awaiting order; manager may cancel awaiting/planned. Transitions live in `Order` methods (`plan`, `confirm`, `decline`, `reject`, `cancel`, `complete`).
- Trip creation generates `vehicle.capacity` free `Ticket`s; cancelling a trip cancels free tickets.
- Vehicle/Route/Stop deletion is `PROTECT`ed; delete views show a message instead of failing.
- Superusers are redirected from `/` and after login to `/admin/`.
- Route `name` is optional in the form: blank means "first - last stop" (max 45 chars).

## Commands

```bash
python manage.py check          # always run after model changes
python manage.py makemigrations && python manage.py migrate
python manage.py test
python manage.py seed_demo      # demo data on an empty DB
python manage.py update_statuses  # trip progress by time (cron)
```

Time zone is `Europe/Kyiv`; on Windows install `tzdata` (`pip install tzdata`).

## Gotchas

- **`manage.py test` can print "System check identified no issues" and exit 0 while `check`, `runserver`, and `migrate` all abort with a `SystemCheckError`.** With zero tests the runner passes an empty database-alias set to the check framework, and `DecimalField`'s `max_digits`/`decimal_places` validation (fields.E135) only fires per database alias. Always run `manage.py check` after model changes.
- The three `ListView`s rely on default `ListView` template resolution, so each needs a template named after the _model_, not the view: `route_list.html`, `trip_list.html`, `vehicle_list.html`.
- `/orders/` is a placeholder page — no `Order` model exists yet.

## Style

Use `-` (hyphen) instead of `—` (em dash) in template text and page titles.
