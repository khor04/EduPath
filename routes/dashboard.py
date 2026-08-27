from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models.transcript import Transcript
from models.semester import Semester
from models.target_cgpa import TargetCGPA
from services.cgpa_services import calculate_cgpa_credits, get_performance_alert
from services.career_services import (
    build_student_profile,
    build_competency_profile,
    top_strengths,
    identify_improvement_courses,
    match_careers,
)

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
    gpa_labels = [f"Sem {s.semester_no} ({s.academic_session})" for s in semesters]
    gpa_values = [float(sem.semester_gpa or 0) for sem in semesters]

    semester_options = [
        {
            "academic_session": s.academic_session,
            "semester_no": s.semester_no
        }
        for s in semesters
        if s.semester_gpa is not None   # only let users pick semesters that actually have a GPA
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
    target_plan = TargetCGPA.query.filter_by(user_id=current_user.user_id).first()
    target_cgpa = round(target_plan.target_cgpa, 2) if target_plan else None
    required_gpa = round(target_plan.required_gpa, 2) if target_plan else None

    performance_alert = get_performance_alert(current_user.user_id)

    # Real Academic Strength/Weakness and Career Pathways -- same
    # pipeline the Career page uses, condensed for a glance-level
    # summary. Read-only here: unlike /career, this doesn't persist
    # into SkillProfile/CareerRecommendation, since Dashboard is
    # likely visited far more often and that data's only real
    # consumer (Feedback) lives on the Career page.
    concept_profile = build_student_profile(current_user.user_id)
    has_skill_data = bool(concept_profile)

    dashboard_strengths = []
    dashboard_weaknesses = []
    dashboard_strong_careers = []
    dashboard_moderate_careers = []

    if has_skill_data:
        competency_profile = build_competency_profile(concept_profile)
        dashboard_strengths = [row["competency_name"] for row in top_strengths(competency_profile, top_n=3)]

        # Course-driven, same as the Career page's "Areas to Strengthen"
        # -- not the competency names, so a student clicking through to
        # /career finds exactly what this preview showed them.
        improvement_courses = identify_improvement_courses(current_user.user_id, top_n=3)
        dashboard_weaknesses = [
            {"course_title": c["course_title"], "grade": c["grade"]}
            for c in improvement_courses
        ]

        dashboard_careers = match_careers(current_user.user_id, top_n=3)
        dashboard_strong_careers = [c["title"] for c in dashboard_careers if c["tier_class"] == "strong"]
        dashboard_moderate_careers = [c["title"] for c in dashboard_careers if c["tier_class"] == "moderate"]

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        semesters=semester_options,
        latest_cgpa=round(latest_cgpa, 2),
        completed_credits=int(completed_credits),
        target_cgpa=target_cgpa,
        required_gpa=required_gpa,
        last_updated=last_updated,
        gpa_labels=gpa_labels,
        gpa_values=gpa_values,
        has_skill_data=has_skill_data,
        dashboard_strengths=dashboard_strengths,
        dashboard_weaknesses=dashboard_weaknesses,
        dashboard_strong_careers=dashboard_strong_careers,
        dashboard_moderate_careers=dashboard_moderate_careers,
        performance_alert=performance_alert
    )