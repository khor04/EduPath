from datetime import datetime

from extensions import db


class TrackedCourse(db.Model):
    """
    A course the student is taking THIS semester and wants to follow
    through the Grade Tracker. Separate from the transcript-backed
    Course model on purpose: a transcript only ever holds finished
    semesters with final grades, while this holds work in progress.
    """

    __tablename__ = "tracked_course"

    tracked_course_id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.user_id"), nullable=False, index=True
    )

    course_code = db.Column(db.String(20), nullable=False)
    course_name = db.Column(db.String(200))
    credit_hour = db.Column(db.Float, nullable=False)
    target_grade = db.Column(db.String(5), nullable=False, default="A-")

    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    assessments = db.relationship(
        "Assessment",
        backref="tracked_course",
        lazy=True,
        cascade="all, delete-orphan",
        order_by="Assessment.assessment_id",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "user_id", "course_code", name="unique_tracked_course_per_user"
        ),
    )


class Assessment(db.Model):
    """
    One graded component of a tracked course (quiz, midterm, final...).

    `result` is stored as the text the student typed -- "8/10", "68%",
    "75" or a letter grade such as "A-" -- and parsed by
    services/grade_tracker_services.parse_result() whenever it is used.
    Keeping the raw text means the Edit form shows exactly what they
    entered. NULL means "not received yet".
    """

    __tablename__ = "assessment"

    assessment_id = db.Column(db.Integer, primary_key=True)
    tracked_course_id = db.Column(
        db.Integer,
        db.ForeignKey("tracked_course.tracked_course_id"),
        nullable=False,
        index=True,
    )

    name = db.Column(db.String(100), nullable=False)
    weight = db.Column(db.Float, nullable=False)  # percent of the final mark
    result = db.Column(db.String(20))
