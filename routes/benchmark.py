from flask import Blueprint, render_template, jsonify, request, redirect, url_for
from flask_login import login_required, current_user
from extensions import db

from models.transcript import Transcript
from models.semester import Semester
from models.users import User
from services.benchmark_services import compute_cohort_standing, MIN_PEERS

benchmark_bp = Blueprint("benchmark", __name__)

# Histogram binning — single source of truth for both the API
# response and the "which bin am I in" calculation, so the
# frontend never needs to duplicate this formula.
BIN_WIDTH = 0.2
BIN_MIN = 2.4
BIN_COUNT = 8


def compute_bin_index(gpa):
    index = int((gpa - BIN_MIN) // BIN_WIDTH)
    return max(0, min(index, BIN_COUNT - 1))
@benchmark_bp.route("/benchmarking")
@login_required
def benchmark():

    transcript = Transcript.query.filter_by(
        user_id=current_user.user_id
    ).first()

    if not transcript:
        return render_template(
            "benchmarking_locked.html",
            active_page="benchmark"
        )

    # Consent gates both directions: a student's data only enters the
    # peer pool, and they can only view peer comparisons, once this is
    # explicitly True. None means they haven't decided yet (prompt
    # them); False means they declined (show why it's unavailable).
    if current_user.benchmark_consent is None:
        return render_template(
            "benchmarking_consent.html",
            active_page="benchmark"
        )

    if current_user.benchmark_consent is False:
        return render_template(
            "benchmarking_declined.html",
            active_page="benchmark"
        )

    semesters = (
        Semester.query
        .join(Transcript)
        .filter(Transcript.user_id == current_user.user_id)
        .order_by(Semester.academic_session, Semester.semester_no)
        .all()
    )

    semester_options = [
        {
            "academic_session": s.academic_session,
            "semester_no": s.semester_no
        }
        for s in semesters
    ]
    print("SEMESTERS:", semester_options)

    return render_template(
        "benchmarking.html",
        semesters=semester_options,
        active_page="benchmark"
    )


@benchmark_bp.route("/benchmarking/consent", methods=["POST"])
@login_required
def benchmark_consent():
    choice = request.form.get("choice")

    # Small whitelist, not a raw redirect target -- lets Profile's
    # toggle send the student back to Profile instead of always
    # bouncing to the Benchmarking page.
    next_endpoint = (
        "profile.profile" if request.form.get("next") == "profile"
        else "benchmark.benchmark"
    )

    if choice not in ("yes", "no"):
        return redirect(url_for(next_endpoint))

    current_user.benchmark_consent = (choice == "yes")
    db.session.commit()

    return redirect(url_for(next_endpoint))


@benchmark_bp.route("/api/benchmark-data")
@login_required
def benchmark_data():

    # Consent gates access as well as participation -- enforced here
    # (not just in the /benchmarking page's own redirect) since this
    # is also called from the Dashboard's peer comparison card, which
    # isn't gated by the same route.
    if current_user.benchmark_consent is not True:
        return jsonify({"error": "consent_required", "sample_size": 0})

    session = (request.args.get("session") or "").strip()
    semester_arg = request.args.get("semester")
    if not session or semester_arg is None:
        return jsonify({"error": "Invalid parameters"})
    semester_no = int(semester_arg)

    if not session or not semester_no:
        return jsonify({"error": "Invalid parameters"})

    standing = compute_cohort_standing(current_user, session, semester_no)

    # "not enough data" covers both too few peers and no recorded GPA
    # for this session/semester — compute_cohort_standing() can't tell
    # the API response apart, but the caller doesn't need to either.
    if standing is None:
        return jsonify({
            "error": "not_enough_data",
            "sample_size": 0
        })

    # Histogram binning is a display-only concern of this live widget
    # (not needed by the Dashboard Report), so it stays local here
    # rather than living in compute_cohort_standing().
    cohort_gpas = (
        db.session.query(Semester.semester_gpa)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .join(User, Transcript.user_id == User.user_id)
        .filter(
            User.user_id != current_user.user_id,
            User.programme == current_user.programme,
            User.batch == current_user.batch,
            User.benchmark_consent == True,
            Semester.academic_session == session,
            Semester.semester_no == semester_no,
            Semester.semester_gpa != None
        )
        .all()
    )

    bins = [0] * BIN_COUNT
    for (gpa,) in cohort_gpas:
        bins[compute_bin_index(gpa)] += 1

    return jsonify({
        "histogram": bins,
        "mean": standing["mean"],
        "sample_size": standing["sample_size"],
        "user_gpa": standing["user_gpa"],
        "user_bin_index": compute_bin_index(standing["user_gpa"]),
        "insight": standing["insight"],
        "performance_band": standing["performance_band"]
    })
@benchmark_bp.route("/api/benchmark-trend")
@login_required
def benchmark_trend():

    if current_user.benchmark_consent is not True:
        return jsonify({
            "labels": [], "student": [], "cohort": [],
            "trend_insight": "Set your sharing preference on Peer Benchmarking to see this."
        })

    semesters = (
        Semester.query
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == current_user.user_id)
        .filter(Semester.semester_gpa != None)
        .order_by(Semester.academic_session, Semester.semester_no)
        .all()
    )

    if not semesters:
        return jsonify({
            "labels": [], "student": [], "cohort": [],
            "trend_insight": "Not enough data to determine a trend yet."
        })

    labels, student, cohort = [], [], []

    for sem in semesters:
        labels.append(f"{sem.academic_session} - Semester {sem.semester_no}")
        student.append(sem.semester_gpa)

        cohort_gpas = (
            db.session.query(Semester.semester_gpa)
            .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
            .join(User, Transcript.user_id == User.user_id)
            .filter(
                User.user_id != current_user.user_id,
                User.programme == current_user.programme,
                User.batch == current_user.batch,
                User.benchmark_consent == True,
                Semester.academic_session == sem.academic_session,
                Semester.semester_no == sem.semester_no,
                Semester.semester_gpa != None
            )
            .all()
        )
        values = [g[0] for g in cohort_gpas]

        # Same anonymity floor as benchmark_data(): require at
        # least MIN_PEERS OTHER peers before revealing an average.
        cohort.append(round(sum(values) / len(values), 2) if len(values) >= MIN_PEERS else None)

    valid_pairs = [(s, c) for s, c in zip(student, cohort) if s is not None and c is not None]

    if valid_pairs:
        above_count = sum(1 for s, c in valid_pairs if s > c)
        below_count = sum(1 for s, c in valid_pairs if s < c)
        total = len(valid_pairs)

        if above_count == total:
            trend_insight = "Your GPA has remained above the department average in every semester — great consistency."
        elif below_count == total:
            trend_insight = "Your GPA has been below the department average so far. \n\nConsistent effort across semesters can help shift this trend."
        elif above_count > below_count:
            trend_insight = f"Your GPA has been above the department average in most semesters ({above_count} out of {total})."
        elif below_count > above_count:
            trend_insight = f"Your GPA has been below the department average in some semesters ({below_count} out of {total}). \n\nProgress often isn't linear — small improvements can shift this over time."
        else:
            trend_insight = f"Your GPA has closely tracked the department average across {total} semesters."
    else:
        trend_insight = "Not enough peer data yet to show a department comparison trend."

    return jsonify({
        "labels": labels,
        "student": student,
        "cohort": cohort,
        "trend_insight": trend_insight
    })