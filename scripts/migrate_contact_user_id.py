"""
One-time schema migration: adds contact_messages.user_id (see
models/contact.py). This project has no Alembic/Flask-Migrate, so
db.create_all() only creates missing TABLES, never missing COLUMNS
on existing ones.

Safe to re-run: uses IF NOT EXISTS, so running it twice is a no-op
the second time.

Usage:
    python scripts/migrate_contact_user_id.py
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
        "ALTER TABLE contact_messages ADD COLUMN IF NOT EXISTS user_id INTEGER REFERENCES users(user_id)"
    ))
    db.session.commit()
    print("Migration complete: contact_messages.user_id is ready.")
