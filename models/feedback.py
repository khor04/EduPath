from extensions import db
from datetime import datetime

class Feedback(db.Model):
    __tablename__ = 'feedback'

    feedback_id = db.Column(db.Integer, primary_key=True)
    career_id   = db.Column(db.Integer, db.ForeignKey('career_recommendation.career_id'), nullable=False)
    rating      = db.Column(db.Integer)   # 1 to 5 (emoji scale)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)