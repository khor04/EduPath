from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user

from extensions import db
from models.career_recommendation import CareerRecommendation
from models.feedback import Feedback
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

@career_bp.route("/career")
@login_required
def career():
    concept_profile = build_student_profile(current_user.user_id)

    if not concept_profile:
        return render_template(
            "career.html",
            active_page="career",
            has_profile=False,
        )

    competency_profile = build_competency_profile(concept_profile)

    strengths = top_strengths(competency_profile, top_n=5)
    improvement_courses = identify_improvement_courses(current_user.user_id, top_n=5)
    careers = match_careers(current_user.user_id, top_n=6, profile=concept_profile)
    save_skill_profile(current_user.user_id, competency_profile, top_n=5)

    name_to_career_id = save_career_recommendations(current_user.user_id, careers)
    for c in careers:
        c["career_id"] = name_to_career_id[c["title"]]

    radar_labels = [row["competency_name"] for row in strengths]
    radar_values = [row["percentage"] for row in strengths]

    return render_template(
        "career.html",
        active_page="career",
        has_profile=True,
        strengths=strengths,
        improvement_courses=improvement_courses,
        careers=careers,
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
