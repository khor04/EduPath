from models.course import Course
from models.semester import Semester
from models.transcript import Transcript
from extensions import db
from decimal import Decimal, ROUND_HALF_UP

FAIL_GRADES = {
    "F",
    "D",
    "D+",
    "C-"
}

# Official UM grade -> grade-point-per-credit mapping.
GRADE_POINTS = {
    "A+": 4.00,
    "A":  4.00,
    "A-": 3.70,
    "B+": 3.30,
    "B":  3.00,
    "B-": 2.70,
    "C+": 2.30,
    "C":  2.00,
    "C-": 1.70,
    "D+": 1.30,
    "D":  1.00,
    "F":  0.00,
}


class Attempt:
    """
    Lightweight stand-in for a single course attempt — either a
    real Course row or a hypothetical simulated one — so the
    best-attempt-selection logic below can run over a mix of both
    without needing to know which is which.
    """

    __slots__ = ("course_code", "credit_hour", "grade", "grade_point")

    def __init__(self, course_code, credit_hour, grade, grade_point):
        self.course_code = course_code
        self.credit_hour = credit_hour
        self.grade = grade
        self.grade_point = grade_point


def _group_by_code(attempts):
    courses_by_code = {}

    for a in attempts:
        code = a.course_code.strip().upper()
        courses_by_code.setdefault(code, []).append(a)

    return courses_by_code


def _compute_cgpa_from_groups(courses_by_code):
    """
    The single source of truth for turning a set of (possibly
    multiple-attempt) courses into a CGPA + earned credits figure.
    Used by both calculate_cgpa_credits() and simulate_cgpa(), so
    a simulated "retake" is guaranteed to be scored by exactly the
    same rule as a real one — pick the best passing attempt among
    all attempts for that course code, or the latest/worst if the
    student never passed it.
    """

    total_registered_credits = Decimal("0")
    earned_credits = Decimal("0")
    total_points = Decimal("0")

    for code, attempts in courses_by_code.items():
        passed_attempts = [a for a in attempts if a.grade not in FAIL_GRADES]

        if passed_attempts:
            # Student eventually passed — use best grade attempt only
            best = max(passed_attempts, key=lambda x: float(x.grade_point or 0))
        else:
            # Student failed all attempts — use latest/worst (still counts against CGPA)
            best = attempts[-1]

        credit = Decimal(str(best.credit_hour or 0))
        gp = Decimal(str(best.grade_point or 0))

        total_registered_credits += credit
        total_points += gp

        if best.grade not in FAIL_GRADES:
            earned_credits += credit

    if total_registered_credits == 0:
        return {"cgpa": 0.0, "credits": 0}

    cgpa = total_points / total_registered_credits
    cgpa_rounded = float(cgpa.quantize(Decimal("0.00"), rounding=ROUND_HALF_UP))

    return {
        "cgpa": cgpa_rounded,
        "credits": int(earned_credits)
    }


def _fetch_user_courses(user_id):
    return (
        db.session.query(Course)
        .join(Semester)
        .join(Transcript)
        .filter(Transcript.user_id == user_id)
        .all()
    )


def calculate_cgpa_credits(user_id):

    courses = _fetch_user_courses(user_id)

    attempts = [
        Attempt(c.course_code, c.credit_hour, c.grade, c.grade_point)
        for c in courses
    ]

    return _compute_cgpa_from_groups(_group_by_code(attempts))


def simulate_cgpa(user_id, simulated_entries):
    """
    Projects CGPA if the given hypothetical course entries were
    added to the student's actual course history.

    Reuses _compute_cgpa_from_groups() — the exact same
    best-attempt-per-course-code rule calculate_cgpa_credits()
    uses — so a simulated retake only changes the projected CGPA
    if it would actually beat (or is needed because there's no)
    an existing passing attempt for that course, matching how a
    real retake would be scored.

    simulated_entries: list of dicts, each either
      {"type": "retake", "course_id": int, "grade": "A"}
      {"type": "future", "credits": float, "grade": "A"}
    """

    courses = _fetch_user_courses(user_id)
    courses_by_id = {c.course_id: c for c in courses}

    attempts = [
        Attempt(c.course_code, c.credit_hour, c.grade, c.grade_point)
        for c in courses
    ]

    for index, entry in enumerate(simulated_entries):

        grade = (entry.get("grade") or "").strip().upper()

        if grade not in GRADE_POINTS:
            raise ValueError(f"Unknown grade: {entry.get('grade')!r}")

        entry_type = entry.get("type")

        if entry_type == "retake":

            real_course = courses_by_id.get(entry.get("course_id"))

            if real_course is None:
                raise ValueError("Course not found.")

            credit_hour = real_course.credit_hour
            course_code = real_course.course_code

        elif entry_type == "future":

            credit_hour = float(entry.get("credits") or 0)

            if credit_hour <= 0:
                raise ValueError("Future course credits must be greater than 0.")

            # Unique synthetic code so a "future course" entry
            # never merges with a real course code, or with
            # another future-course entry.
            course_code = f"__FUTURE_{index}__"

        else:
            raise ValueError(f"Unknown entry type: {entry_type!r}")

        grade_point = GRADE_POINTS[grade] * credit_hour

        attempts.append(
            Attempt(course_code, credit_hour, grade, grade_point)
        )

    return _compute_cgpa_from_groups(_group_by_code(attempts))
