from extensions import db
from datetime import datetime

class TargetCGPA(db.Model):
    __tablename__ = 'target_cgpa'

    target_id         = db.Column(db.Integer, primary_key=True)
    user_id           = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    target_cgpa       = db.Column(db.Float)
    required_gpa      = db.Column(db.Float)
    remaining_credits = db.Column(db.Float)
    updated_at        = db.Column(db.DateTime, default=datetime.utcnow)