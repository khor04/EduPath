"""
One-time schema migration: adds indexes on three foreign-key columns that
were never indexed --

    course.semester_id
    semester.transcript_id
    transcript.user_id

-- so joining Course -> Semester -> Transcript filtered by user_id (used by
services/classification_jobs.py's needs_classification(), and elsewhere)
doesn't fall back to a sequential scan. This project has no Alembic/
Flask-Migrate, so db.create_all() only creates missing TABLES, never missing
indexes on columns of existing ones (the models now declare index=True on
these columns, which only takes effect for a table created from scratch).

Safe to re-run: uses IF NOT EXISTS, so running it twice is a no-op the
second time.

Usage:
    python scripts/migrate_add_fk_indexes.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text

from extensions import db
from app import create_app

app = create_app()

with app.app_context():
    db.session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_course_semester_id ON course (semester_id)"
    ))
    db.session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_semester_transcript_id ON semester (transcript_id)"
    ))
    db.session.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_transcript_user_id ON transcript (user_id)"
    ))
    db.session.commit()
    print("Migration complete: course.semester_id, semester.transcript_id and "
          "transcript.user_id are now indexed.")
