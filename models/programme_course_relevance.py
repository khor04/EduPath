from extensions import db
from datetime import datetime

class ProgrammeCourseRelevance(db.Model):
    __tablename__ = 'programme_course_relevance'

    id             = db.Column(db.Integer, primary_key=True)
    course_code    = db.Column(db.String(20), nullable=False)
    programme      = db.Column(db.String(200), nullable=False)

    relevance_tier = db.Column(db.String(20), nullable=False)  # 'Core' / 'Related' / 'General'

    model_name     = db.Column(db.String(50), nullable=False)
    prompt_version = db.Column(db.String(20), nullable=False)

    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('course_code', 'programme', name='unique_course_programme'),
    )
