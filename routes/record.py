from flask import Blueprint, render_template
from flask_login import login_required, current_user

from models.transcript import Transcript
from models.semester import Semester
from models.course import Course
from services.cgpa_services import calculate_cgpa_credits

record_bp = Blueprint("record", __name__)


@record_bp.route("/academic-record")
@login_required
def academic_record():
    transcript = Transcript.query.filter_by(user_id=current_user.user_id).first()

    if not transcript:
        return render_template("academic_record_locked.html", active_page="record")

    # Semesters span ALL of the user's Transcript rows, not just the
    # first -- a re-upload creates a new Transcript rather than reusing
    # one, same as how cgpa_services._fetch_user_courses() and
    # benchmark.py's semester queries already treat it. Most recent
    # semester first, matching the "latest result" framing of the page;
    # each is rendered as a collapsible card, open by default for the
    # first (latest) one only.
    semesters = (
        Semester.query
        .join(Transcript)
        .filter(Transcript.user_id == current_user.user_id)
        .order_by(Semester.academic_session.desc(), Semester.semester_no.desc())
        .all()
    )

    for sem in semesters:
        sem.courses.sort(key=lambda c: c.course_code)

    cgpa_result = calculate_cgpa_credits(current_user.user_id)

    last_updated = (
        Transcript.query
        .filter_by(user_id=current_user.user_id)
        .order_by(Transcript.uploaded_at.desc())
        .first()
        .uploaded_at
    )

    return render_template(
        "academic_record.html",
        semesters=semesters,
        cgpa=cgpa_result["cgpa"],
        credits=cgpa_result["credits"],
        last_updated=last_updated,
        active_page="record",
    )
