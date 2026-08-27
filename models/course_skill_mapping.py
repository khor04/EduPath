from extensions import db
from datetime import datetime

class CourseSkillMapping(db.Model):
    __tablename__ = 'course_skill_mapping'

    id            = db.Column(db.Integer, primary_key=True)
    course_code   = db.Column(db.String(20), nullable=False)
    course_title  = db.Column(db.String(200), nullable=False)

    concept_type  = db.Column(db.String(10), nullable=False)   # 'skill' or 'knowledge'
    concept_name  = db.Column(db.String(100), nullable=False)
    confidence    = db.Column(db.Float, nullable=False)   # LLM-assigned relevance score, not a calibrated probability

    model_name    = db.Column(db.String(50), nullable=False)
    prompt_version = db.Column(db.String(20), nullable=False)

    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.Index('ix_course_skill_mapping_course_code', 'course_code'),
        db.UniqueConstraint(
            'course_code', 'concept_type', 'concept_name',
            name='unique_course_concept'
        ),
    )

