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

    email_pending = db.Column(db.String(120), nullable=True) 

    def get_id(self):
        return str(self.user_id)