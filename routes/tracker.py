from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from extensions import db, limiter
from models.tracked_course import TrackedCourse, Assessment
from services.grade_tracker_services import (
    build_tracker_state,
    grade_scale,
    validate_course_fields,
    validate_assessment_fields,
)

tracker_bp = Blueprint("tracker", __name__)

# Every edit is a request, and the app-wide default (50/hour per IP) is
# far too tight for a page meant to be used a little every week -- keyed
# per-user for the same reason as routes/career.py.
TRACKER_LIMIT = "120 per minute"

# Small tolerance so 3 x 33.3 + 0.1 style float sums aren't rejected.
WEIGHT_EPSILON = 1e-6


def _user_key():
    return current_user.get_id()


def _fail(message, status=400):
    return jsonify({"success": False, "message": message}), status


def _ok():
    # Every change returns the fresh page state, so the client needs one
    # request per action rather than a change plus a reload.
    return jsonify({"success": True, "state": build_tracker_state(current_user.user_id)})


def _get_course(course_id):
    return TrackedCourse.query.filter_by(
        tracked_course_id=course_id, user_id=current_user.user_id
    ).first()


def _get_assessment(assessment_id):
    # Ownership is checked through the parent course, never trusted from
    # the request.
    return (
        Assessment.query.join(TrackedCourse)
        .filter(
            Assessment.assessment_id == assessment_id,
            TrackedCourse.user_id == current_user.user_id,
        )
        .first()
    )


def _weight_total_error(course, new_weight, exclude_assessment_id=None):
    """A message if adding/changing to `new_weight` would push the
    course's weights over 100%, else None."""

    others = sum(
        a.weight for a in course.assessments
        if a.assessment_id != exclude_assessment_id
    )

    if others + new_weight > 100 + WEIGHT_EPSILON:
        room = max(0, 100 - others)
        return (
            f"Weights can't add up to more than 100%. "
            f"This course has {room:g}% left to assign."
        )

    return None


@tracker_bp.route("/grade-tracker")
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def grade_tracker():
    return render_template(
        "tracker.html",
        active_page="tracker",
        state=build_tracker_state(current_user.user_id),
        grade_scale=grade_scale(),
    )


@tracker_bp.route("/api/tracker/courses", methods=["POST"])
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def add_course():

    try:
        fields = validate_course_fields(request.get_json(silent=True) or {})
    except ValueError as e:
        return _fail(str(e))

    if TrackedCourse.query.filter_by(
        user_id=current_user.user_id, course_code=fields["course_code"]
    ).first():
        return _fail(f"You are already tracking {fields['course_code']}.")

    db.session.add(TrackedCourse(user_id=current_user.user_id, **fields))

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _fail(f"You are already tracking {fields['course_code']}.")

    return _ok()


@tracker_bp.route("/api/tracker/courses/<int:course_id>", methods=["PATCH"])
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def edit_course(course_id):

    course = _get_course(course_id)
    if course is None:
        return _fail("Course not found.", 404)

    try:
        fields = validate_course_fields(request.get_json(silent=True) or {}, partial=True)
    except ValueError as e:
        return _fail(str(e))

    new_code = fields.get("course_code")
    if new_code and new_code != course.course_code:
        if TrackedCourse.query.filter_by(
            user_id=current_user.user_id, course_code=new_code
        ).first():
            return _fail(f"You are already tracking {new_code}.")

    for key, value in fields.items():
        setattr(course, key, value)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return _fail("That course code is already in use.")

    return _ok()


@tracker_bp.route("/api/tracker/courses/<int:course_id>", methods=["DELETE"])
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def delete_course(course_id):

    course = _get_course(course_id)
    if course is None:
        return _fail("Course not found.", 404)

    db.session.delete(course)
    db.session.commit()

    return _ok()


@tracker_bp.route("/api/tracker/courses/<int:course_id>/assessments", methods=["POST"])
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def add_assessment(course_id):

    course = _get_course(course_id)
    if course is None:
        return _fail("Course not found.", 404)

    data = request.get_json(silent=True) or {}

    try:
        fields = validate_assessment_fields(data)
    except ValueError as e:
        return _fail(str(e))

    error = _weight_total_error(course, fields["weight"])
    if error:
        return _fail(error)

    db.session.add(Assessment(tracked_course_id=course.tracked_course_id, **fields))
    db.session.commit()

    return _ok()


@tracker_bp.route("/api/tracker/assessments/<int:assessment_id>", methods=["PATCH"])
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def edit_assessment(assessment_id):

    assessment = _get_assessment(assessment_id)
    if assessment is None:
        return _fail("Assessment not found.", 404)

    try:
        fields = validate_assessment_fields(request.get_json(silent=True) or {}, partial=True)
    except ValueError as e:
        return _fail(str(e))

    if "weight" in fields:
        error = _weight_total_error(
            assessment.tracked_course, fields["weight"], assessment.assessment_id
        )
        if error:
            return _fail(error)

    for key, value in fields.items():
        setattr(assessment, key, value)

    db.session.commit()

    return _ok()


@tracker_bp.route("/api/tracker/assessments/<int:assessment_id>", methods=["DELETE"])
@login_required
@limiter.limit(TRACKER_LIMIT, key_func=_user_key)
def delete_assessment(assessment_id):

    assessment = _get_assessment(assessment_id)
    if assessment is None:
        return _fail("Assessment not found.", 404)

    db.session.delete(assessment)
    db.session.commit()

    return _ok()
