from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user

from extensions import db, limiter
from models.career_recommendation import CareerRecommendation
from models.feedback import Feedback
from services.classification_jobs import ensure_profile_build, is_building
from services.career_services import (
    build_student_profile,
    build_competency_profile,
    top_strengths,
    identify_improvement_courses,
    save_skill_profile,
    match_careers,
    save_career_recommendations,
)

career_bp = Blueprint("career", __name__)

# Career page layout: the top matches, then a smaller "you may also like" row.
BEST_MATCH_COUNT = 3
MORE_MATCH_COUNT = 2


def _career_rate_limit():
    """
    This page's cap is tighter than the app default because it can do
    real work: career matching plus writes to SkillProfile/
    CareerRecommendation, and a Gemini classification for any course
    still uncached. 30/minute is still far above normal use (a student
    revisiting and refreshing), while stopping a stuck tab from
    hammering it.

    While the post-upload classification is running it does none of
    that -- it just renders "preparing" -- and that is exactly when a
    student is most likely to refresh by hand rather than wait. Locking
    them out of the page they're waiting on, with a "please slow down"
    message, would be the worst possible moment for it. Evaluated per
    request, so the normal cap returns the moment the work is real
    again.
    """
    try:
        if is_building(current_user.user_id):
            return "60 per minute"
    except Exception:
        pass
    return "30 per minute"


@career_bp.route("/career")
@login_required
# Keyed per-user, not the default per-IP -- this is behind
# @login_required, and IP-based limiting would let testers sharing a
# network (e.g. campus wifi during UAT) throttle each other.
@limiter.limit(_career_rate_limit, key_func=lambda: current_user.get_id())
def career():
    # Skill/career computation calls Gemini for any course nobody's
    # profile has ever needed classified before (services/career_services.py).
    # That call has no safety net of its own -- a quota/network failure
    # (confirmed in production: the shared daily Gemini quota across
    # dashboard/career/AI-planner/chatbot got exhausted by ordinary
    # traffic and crashed this route with a raw 500) must never take
    # the whole page down. "reason" tells the template whether this is
    # a genuinely-no-transcript-yet student (show the upload prompt) or
    # a transient failure on a student who does have one (don't tell
    # them to re-upload -- that wouldn't help and would be confusing).
    # Still classifying in the background after an upload? Say so,
    # instead of starting a second, duplicate classification of the
    # same courses here (services/classification_jobs.py).
    if ensure_profile_build(current_user.user_id):
        return render_template("career_locked.html", active_page="career", reason="building")

    try:
        concept_profile = build_student_profile(current_user.user_id)
    except Exception:
        current_app.logger.exception(
            "Skill profile computation failed for user %s", current_user.user_id
        )
        return render_template("career_locked.html", active_page="career", reason="error")

    if not concept_profile:
        return render_template("career_locked.html", active_page="career", reason="no_transcript")

    try:
        competency_profile = build_competency_profile(concept_profile)

        strengths = top_strengths(competency_profile, top_n=5)
        improvement_courses = identify_improvement_courses(current_user.user_id, top_n=5)
        careers = match_careers(current_user.user_id, top_n=BEST_MATCH_COUNT + MORE_MATCH_COUNT, profile=concept_profile)
        save_skill_profile(current_user.user_id, competency_profile, top_n=5)

        name_to_career_id = save_career_recommendations(current_user.user_id, careers)
        for c in careers:
            c["career_id"] = name_to_career_id[c["title"]]

        radar_labels = [row["competency_name"] for row in strengths]
        radar_values = [row["percentage"] for row in strengths]
    except Exception:
        current_app.logger.exception(
            "Career recommendation computation failed for user %s", current_user.user_id
        )
        return render_template("career_locked.html", active_page="career", reason="error")

    return render_template(
        "career.html",
        active_page="career",
        strengths=strengths,
        improvement_courses=improvement_courses,
        careers=careers,
        best_careers=careers[:BEST_MATCH_COUNT],
        more_careers=careers[BEST_MATCH_COUNT:],
        radar_labels=radar_labels,
        radar_values=radar_values,
    )


@career_bp.route("/career/feedback/<int:career_id>", methods=["POST"])
@login_required
def submit_career_feedback(career_id):
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")

    if rating not in (1, 2, 3, 4, 5):
        return jsonify({"success": False, "error": "Invalid rating."}), 400

    # Ownership check -- career_id is a guessable sequential integer,
    # so without this a user could submit feedback against any other
    # student's recommendation by trying different IDs.
    career = CareerRecommendation.query.filter_by(
        career_id=career_id, user_id=current_user.user_id
    ).first()
    if career is None:
        return jsonify({"success": False, "error": "Recommendation not found."}), 404

    db.session.add(Feedback(career_id=career_id, rating=rating))
    db.session.commit()

    return jsonify({"success": True})
