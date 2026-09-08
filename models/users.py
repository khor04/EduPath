from extensions import db
from flask_login import UserMixin
from datetime import datetime

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    user_id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)

    faculty = db.Column(db.String(200), nullable=False)
    programme = db.Column(db.String(200), nullable=False)
    batch = db.Column(db.String(20), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    profile_picture=db.Column(db.String(500), default=None)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    # Tri-state on purpose: None = hasn't decided yet (shows the
    # consent prompt), True = opted in, False = explicitly declined.
    # Consent gates BOTH directions -- a student's data only enters
    # the peer pool, and they can only view peer comparisons, when
    # this is True. See routes/benchmark.py and services/benchmark_services.py.
    benchmark_consent = db.Column(db.Boolean, nullable=True, default=None)

    email_pending = db.Column(db.String(120), nullable=True)

    verification_code_hash = db.Column(db.String(255), nullable=True)
    verification_expires_at = db.Column(db.DateTime, nullable=True)
    verification_attempts = db.Column(db.Integer, default=0)

    def get_id(self):
        return str(self.user_id)