from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required, current_user
from extensions import db

from models.transcript import Transcript
from models.semester import Semester
from models.users import User

benchmark_bp = Blueprint("benchmark", __name__)
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

@benchmark_bp.route("/api/benchmark-data")
@login_required
def benchmark_data():

    session = (request.args.get("session") or "").strip()
    semester_arg = request.args.get("semester")
    if not session or semester_arg is None:
        return jsonify({"error": "Invalid parameters"})
    semester_no = int(semester_arg)

    if not session or not semester_no:
        return jsonify({"error": "Invalid parameters"})

    cohort_gpas = (
        db.session.query(Semester.semester_gpa)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .join(User, Transcript.user_id == User.user_id)
        .filter(
            User.programme == current_user.programme,
            User.batch == current_user.batch,
            Semester.academic_session == session,
            Semester.semester_no == semester_no,
            Semester.semester_gpa != None
        )
        .all()
    )

    gpa_values = [g[0] for g in cohort_gpas]
    sample_size = len(gpa_values)

    if sample_size < 2:
        return jsonify({
            "error": "not_enough_data",
            "sample_size": sample_size
        })

    mean = round(sum(gpa_values) / sample_size, 2)

    user_sem = (
        db.session.query(Semester)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(
            Transcript.user_id == current_user.user_id,
            Semester.academic_session == session,
            Semester.semester_no == semester_no
        )
        .first()
    )

    user_gpa = user_sem.semester_gpa

    bins = [0] * 8
    for gpa in gpa_values:
        index = int((gpa - 2.4) // 0.2)
        index = max(0, min(index, 7))
        bins[index] += 1

    gap = mean - user_gpa

    if gap <= 0:
        performance_band = "above"
        insight = f"Your GPA ({user_gpa:.2f}) is above the cohort average ({mean:.2f})."
    elif gap < 0.15:
        performance_band = "slightly_below"
        insight = f"Your GPA ({user_gpa:.2f}) is slightly below the cohort average ({mean:.2f})."
    else:
        performance_band = "below"
        insight = f"Your GPA ({user_gpa:.2f}) is below the cohort average ({mean:.2f})."

    return jsonify({
        "histogram": bins,
        "mean": mean,
        "sample_size": sample_size,
        "user_gpa": user_gpa,
        "insight": insight,
        "performance_band": performance_band
    })
@benchmark_bp.route("/api/benchmark-trend")
@login_required
def benchmark_trend():

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
                User.programme == current_user.programme,
                User.batch == current_user.batch,
                Semester.academic_session == sem.academic_session,
                Semester.semester_no == sem.semester_no,
                Semester.semester_gpa != None
            )
            .all()
        )
        values = [g[0] for g in cohort_gpas]

        cohort.append(round(sum(values) / len(values), 2) if len(values) >= 2 else None)

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