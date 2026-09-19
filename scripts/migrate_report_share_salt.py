"""
One-time schema migration: adds report_shares.salt (see
models/report_share.py). This project has no Alembic/Flask-Migrate, so
db.create_all() only creates missing TABLES, never missing COLUMNS on
existing ones.

Only needed if the report_shares table already exists in the database
(i.e. the app was started after the first version of the sharing
feature). If the table doesn't exist yet, create_app() below creates it
with the salt column already in place and the ALTER is a no-op.

Any pre-existing row gets an empty salt. That is safe: such a link keeps
working for whoever already has the URL (it's validated from the stored
hash alone), it just can't be re-displayed to the student, so they are
offered "Create Link" instead -- see get_current_link() in
services/share_services.py.

Safe to re-run: uses IF NOT EXISTS, so running it twice is a no-op
the second time.

Usage:
    python scripts/migrate_report_share_salt.py
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
        "ALTER TABLE report_shares ADD COLUMN IF NOT EXISTS salt VARCHAR(64) NOT NULL DEFAULT ''"
    ))
    db.session.commit()
    print("Migration complete: report_shares.salt is ready.")
