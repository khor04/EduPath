"""
One-time schema migration for the admin feature: adds the two columns
the new models declare that don't exist on the live tables yet
(this project has no Alembic/Flask-Migrate, so db.create_all() only
creates missing TABLES, never missing COLUMNS on existing ones).

Safe to re-run: uses IF NOT EXISTS, so running it twice is a no-op
the second time.

Usage:
    python scripts/migrate_admin_columns.py
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
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin BOOLEAN NOT NULL DEFAULT false"
    ))
    db.session.execute(text(
        "ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT now()"
    ))
    db.session.commit()
    print("Migration complete: users.is_admin and contact_messages.created_at are ready.")
