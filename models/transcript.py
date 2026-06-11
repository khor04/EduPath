from extensions import db
from datetime import datetime

class Transcript(db.Model):
    __tablename__ = 'transcript'

    transcript_id = db.Column(db.Integer, primary_key=True)
    user_id       = db.Column(db.Integer, db.ForeignKey('users.user_id'), nullable=False)
    status        = db.Column(db.String(20), default='pending')  # pending / verified
    uploaded_at   = db.Column(db.DateTime, default=datetime.utcnow)
    uploaded_type = db.Column(db.String(20)) #new/appeal/mixed
    summary = db.Column(db.Text) #human-readable history
    # Relationships
    semesters             = db.relationship('Semester', backref='transcript', lazy=True)
    skill_profiles        = db.relationship('SkillProfile', backref='transcript', lazy=True)
    career_recommendations = db.relationship('CareerRecommendation', backref='transcript', lazy=True)