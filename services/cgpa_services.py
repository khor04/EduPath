from models.course import Course
from models.semester import Semester
from models.transcript import Transcript
from models.target_cgpa import TargetCGPA
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


def project_cgpa(current_cgpa, current_credits, remaining_credits, assumed_gpa):
    """
    Credit-weighted CGPA projection — the server-side twin of
    projectCGPA() in analysis.js. Kept here as the single shared
    formula so the Target CGPA Simulator (client-side) and the
    Dashboard's Performance Alert (server-side) can never drift
    into computing "projected CGPA" two different ways.
    """

    total_credits = current_credits + remaining_credits

    if total_credits <= 0:
        return current_cgpa

    return (
        (current_cgpa * current_credits) + (assumed_gpa * remaining_credits)
    ) / total_credits

##reusable for dashboard and analysis page
def detect_trend(history):
    """
    Classifies a chronological semester GPA history into a trend
    label. `history` is a list of dicts with a "gpa" key.
    """

    if len(history) < 2:
        return "Stable"

    gpas = [h["gpa"] for h in history]  # eg: gpas = [3.53,3.81,4.0,4.0]
    deltas = [gpas[i + 1] - gpas[i] for i in range(len(gpas) - 1)]  # semester-to-semester changes
    avg_change = sum(deltas) / len(deltas)

    # count positive & negative changes; ignore changes == 0
    positive = sum(1 for d in deltas if d > 0)
    negative = sum(1 for d in deltas if d < 0)
    non_zero = positive + negative

    # substantial swings in both directions = instability, not a
    # clean improving/declining trend
    is_volatile = (
        max(deltas) - min(deltas) > 0.5
        and positive > 0
        and negative > 0
    )

    if non_zero > 0:
        positive_ratio = positive / non_zero
        negative_ratio = negative / non_zero
    else:
        positive_ratio = 0
        negative_ratio = 0

    # 0.75 = at least 75% of semester changes point the same way
    if is_volatile:
        return "Volatile"
    elif positive_ratio >= 0.75 and avg_change > 0:
        return "Improving"
    elif negative_ratio >= 0.75 and avg_change < 0:
        return "Declining"
    elif avg_change >= 0.05:
        return "Slightly Improving"
    elif avg_change <= -0.05:
        return "Slightly Declining"
    else:
        return "Stable"


# A saved target's required GPA above this is "unusually high" —
# close enough to the 4.00 ceiling that it's worth flagging even
# though it may still be mathematically achievable.
HIGH_REQUIRED_GPA_THRESHOLD = 3.85

# A projected CGPA has to fall short of the target by more than
# this to count as "meaningfully" below it — avoids flagging a
# trivial, rounding-level near-miss.
TARGET_SHORTFALL_BUFFER = 0.05


def get_performance_alert(user_id):
    """
    Returns a single, prioritized Performance Alert for the
    dashboard, or None if there's nothing currently worth flagging.

    Two independent trigger groups feed into one alert:
      - Target-based (only evaluated if the student has SAVED a
        target CGPA plan — no saved target is not itself a
        problem, it just means this half can't be evaluated yet).
      - Trend-based (evaluated for any student with 2+ semesters,
        no target required).

    Priority order (first match wins — only one alert is ever
    returned, never a list, since a target-based concern is more
    directly actionable than a general trend observation):
      1. Projected CGPA meaningfully below a saved target.
      2. Required GPA for a saved target is unusually high.
      3. Volatile GPA trend.
      4. Declining / Slightly Declining GPA trend.
    """

    semesters = (
        db.session.query(Semester)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == user_id)
        .filter(Semester.semester_gpa != None)
        .order_by(Semester.academic_session, Semester.semester_no)
        .all()
    )

    gpa_history = [{"gpa": float(s.semester_gpa)} for s in semesters]

    # ---- Target-based checks ----
    target_plan = TargetCGPA.query.filter_by(user_id=user_id).first()

    if target_plan and target_plan.target_cgpa and target_plan.remaining_credits:

        if gpa_history:
            cgpa_result = calculate_cgpa_credits(user_id)
            latest_gpa = gpa_history[-1]["gpa"]

            projected = project_cgpa(
                cgpa_result["cgpa"],
                cgpa_result["credits"],
                target_plan.remaining_credits,
                latest_gpa
            )

            if projected < target_plan.target_cgpa - TARGET_SHORTFALL_BUFFER:
                return {
                    "type": "target_below",
                    "message": (
                        f"Based on your recent performance, you may fall short of your "
                        f"target CGPA of {target_plan.target_cgpa:.2f}. Consider reviewing "
                        f"your study plan or adjusting your target."
                    )
                }

        if (
            target_plan.required_gpa
            and target_plan.required_gpa > HIGH_REQUIRED_GPA_THRESHOLD
        ):
            return {
                "type": "required_high",
                "message": (
                    f"Reaching your target CGPA now requires an average GPA of "
                    f"{target_plan.required_gpa:.2f} in your remaining credits — close to "
                    f"the maximum possible. This target may be worth revisiting."
                )
            }

    # ---- Trend-based checks ----
    trend = detect_trend(gpa_history)

    if trend == "Volatile":
        return {
            "type": "volatile",
            "message": (
                "Your GPA has been fluctuating significantly between semesters. "
                "Consistent performance across semesters can help stabilize your CGPA trajectory."
            )
        }

    if trend in ("Declining", "Slightly Declining"):
        return {
            "type": "declining",
            "message": (
                "Your recent GPA shows a declining pattern. Maintaining or improving your "
                "upcoming semester results could help prevent further CGPA decline."
            )
        }

    return None


def determine_feasibility(current_cgpa, target_cgpa, remaining_sems_credits, trend, required_gpa):
    """
    Moved here from routes/analysis.py so the Target CGPA Simulator
    and the Dashboard Report (services/report_services.py) share one
    feasibility rule instead of two copies drifting apart.
    """
    total_remaining_credits = sum(remaining_sems_credits)

    if total_remaining_credits == 0:
        return "Impossible" if current_cgpa < target_cgpa else "Achieved"

    if required_gpa > 4.0:
        return "Impossible"

    #adjust feasibiltiy based on trend
    trend_boost = {
        "Improving": 0.20,
        "Slightly Improving": 0.10,
        "Stable": 0.0,
        "Volatile": -0.05,
        "Slightly Declining": -0.10,
        "Declining": -0.20,
    }.get(trend, 0)

    #base tolerance is 0.25 — meaning if the required GPA is within 0.25 of current CGPA, it's considered Achievable.
    adjusted_threshold = 0.25 + trend_boost
    cgpa_gap = required_gpa - current_cgpa

    if cgpa_gap <= 0:#already exceed target
        return "Achievable"
    elif cgpa_gap <= adjusted_threshold:#small gap
        return "Achievable"
    elif cgpa_gap <= adjusted_threshold + 0.20: #medium gap
        return "Challenging"
    else:
        return "Very Challenging" #large gap
