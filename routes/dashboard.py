from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.transcript import Transcript
from models.semester import Semester
from models.target_cgpa import TargetCGPA
from services.cgpa_services import calculate_cgpa_credits

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard():

    # Get all semester records for current user
    semesters = (
        Semester.query
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == current_user.user_id)
        .all()
    )

    semesters = sorted(
        semesters,
        key=lambda s:(
            s.academic_session,
            s.semester_no
        )
    )

    # GPA trend chart data
    gpa_labels = [f"Sem {s.semester_no} ({s.academic_session})"
                  for s in semesters]
    gpa_values = [
    float(sem.semester_gpa or 0)
    for sem in semesters
    ]

    # Latest CGPA and completed credits
    cgpa_result = calculate_cgpa_credits(current_user.user_id)

    latest_cgpa = cgpa_result["cgpa"]
    completed_credits = cgpa_result["credits"]
    # Latest transcript upload time
    latest_transcript = (
        Transcript.query
        .filter_by(user_id=current_user.user_id)
        .order_by(Transcript.uploaded_at.desc())
        .first()
    )

    last_updated = (
        latest_transcript.uploaded_at.strftime("%d-%m-%Y %H:%M:%S")
        if latest_transcript else "No transcript uploaded"
    )

    # Saved target CGPA plan
    target_plan = TargetCGPA.query.filter_by(
        user_id=current_user.user_id
    ).first()

    target_cgpa = round(target_plan.target_cgpa, 2) if target_plan else None
    required_gpa = round(target_plan.required_gpa, 2) if target_plan else None

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        semesters=semesters,
        latest_cgpa=round(latest_cgpa, 2),
        completed_credits=int(completed_credits),
        target_cgpa=target_cgpa,
        required_gpa=required_gpa,
        last_updated=last_updated,

        gpa_labels=gpa_labels,
        gpa_values=gpa_values
    )