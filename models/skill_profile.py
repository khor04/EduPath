from extensions import db
from datetime import datetime

class SkillProfile(db.Model):
    __tablename__ = 'skill_profile'

    skill_id        = db.Column(db.Integer, primary_key=True)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    transcript_id   = db.Column(db.Integer, db.ForeignKey('transcript.transcript_id'), nullable=False)
    skill_name      = db.Column(db.String(100))
    raw_score       = db.Column(db.Float)
    percentage      = db.Column(db.Float)
    skill_category  = db.Column(db.String(20))  # 'strength' or 'growth'
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)