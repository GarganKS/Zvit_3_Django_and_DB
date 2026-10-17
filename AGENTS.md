# AGENTS.md

Django 6.1.2 + SQLite report project ("BusFlow") on Python 3.14. No README, no CI, no lint/typecheck config, no dependency manifest — `.venv` is the only source of truth for installed packages (Django + asgiref + sqlparse only; don't assume anything else is importable).

## Commands

Run from the repo root with the project venv (it has no `pip` module; use `python -m ensurepip` if a package must be installed):

```bash
.venv/bin/python manage.py runserver
.venv/bin/python manage.py check          # verify model changes with THIS, not just test
.venv/bin/python manage.py makemigrations
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test           # single test: ... test app_BusFlow.tests.SomeTest.test_method
```

There is no lint/format/typecheck step. `app_BusFlow/tests.py` is currently empty — no test suite exists yet.

## Layout

- `project_BusFlow/` — project config. Root `urls.py` mounts `app_BusFlow.urls` at `""` plus `admin/`.
- `app_BusFlow/` — the single app: models (`Stop`, `Route`, through-model `StopOnRoute`, `Vehicle`, `Trip`), views, admin, app templates in `app_BusFlow/templates/app_BusFlow/`.
- `templates/base.html` — project-level base template (from `TEMPLATES DIRS`); page templates extend it.
- `db.sqlite3` — live dev DB, gitignored but present locally; created from migrations `0001`–`0007` and currently empty (demo data was dropped). Older copies may sit next to it as `db.sqlite3.bak-*` (also gitignored).

## Gotchas

- **`manage.py test` can print "System check identified no issues" and exit 0 while `check`, `runserver`, and `migrate` all abort with a `SystemCheckError`.** With zero tests the runner passes an empty database-alias set to the check framework, and `DecimalField`'s `max_digits`/`decimal_places` validation (fields.E135) only fires per database alias. Always run `manage.py check` after model changes.
- `RoutesListView` relies on default `ListView` template resolution, so it needs `app_BusFlow/templates/app_BusFlow/route_list.html` (named after the _model_, not the view).

## Style

Use `-` (hyphen) instead of `—` (em dash) in template text and page titles.
