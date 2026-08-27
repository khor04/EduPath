from extensions import db
from models.semester import Semester
from models.transcript import Transcript
from models.users import User


def _classify_standing(user_gpa, mean, sample_size):
    """
    Shared by compute_cohort_standing() and compute_cohort_standings_bulk()
    so the above/below wording and thresholds have exactly one
    definition, however the caller happened to gather the numbers.
    """
    gap = round(mean - user_gpa, 2)

    if gap == 0:
        performance_band = "equal"
        insight = f"Your GPA ({user_gpa:.2f}) matches the cohort average ({mean:.2f})."
    elif gap < 0:
        performance_band = "above"
        insight = f"Your GPA ({user_gpa:.2f}) is above the cohort average ({mean:.2f})."
    elif gap < 0.15:
        performance_band = "slightly_below"
        insight = f"Your GPA ({user_gpa:.2f}) is slightly below the cohort average ({mean:.2f})."
    else:
        performance_band = "below"
        insight = f"Your GPA ({user_gpa:.2f}) is below the cohort average ({mean:.2f})."

    return {
        "mean": mean,
        "sample_size": sample_size,
        "user_gpa": user_gpa,
        "performance_band": performance_band,
        "insight": insight,
    }


def compute_cohort_standing(user, session, semester_no):
    """
    How `user`'s GPA in one semester compares to their programme+batch
    cohort. Used by the live Benchmarking widget (routes/benchmark.py),
    which only ever needs one semester at a time (whichever the
    student picked from the dropdown) -- see
    compute_cohort_standings_bulk() for the Dashboard Report's
    all-semesters-at-once equivalent.

    Peers only, same anonymity floor as the rest of benchmarking: the
    viewer is compared against at least 2 OTHER students, never folded
    into its own average. Returns None if that floor isn't met, or if
    the user has no recorded GPA for this session/semester.
    """
    cohort_gpas = (
        db.session.query(Semester.semester_gpa)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .join(User, Transcript.user_id == User.user_id)
        .filter(
            User.user_id != user.user_id,
            User.programme == user.programme,
            User.batch == user.batch,
            Semester.academic_session == session,
            Semester.semester_no == semester_no,
            Semester.semester_gpa != None
        )
        .all()
    )

    gpa_values = [g[0] for g in cohort_gpas]
    sample_size = len(gpa_values)

    if sample_size < 2:
        return None

    user_sem = (
        db.session.query(Semester)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(
            Transcript.user_id == user.user_id,
            Semester.academic_session == session,
            Semester.semester_no == semester_no
        )
        .first()
    )

    if not user_sem or user_sem.semester_gpa is None:
        return None

    mean = round(sum(gpa_values) / sample_size, 2)
    return _classify_standing(user_sem.semester_gpa, mean, sample_size)


def compute_cohort_standings_bulk(user, semesters):
    """
    Same per-semester standing as compute_cohort_standing(), for every
    semester in `semesters` (Semester ORM rows already known to belong
    to `user`) in ONE query instead of one round trip per semester --
    built for the Dashboard Report, which needs every semester at
    once. Against a remote DB, N sequential compute_cohort_standing()
    calls cost N network round trips each; this costs one, regardless
    of how many semesters the student has.

    Returns a dict keyed by (academic_session, semester_no) -> the
    same shape compute_cohort_standing() returns. A semester that
    doesn't meet the peer-count floor is simply absent from the dict
    (mirroring compute_cohort_standing()'s None return for that case).
    """
    if not semesters:
        return {}

    # Fetches the whole cohort's semester history in one shot rather
    # than filtering to just the caller's semesters -- avoids a
    # composite (session, semester_no) IN-clause, whose row-value
    # syntax isn't reliably portable across SQLite (used in tests) and
    # Postgres (used in production). The row count this pulls back is
    # bounded by cohort size x their semester count, which is small.
    cohort_rows = (
        db.session.query(Semester.academic_session, Semester.semester_no, Semester.semester_gpa)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .join(User, Transcript.user_id == User.user_id)
        .filter(
            User.user_id != user.user_id,
            User.programme == user.programme,
            User.batch == user.batch,
            Semester.semester_gpa != None
        )
        .all()
    )

    grouped = {}
    for academic_session, semester_no, gpa in cohort_rows:
        grouped.setdefault((academic_session, semester_no), []).append(gpa)

    results = {}
    for sem in semesters:
        if sem.semester_gpa is None:
            continue

        gpa_values = grouped.get((sem.academic_session, sem.semester_no), [])
        sample_size = len(gpa_values)
        if sample_size < 2:
            continue

        mean = round(sum(gpa_values) / sample_size, 2)
        results[(sem.academic_session, sem.semester_no)] = _classify_standing(sem.semester_gpa, mean, sample_size)

    return results
