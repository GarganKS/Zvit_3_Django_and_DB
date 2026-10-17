# AGENTS.md

Django 6.1.2 + SQLite report project ("BusFlow") on Python 3.14. Read-only (temporary) passenger bus line tracking: routes, stops, trips, vehicles. All UI text, model choices and error messages are in Ukrainian. No README, no CI, no lint/typecheck config, no dependency manifest — `.venv` is the only source of truth for installed packages (Django + asgiref + sqlparse only; don't assume anything else is importable).

## Commands

Run from the repo root with the project venv (it has no `pip` module; use `python -m ensurepip` if a package must be installed):

```bash
.venv/bin/python manage.py runserver
.venv/bin/python manage.py check          # verify model changes with THIS, not just test
.venv/bin/python manage.py makemigrations
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test           # single test: ... test app_BusFlow.tests.SomeTest.test_method
```

There is no lint/format/typecheck step. `app_BusFlow/tests.py` is still empty — no test suite exists yet.

## Layout

- `project_BusFlow/` — project config. Root `urls.py` mounts `app_BusFlow.urls` at `""` plus `admin/`. `settings.py` is stock plus a `MAILERS` dict (console email backend) at the bottom.
- `app_BusFlow/` — the single app:
  - `models.py` — `Stop`, `Route`, through-model `StopOnRoute`, `Vehicle`, `Trip`.
  - `views.py` — `HomeView`/`OrdersView` (`TemplateView`), `RoutesListView`/`TripsListView`/`VehiclesListView` (`ListView`).
  - `urls.py` — named routes `home`, `routes`, `trips`, `vehicles`, `orders` at `""`, `/routes/`, `/trips/`, `/vehicles/`, `/orders/`.
  - `admin.py` — all five models registered plainly (`admin.site.register`), no custom admin classes.
  - `templates/app_BusFlow/` — `home.html`, `route_list.html`, `trip_list.html`, `vehicle_list.html`, `order_list.html`.
- `templates/base.html` — project-level base template (from `TEMPLATES DIRS`): nav bar with active-tab highlighting via `request.resolver_match.url_name`, all CSS inlined in a `<style>` block (no static files, no `static/` dir).
- `db.sqlite3` — live dev DB, gitignored but present locally; migrated through `0001`–`0007` and **populated with hand-added demo data — don't assume it's empty**. Older copies may sit next to it as `db.sqlite3.bak-*` (also gitignored).

## Data model notes

- `Route` has **no `name` field** (removed in migration 0004). Its name is the `display_name` property: first stop by `stop_sequence` - last stop, falling back to "Новий маршрут" (no pk) or `Маршрут #<pk>` (no stops). It reads `stoponroute_set`, so use `prefetch_related` on routes shown in lists.
- `StopOnRoute` (route <-> stop) carries `stop_sequence` plus nullable `arrival_time`/`departure_time`.
- `Trip.departure_time`/`arrival_time` are nullable `DateTimeField`s; `Trip.vehicle` is a required FK (`related_name="trip"`).
- Status fields (`Vehicle.status`, `Trip.status`) are Ukrainian `TextChoices` values guarded twice: model-level `clean()` and a DB `CheckConstraint` — extend both when adding a status.
- Time-order constraints (`trip_arrival_after_departure`, `stoponroute_arrival_lte_departure`) skip rows where either time is NULL.

## Gotchas

- **`manage.py test` can print "System check identified no issues" and exit 0 while `check`, `runserver`, and `migrate` all abort with a `SystemCheckError`.** With zero tests the runner passes an empty database-alias set to the check framework, and `DecimalField`'s `max_digits`/`decimal_places` validation (fields.E135) only fires per database alias. Always run `manage.py check` after model changes.
- The three `ListView`s rely on default `ListView` template resolution, so each needs a template named after the _model_, not the view: `route_list.html`, `trip_list.html`, `vehicle_list.html`.
- `/orders/` is a placeholder page — no `Order` model exists yet.

## Style

Use `-` (hyphen) instead of `—` (em dash) in template text and page titles.
