from extensions import db
class Course(db.Model):
    __tablename__ = 'course'

    course_id    = db.Column(db.Integer, primary_key=True)
    semester_id  = db.Column(db.Integer, db.ForeignKey('semester.semester_id'), nullable=False)

    course_code  = db.Column(db.String(20), nullable=False)
    course_name  = db.Column(db.String(200))

    credit_hour  = db.Column(db.Float)
    grade        = db.Column(db.String(5))
    grade_point  = db.Column(db.Float)

    __table_args__ = (
    db.UniqueConstraint(
        'semester_id',
        'course_code',
        name='unique_course_per_semester'
    ),
)