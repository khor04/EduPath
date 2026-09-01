"""
Backend logic for the EduPath AI chat assistant: the compact,
facts-only academic summary injected into its prompt
(services/gemini_service.generate_chat_response()), and the
conservative deep-link matcher used to suggest a relevant page.

This file deliberately does no interpretation of its own -- every
number and label here comes straight from the same authoritative
functions Dashboard/Career/Analysis/Benchmarking already call
(calculate_cgpa_credits, detect_trend, determine_feasibility,
compute_cohort_standing, build_student_profile, top_strengths,
identify_improvement_courses, match_careers). Gemini does the
interpreting; this only gathers facts, so the assistant can never
disagree with what the student already sees elsewhere in the app.

Kept intentionally compact -- a handful of summary lines, not full
semester/course/career datasets -- so a general-knowledge question
("what is recursion?") doesn't carry an unneeded data dump, and so
this doesn't drift into "just include everything" as the app grows.
"""
from models.users import User
from models.transcript import Transcript
from models.semester import Semester
from models.target_cgpa import TargetCGPA
from services.cgpa_services import calculate_cgpa_credits, detect_trend, determine_feasibility
from services.benchmark_services import compute_cohort_standing
from services.career_services import (
    build_student_profile,
    build_competency_profile,
    top_strengths,
    identify_improvement_courses,
    match_careers,
)

STANDING_LABELS = {
    "above": "above the cohort average",
    "equal": "on par with the cohort average",
    "slightly_below": "slightly below the cohort average",
    "below": "below the cohort average",
}


def build_chat_context(user_id):
    """
    Returns {"has_data": False, "summary_text": None} if the student
    has no graded semester yet -- the assistant can still answer
    general academic questions in that case, just without personal
    context. Otherwise returns {"has_data": True, "summary_text": "..."}
    ready to inject directly into the chat prompt.
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
        return {"has_data": False, "summary_text": None, "has_target": False, "top_career_title": None}

    cgpa_result = calculate_cgpa_credits(user_id)
    trend = detect_trend([{"gpa": float(s.semester_gpa)} for s in semesters])

    lines = [
        f"Current CGPA: {cgpa_result['cgpa']:.2f}",
        f"Credits completed: {cgpa_result['credits']}",
        f"Overall GPA trend: {trend}",
    ]

    # Only the most recent semesters, not the full history -- enough
    # to answer "why did my GPA change" without a full transcript dump.
    for sem in semesters[-2:]:
        lines.append(f"Sem {sem.semester_no} ({sem.academic_session}) GPA: {float(sem.semester_gpa):.2f}")

    target_plan = TargetCGPA.query.filter_by(user_id=user_id).first()
    has_target = bool(target_plan and target_plan.target_cgpa and target_plan.remaining_credits)
    if has_target:
        prediction_status = determine_feasibility(
            current_cgpa=cgpa_result["cgpa"],
            target_cgpa=target_plan.target_cgpa,
            remaining_sems_credits=[target_plan.remaining_credits],
            trend=trend,
            required_gpa=target_plan.required_gpa or 0,
        )
        lines.append(f"Target CGPA: {target_plan.target_cgpa:.2f}")
        lines.append(f"Required GPA on remaining credits: {(target_plan.required_gpa or 0):.2f}")
        lines.append(f"Target prediction status: {prediction_status}")
    else:
        lines.append("No target CGPA plan saved yet.")

    latest_sem = semesters[-1]
    standing = compute_cohort_standing(user, latest_sem.academic_session, latest_sem.semester_no)
    if standing:
        label = STANDING_LABELS.get(standing["performance_band"], standing["insight"])
        lines.append(f"Latest semester standing vs cohort: {label} (cohort average {standing['mean']:.2f})")
    else:
        lines.append("Not enough peer data yet to compare against the cohort.")

    top_career_title = None

    concept_profile = build_student_profile(user_id)
    if concept_profile:
        competency_profile = build_competency_profile(concept_profile)
        strengths = top_strengths(competency_profile, top_n=3)
        if strengths:
            lines.append("Top academic strengths: " + ", ".join(row["competency_name"] for row in strengths))

        # Deliberately labeled as a plain fact ("lower grades"), not a
        # causal claim ("courses affecting your CGPA") -- the ranking
        # underneath is already credit-weighted (grade_weakness x
        # relevance_weight x credit_hour), but that doesn't make "this
        # course hurt your CGPA" a fact this context should assert on
        # the student's behalf. Let Gemini phrase the interpretation.
        improvement_courses = identify_improvement_courses(user_id, top_n=5)
        if improvement_courses:
            lines.append("Courses with lower grades:")
            for c in improvement_courses:
                lines.append(f"  - {c['course_title']}: {c['grade']}")

        top_careers = match_careers(user_id, top_n=3, profile=concept_profile)
        if top_careers:
            lines.append("Top career matches:")
            for career in top_careers:
                lines.append(f"  - {career['title']}: {career['match_percentage']:.0f}%")
            top_career_title = top_careers[0]["title"]

    return {
        "has_data": True,
        "summary_text": "\n".join(lines),
        # Exposed so /api/chat/suggestions can tailor its starter
        # questions without recomputing target_plan/match_careers a
        # second time -- these are already-computed byproducts of
        # building the summary above, not new work.
        "has_target": has_target,
        "top_career_title": top_career_title,
    }


# Matched against the student's OWN question only, never the generated
# answer -- an answer that merely mentions "benchmarking" in passing
# while actually being about something else would produce a misleading
# link if matched against the answer text instead. Checked in this
# order; the first match wins, so at most one link is ever returned.
# A vague question ("how can I improve my GPA?") intentionally matches
# nothing here rather than guessing a destination.
_DEEP_LINK_RULES = [
    (("target cgpa", "target gpa", "required gpa", "prediction", "target"), "analysis"),
    (("career", "occupation", "job", "recommended", "recommendation"), "career"),
    (("benchmark", "peer", "cohort"), "benchmark"),
]


def get_deep_link_module(message):
    """Returns 'analysis' / 'career' / 'benchmark' / None."""
    lowered = message.lower()
    for keywords, module_key in _DEEP_LINK_RULES:
        if any(kw in lowered for kw in keywords):
            return module_key
    return None


# Maps get_performance_alert()'s "type" to a ready-to-send follow-up
# question -- clicking the proactive alert in the chat greeting sends
# this straight to /api/chat, the same as clicking a suggestion chip,
# so the student can act on the flag in one click instead of typing
# their own question about it.
_ALERT_FOLLOWUP_QUESTIONS = {
    "target_below": "Why does it look like I might fall short of my target CGPA, and what can I do about it?",
    "required_high": "My required GPA looks very high -- is my target still realistic, and what are my options?",
    "volatile": "Why has my GPA been fluctuating, and how can I make my performance more consistent?",
    "declining": "Why is my GPA declining, and what should I focus on to turn it around?",
}


def get_alert_followup_question(alert_type):
    """Falls back to a generic prompt for any alert type not in the map."""
    return _ALERT_FOLLOWUP_QUESTIONS.get(
        alert_type,
        "I noticed something worth discussing about my academic progress -- can you help?"
    )
