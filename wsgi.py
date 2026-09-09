"""Gunicorn entry point: `gunicorn wsgi:app`.

Kept separate from app.py rather than adding a module-level `app = create_app()`
there, because several one-off scripts (scripts/create_admin.py,
scripts/migrate_*.py) already do `from app import create_app` and call it
themselves -- a module-level call in app.py would run create_app() a second
time (and its own DB setup/print) on every one of those imports.
"""
from app import create_app

app = create_app()
