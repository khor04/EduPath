from extensions import db
from datetime import datetime

class CareerRecommendation(db.Model):
    __tablename__ = 'career_recommendation'

    career_id     = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    transcript_id = db.Column(db.Integer, db.ForeignKey('transcript.transcript_id'), nullable=False)
    career_name   = db.Column(db.String(100))
    career_score  = db.Column(db.Float)
    match_level   = db.Column(db.String(20))   # 'strong' or 'moderate'
    rank          = db.Column(db.Integer)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationship
    feedback = db.relationship('Feedback', backref='career', lazy=True)