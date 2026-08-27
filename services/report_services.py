import base64
import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from xhtml2pdf import pisa

from models.users import User
from models.transcript import Transcript
from models.semester import Semester
from models.target_cgpa import TargetCGPA
from services.cgpa_services import calculate_cgpa_credits, detect_trend, determine_feasibility
from services.benchmark_services import compute_cohort_standings_bulk
from services.career_services import build_student_profile, match_careers


TREND_NARRATIVES = {
    "Improving": "The student demonstrates a consistent improvement trend across semesters, reflecting strong academic momentum.",
    "Slightly Improving": "The student shows a gradual improvement trend across semesters, with performance trending upward.",
    "Stable": "The student's performance has remained consistent across semesters, showing steady academic stability.",
    "Volatile": "The student's performance has fluctuated notably between semesters, without a clear improving or declining direction.",
    "Slightly Declining": "The student's performance shows a slight downward trend across recent semesters.",
    "Declining": "The student's performance shows a declining trend across recent semesters that may warrant attention.",
}

STANDING_LABELS = {
    "above": "Above the cohort average",
    "equal": "On par with the cohort average",
    "slightly_below": "Slightly below the cohort average",
    "below": "Below the cohort average",
}


def _short_session(academic_session):
    """'2023/2024' -> '23/24' -- compact enough to keep the chart's
    two-line x-axis labels legible even with 6-8 semesters. The full
    4-digit year is still right there in the GPA table below the
    chart, so nothing is lost."""
    return "/".join(part[-2:] for part in academic_session.split("/"))


def render_gpa_chart_base64(semesters):
    """
    Renders the GPA progression line chart as a standalone PNG and
    returns it as a base64 data URI, so the same <img> markup works
    unchanged in both the browser preview and the PDF -- xhtml2pdf
    reads data URIs directly, no temp files or static hosting needed.
    Same visual language as the live Chart.js dashboard chart: purple
    line, round markers, 0-4.5 axis.

    Uses its own short "Sem N / YY-YY" two-line tick labels rather
    than the GPA table's full "Sem N (YYYY/YYYY)" label -- with 5+
    semesters the full label overlaps illegibly at any chart width
    that still fits the report page.
    """
    chart_labels = [f"Sem {s.semester_no}\n{_short_session(s.academic_session)}" for s in semesters]
    values = [float(s.semester_gpa) for s in semesters]

    fig, ax = plt.subplots(figsize=(6.4, 2.6), dpi=150)
    ax.plot(chart_labels, values, marker="o", color="#7776B3", linewidth=2, markersize=6)
    ax.set_ylim(0, 4.5)
    ax.set_ylabel("GPA")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.grid(axis="y", color="#e5e5e5", linewidth=0.7)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)

    encoded = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _join_with_and(items):
    """'A, B, and C' -- matches the report mockup's phrasing."""
    if not items:
        return ""
    if len(items) == 1:
        return items[0]
    if len(items) == 2:
        return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + ", and " + items[-1]


def build_report_context(user_id):
    """
    Assembles every value templates/report.html needs, for both the
    preview (HTML) and download (PDF) routes in routes/dashboard.py --
    one code path, so the two can never show different numbers for the
    same student.

    Returns {"has_transcript": False} alone if the student has no
    graded semester yet. Every other section is independently guarded
    by its own has_* flag, since a student can have semester data but
    no saved target plan, not enough peers, or no skill profile yet.
    """
    user = User.query.get(user_id)
    if user is None:
        raise ValueError("User not found.")

    semesters = (
        Semester.query
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == user_id)
        .filter(Semester.semester_gpa != None)
        .order_by(Semester.academic_session, Semester.semester_no)
        .all()
    )

    if not semesters:
        return {"has_transcript": False}

    cgpa_result = calculate_cgpa_credits(user_id)
    latest_cgpa = cgpa_result["cgpa"]
    completed_credits = cgpa_result["credits"]
    latest_semester = semesters[-1]

    gpa_labels = [f"Sem {s.semester_no} ({s.academic_session})" for s in semesters]
    gpa_values = [float(s.semester_gpa) for s in semesters]
    trend = detect_trend([{"gpa": v} for v in gpa_values])

    context = {
        "has_transcript": True,
        "generated_on": date.today().strftime("%d-%m-%Y"),
        "student_name": user.username,
        "student_department": user.programme,
        "latest_cgpa": latest_cgpa,
        "completed_credits": completed_credits,
        "latest_semester_gpa": latest_semester.semester_gpa,
        "gpa_table": list(zip(gpa_labels, gpa_values)),
        "gpa_chart": render_gpa_chart_base64(semesters),
        "trend_narrative": TREND_NARRATIVES.get(trend, TREND_NARRATIVES["Stable"]),
    }

    # ---- Target CGPA Prediction ----
    target_plan = TargetCGPA.query.filter_by(user_id=user_id).first()
    if target_plan and target_plan.target_cgpa and target_plan.remaining_credits:
        prediction_status = determine_feasibility(
            current_cgpa=latest_cgpa,
            target_cgpa=target_plan.target_cgpa,
            remaining_sems_credits=[target_plan.remaining_credits],
            trend=trend,
            required_gpa=target_plan.required_gpa or 0,
        )
        context.update({
            "has_target": True,
            "target_cgpa": target_plan.target_cgpa,
            "required_gpa": target_plan.required_gpa,
            "remaining_credits": target_plan.remaining_credits,
            "prediction_status": prediction_status,
        })
    else:
        context["has_target"] = False

    # ---- Benchmarking Summary (one row per graded semester, not just
    # the latest -- a semester with too few peers shouldn't hide the
    # semesters that do have enough data, and vice versa) ----
    standings_by_semester = compute_cohort_standings_bulk(user, semesters)
    benchmark_rows = []
    for sem in semesters:
        standing = standings_by_semester.get((sem.academic_session, sem.semester_no))
        row = {"label": f"Sem {sem.semester_no} ({sem.academic_session})", "has_data": bool(standing)}
        if standing:
            row.update({
                "compared_students": standing["sample_size"],
                "cohort_average": standing["mean"],
                "standing_label": STANDING_LABELS.get(standing["performance_band"], standing["insight"]),
            })
        benchmark_rows.append(row)

    context.update({
        "has_benchmark": any(row["has_data"] for row in benchmark_rows),
        "cohort_label": f"{user.programme} Batch {user.batch}",
        "benchmark_rows": benchmark_rows,
    })

    # ---- Career Recommendation Summary ----
    concept_profile = build_student_profile(user_id)
    if concept_profile:
        top_careers = match_careers(user_id, top_n=3, profile=concept_profile)

        matched_skills = []
        for career in top_careers:
            for skill in career["matched_competencies"]:
                if skill not in matched_skills:
                    matched_skills.append(skill)

        context.update({
            "has_careers": bool(top_careers),
            "top_careers": top_careers,
            "matched_skills_sentence": _join_with_and(matched_skills[:4]),
        })
    else:
        context["has_careers"] = False

    return context


def html_to_pdf_bytes(html_string):
    buf = io.BytesIO()
    pisa.CreatePDF(html_string, dest=buf)
    return buf.getvalue()
