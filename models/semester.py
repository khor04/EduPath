from extensions import db
class Semester(db.Model):
    __tablename__ = 'semester'

    semester_id          = db.Column(db.Integer, primary_key=True)
    transcript_id        = db.Column(db.Integer, db.ForeignKey('transcript.transcript_id'), nullable=False)

    semester_no          = db.Column(db.Integer,nullable=False)
    academic_session     = db.Column(db.String(20),nullable=False)

    semester_gpa         = db.Column(db.Float)
    semester_credits     = db.Column(db.Float)

    is_revised           = db.Column(db.Boolean, default=False)
    
    # Relationships
    courses = db.relationship('Course', backref='semester', lazy=True)