import re
from datetime import date

from flask import Blueprint, render_template, Response, current_app
from flask_login import login_required, current_user
from models.transcript import Transcript
from models.semester import Semester
from models.target_cgpa import TargetCGPA
from services.cgpa_services import calculate_cgpa_credits, get_performance_alert, find_missing_semesters
from services.classification_jobs import is_building
from services.career_services import (
    build_student_profile,
    build_competency_profile,
    top_strengths,
    identify_improvement_courses,
    match_careers,
)
from services.report_services import build_report_context, html_to_pdf_bytes

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
    #
    # Wrapped: this calls Gemini for any course nobody's profile has
    # needed classified before, with no safety net of its own -- a
    # quota/network failure here (confirmed in production 2026-09-22:
    # the shared daily Gemini quota got exhausted by ordinary traffic
    # and crashed this route with a raw 500 for every visitor, not just
    # the student who happened to trigger it) must never take the whole
    # dashboard down. skill_data_error tells the template whether this
    # is a genuinely-no-transcript-yet student (has_skill_data=False,
    # skill_data_error=False -- show the upload prompt) or a transient
    # failure on a student who does have one (skill_data_error=True --
    # don't tell them to re-upload, that wouldn't help).
    has_skill_data = False
    skill_data_error = False
    # Set while the upload's background classification is still running
    # (services/classification_jobs.py) -- show "still preparing"
    # rather than starting a second, duplicate classification here.
    skill_data_building = is_building(current_user.user_id)
    dashboard_strengths = []
    dashboard_weaknesses = []
    dashboard_top_careers = []

    try:
        concept_profile = None if skill_data_building else build_student_profile(current_user.user_id)
        has_skill_data = bool(concept_profile)

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

            dashboard_careers = match_careers(current_user.user_id, top_n=3, profile=concept_profile)
            dashboard_top_careers = [c["title"] for c in dashboard_careers]
    except Exception:
        current_app.logger.exception(
            "Skill/career computation failed for user %s -- showing empty state instead of crashing",
            current_user.user_id
        )
        has_skill_data = False
        skill_data_error = True
        dashboard_strengths = []
        dashboard_weaknesses = []
        dashboard_top_careers = []

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
        missing_semesters=find_missing_semesters(semesters),
        has_skill_data=has_skill_data,
        skill_data_error=skill_data_error,
        skill_data_building=skill_data_building,
        dashboard_strengths=dashboard_strengths,
        dashboard_weaknesses=dashboard_weaknesses,
        dashboard_top_careers=dashboard_top_careers,
        performance_alert=performance_alert
    )


@dashboard_bp.route("/dashboard/report/preview")
@login_required
def report_preview():
    context = build_report_context(current_user.user_id)
    return render_template("report.html", is_pdf=False, **context)


@dashboard_bp.route("/dashboard/report/download")
@login_required
def report_download():
    context = build_report_context(current_user.user_id)
    html = render_template("report.html", is_pdf=True, **context)
    pdf_bytes = html_to_pdf_bytes(html)

    # Sanitized so an unusual username can't inject extra headers or
    # produce a malformed Content-Disposition filename.
    safe_username = re.sub(r"[^A-Za-z0-9_-]", "_", current_user.username)
    filename = f"academic_report_{safe_username}_{date.today().isoformat()}.pdf"

    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )