from sqlalchemy import func

from extensions import db
from models.course import Course
from models.semester import Semester
from models.tracked_course import TrackedCourse
from models.transcript import Transcript
from models.users import User
from services.benchmark_services import MIN_PEERS
from services.cgpa_services import FAIL_GRADES, GRADE_POINTS

# Grades a mean grade point is rounded to for display. A+ is left out
# because it has the same point value as A, so "nearest grade" would
# be ambiguous between them.
_LABEL_SCALE = [(g, gp) for g, gp in GRADE_POINTS.items() if g != "A+"]


def _grade_label(mean_grade_point):
    """Nearest letter grade to a mean grade point, e.g. 3.28 -> 'B+'."""
    return min(_LABEL_SCALE, key=lambda item: abs(item[1] - mean_grade_point))[0]


def compute_course_stats(course_code=None, programme=None, session=None,
                         exclude_user_id=None, min_students=None, consenting_only=True,
                         faculty=None):
    """
    Grade spread and fail rate per course code, and only for courses
    with at least `min_students` students (default MIN_PEERS, the
    student-facing floor; the staff view passes its own stricter one) --
    a course below the floor is simply absent from the result, never
    returned with partial numbers.

    Who is pooled depends on who will see the result:
      consenting_only=True  (default, student-facing) -- only students
          who opted into benchmark_consent, the same gate as Peer
          Benchmarking: this is what other students get to see.
      consenting_only=False (staff analytics) -- every non-admin student
          with an uploaded transcript, whatever their sharing choice.
          The staff view is aggregate-only with a stricter floor, and
          the privacy notice says so.

    Every number is based on each student's FIRST attempt at the
    course, so a fail followed by a passing retake still counts as a
    fail (a retake is stored as a separate row in a later semester).
    An appeal that changed the grade in the same semester overwrites
    that row in place, so an appealed fail is not visible here -- the
    fail rate can only ever understate, never overstate.

    "First" means earliest by (academic_session, semester_no):
    sessions are always "YYYY/YYYY" so they sort chronologically as
    strings, and semester_no (1, 2, or 3 for a special semester) orders
    the terms within a session. Insertion/upload order is irrelevant.

    Filters:
      course_code     -- one course only (normalised: trimmed, upper-case).
      programme       -- only students enrolled in this programme.
      faculty         -- only students in this faculty.
      session         -- only students whose FIRST attempt was in this
                         academic session. The first attempt is worked
                         out from the student's whole history before
                         this filter is applied, so a later retake in
                         `session` is never mistaken for a first attempt.
      exclude_user_id -- leave this student out (a viewer looking at
                         their own programme's stats shouldn't be able
                         to back out a lone peer's grade from a pool
                         they're part of).

    Admin accounts are never part of the pool, even if consent is set
    on them (same is_admin == False rule admin_services.py applies).

    Population, in order: non-admin students (consenting ones only, unless
    consenting_only=False) -> viewer excluded ->
    each student's first attempt -> unrecognised grades dropped ->
    minimum-students check. sample_size, avg_grade_point, fail_rate and the
    distribution are all computed from that one final list of grades
    (retake_rate from the same students), so they can never disagree
    about who is in the pool.

    Returns a list of dicts sorted by course_code:
      course_code, course_name, sample_size, avg_grade_point,
      avg_grade (nearest letter), fail_rate (0-100, 1 dp),
      retake_rate (0-100, 1 dp: students with 2+ attempts),
      distribution ({grade: student count} for every grade, in
      GRADE_POINTS order).
    """
    query = (
        db.session.query(
            User.user_id,
            Course.course_code,
            Course.course_name,
            Course.grade,
            Semester.academic_session,
            Semester.semester_no,
        )
        .join(Transcript, Transcript.user_id == User.user_id)
        .join(Semester, Semester.transcript_id == Transcript.transcript_id)
        .join(Course, Course.semester_id == Semester.semester_id)
        .filter(User.is_admin == False)
    )

    if consenting_only:
        query = query.filter(User.benchmark_consent == True)
    if programme is not None:
        query = query.filter(User.programme == programme)
    if faculty is not None:
        query = query.filter(User.faculty == faculty)
    if exclude_user_id is not None:
        query = query.filter(User.user_id != exclude_user_id)
    if course_code is not None:
        query = query.filter(
            func.upper(func.trim(Course.course_code)) == course_code.strip().upper()
        )

    # Attempts per (student, course), oldest first.
    attempts = {}
    for user_id, code, name, grade, academic_session, semester_no in sorted(
        query.all(), key=lambda r: (r[4], r[5])
    ):
        attempts.setdefault((user_id, code.strip().upper()), []).append(
            (name, (grade or "").strip().upper(), academic_session)
        )

    by_course = {}
    for (_, code), rows in attempts.items():
        name, first_grade, first_session = rows[0]

        if session is not None and first_session != session:
            continue
        # An unrecognised first grade is dropped, not replaced by the
        # student's second attempt -- that would no longer be a first
        # attempt.
        if first_grade not in GRADE_POINTS:
            continue

        entry = by_course.setdefault(code, {"name": name, "grades": [], "retakes": 0})
        entry["grades"].append(first_grade)
        if len(rows) > 1:
            entry["retakes"] += 1

    floor = MIN_PEERS if min_students is None else min_students

    results = []
    for code in sorted(by_course):
        entry = by_course[code]
        grades = entry["grades"]
        sample_size = len(grades)
        if sample_size < floor:
            continue

        mean_gp = sum(GRADE_POINTS[g] for g in grades) / sample_size
        results.append({
            "course_code": code,
            "course_name": entry["name"],
            "sample_size": sample_size,
            "avg_grade_point": round(mean_gp, 2),
            "avg_grade": _grade_label(mean_gp),
            "fail_rate": round(100 * sum(g in FAIL_GRADES for g in grades) / sample_size, 1),
            "retake_rate": round(100 * entry["retakes"] / sample_size, 1),
            "distribution": {g: grades.count(g) for g in GRADE_POINTS},
        })

    return results


def get_course_stats(course_code, programme=None, session=None,
                     exclude_user_id=None, min_students=None, consenting_only=True):
    """
    compute_course_stats() for a single course. None if the course has
    fewer than the floor's eligible students -- callers show "Not
    enough data yet" for that, never a number.
    """
    results = compute_course_stats(
        course_code=course_code,
        programme=programme,
        session=session,
        exclude_user_id=exclude_user_id,
        min_students=min_students,
        consenting_only=consenting_only,
    )
    return results[0] if results else None


def get_student_course_list(user, scope="programme"):
    """
    The course statistics one student is allowed to see: every course
    with at least MIN_PEERS OTHER consenting students' first attempts,
    from the viewer's own programme (scope "programme", the default) or
    their own faculty (scope "faculty"). Never other faculties.

    The viewer is left out of the pool, so the pool never contains the
    viewer's own grade and a lone peer's grade can't be backed out of
    the average. And consent works both ways, same as Peer Benchmarking:
    a student who hasn't agreed to share gets nothing back.
    """
    if user.benchmark_consent is not True:
        return []

    if scope == "faculty":
        pool = {"faculty": user.faculty}
    else:
        pool = {"programme": user.programme}

    return compute_course_stats(exclude_user_id=user.user_id, **pool)


def get_viewer_course_status(user_id):
    """
    What the viewer has done with each course, {NORMALISED CODE: status}:
      "taken"       -- on their transcript (any attempt, passed or not);
      "in_progress" -- in their Grade Tracker for this semester but not on
                       a transcript yet.
    Any course absent from the result is "not taken yet". This is the
    viewer's own data only, used to label rows in their own list.
    """
    tracked = {
        code.strip().upper()
        for (code,) in db.session.query(TrackedCourse.course_code)
        .filter(TrackedCourse.user_id == user_id)
    }
    taken = {
        code.strip().upper()
        for (code,) in db.session.query(Course.course_code)
        .join(Semester, Course.semester_id == Semester.semester_id)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == user_id)
    }
    status = {code: "in_progress" for code in tracked}
    status.update({code: "taken" for code in taken})   # a transcript beats "in progress"
    return status
