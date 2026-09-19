from datetime import datetime

from extensions import db


class ReportShare(db.Model):
    """
    A time-limited link a student creates so their advisor can view
    their report without an EduPath account.

    A unique random salt is generated for each share record, and a
    deterministic token is derived from it using an HMAC with the
    application's SECRET_KEY (see services/share_services.py). The
    token is then hashed before it is stored, and the hash is what
    incoming links are validated against.

    The token itself is never stored, so a leaked database alone isn't
    enough to reconstruct a working URL -- that also takes SECRET_KEY,
    which lives in the environment, not the database. The student can
    still be shown their link again, because the server can re-derive
    it from the salt.

    The link points at the student's CURRENT report, not a copy: there
    is nothing stored here beyond who it belongs to and when it expires.
    """

    __tablename__ = "report_shares"

    share_id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )

    salt = db.Column(db.String(64), nullable=False)
    token_hash = db.Column(db.String(64), unique=True, nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
