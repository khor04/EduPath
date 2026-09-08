"""
One-time schema migration: adds users.benchmark_consent (see
models/users.py). This project has no Alembic/Flask-Migrate, so
db.create_all() only creates missing TABLES, never missing COLUMNS
on existing ones.

Deliberately no DEFAULT clause -- the column is nullable and every
existing row should land on NULL ("hasn't decided yet"), which is
exactly what a bare ADD COLUMN without DEFAULT produces. Every
student, new or existing, sees the consent prompt the first time
they visit Peer Benchmarking with a transcript uploaded; nobody is
silently opted in or out.

Safe to re-run: uses IF NOT EXISTS, so running it twice is a no-op
the second time.

Usage:
    python scripts/migrate_benchmark_consent.py
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from extensions import db
from app import create_app

app = create_app()

with app.app_context():
    db.session.execute(text(
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS benchmark_consent BOOLEAN"
    ))
    db.session.commit()
    print("Migration complete: users.benchmark_consent is ready (NULL for all existing rows).")
