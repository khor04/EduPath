"""
Grade Tracker: current-semester grade projection.

Everything above the "database" divider is pure -- plain values in, plain
values out, no Flask/DB -- so the marks arithmetic can be tested directly.
All marks arithmetic uses Decimal so a boundary case (a mark of exactly
75.00) is never decided by float noise.

Grade boundaries and grade points come from services/cgpa_services.py,
the app's single source for the official UM scale.
"""

from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_DOWN, ROUND_HALF_UP

from models.tracked_course import TrackedCourse
from services.cgpa_services import (
    FAIL_GRADES,
    GRADE_MIN_MARK,
    GRADE_POINTS,
    calculate_cgpa_credits,
    simulate_cgpa,
)

HUNDRED = Decimal(100)
MIN_MARK = dict(GRADE_MIN_MARK)

# Grades a student can aim for: passing grades only.
TARGET_GRADES = [g for g, _ in GRADE_MIN_MARK if g not in FAIL_GRADES]
DEFAULT_TARGET_GRADE = "A-"

RESULT_FORMAT_HINT = "Use a mark like 8/10, 75 or 68%, or a grade like A-."


# --------------------------------------------------------------------
# Pure logic
# --------------------------------------------------------------------

def grade_for_mark(mark):
    """
    Grade for a mark out of 100. The mark is used as-is: UM's bands are
    X.00-X.99, so 74.99 is a B+ and is never rounded up to an A-.
    """
    for grade, minimum in GRADE_MIN_MARK:
        if mark >= minimum:
            return grade
    return "F"


def grade_scale():
    """
    The grade table shown on the page, derived from GRADE_MIN_MARK,
    GRADE_POINTS and FAIL_GRADES -- never typed out separately -- so it
    can't disagree with the boundaries the calculations use. A band runs
    from its minimum to 0.01 below the next band's minimum (75.00-79.99),
    matching the X.00-X.99 form of UM's published scale.
    """

    rows = []
    upper = Decimal("100.00")

    for grade, minimum in GRADE_MIN_MARK:
        low = Decimal(minimum).quantize(Decimal("0.01"))
        rows.append({
            "grade": grade,
            "marks": f"{low}–{upper}",
            "grade_point": f"{GRADE_POINTS[grade]:.2f}",
            "result": "Fail" if grade in FAIL_GRADES else "Pass",
        })
        upper = low - Decimal("0.01")

    return rows


def _decimal(text):
    value = Decimal(text)
    if not value.is_finite():
        raise InvalidOperation
    return value


def parse_result(text):
    """
    Turns what the student typed into a percentage out of 100.

      "8/10" -> 80      "75" / "68%" -> 75 / 68      "A-" -> 75

    A letter grade is only a band, not a mark, so it is counted at the
    BOTTOM of its band (A- = 75, the lowest mark that earns an A-). That
    is the conservative choice: if the tracker says a target needs
    76.8%, the student really does need it -- they can't end up short
    because the estimate was optimistic. `estimated` flags this so the
    UI can say so.

    Returns None for blank input (result not received yet), otherwise
    {"percent": Decimal, "estimated": bool}. Raises ValueError with a
    user-facing message on anything invalid.
    """

    if text is None:
        return None

    s = str(text).strip().replace(" ", "")

    if not s:
        return None

    grade = s.upper()
    if grade in MIN_MARK:
        return {"percent": Decimal(MIN_MARK[grade]), "estimated": True}

    try:
        if "/" in s:
            score_text, max_text = s.split("/", 1)
            score, maximum = _decimal(score_text), _decimal(max_text)

            if maximum <= 0:
                raise ValueError("The total marks must be greater than 0.")
            if score < 0 or score > maximum:
                raise ValueError(
                    f"A mark of {score_text} is not possible out of {max_text}."
                )

            percent = score / maximum * HUNDRED
        else:
            percent = _decimal(s[:-1] if s.endswith("%") else s)

            if percent < 0 or percent > 100:
                raise ValueError("A percentage must be between 0 and 100.")

    except InvalidOperation:
        raise ValueError(f"Couldn't read \"{text}\" as a result. {RESULT_FORMAT_HINT}")

    return {"percent": percent, "estimated": False}


def _to_float(value, places=2, rounding=ROUND_DOWN):
    return float(value.quantize(Decimal(1).scaleb(-places), rounding=rounding))


def summarize_course(assessments, target_grade):
    """
    assessments: list of {"name", "weight", "result"} (result may be
    None/blank for "not received yet"). Results were validated when
    saved, so parse_result() is not expected to fail here.

    "Remaining" is defined as 100% minus the weight already marked -- not
    the weights of the assessments still listed as blank -- so "what I
    need" works even if the student hasn't entered the final exam's
    weight (or forgot an assessment).
    """

    graded_weight = Decimal(0)
    earned = Decimal(0)
    declared_weight = Decimal(0)
    pending = []
    items = []

    for a in assessments:
        weight = Decimal(str(a["weight"]))
        declared_weight += weight
        parsed = parse_result(a.get("result"))

        item = {
            "name": a["name"],
            "weight": _to_float(weight, 2),
            "result": a.get("result"),
            "estimated": False,
            "counted_percent": None,
        }

        if parsed is None:
            pending.append(a["name"])
        else:
            graded_weight += weight
            earned += weight * parsed["percent"] / HUNDRED
            item["estimated"] = parsed["estimated"]
            item["counted_percent"] = _to_float(parsed["percent"], 2)

        items.append(item)

    remaining = max(Decimal(0), HUNDRED - graded_weight)
    has_estimate = any(i["estimated"] for i in items)

    current = earned / graded_weight * HUNDRED if graded_weight > 0 else None
    projected_grade = grade_for_mark(current) if current is not None else None

    # ---- what's needed for the target ----
    need = None
    if target_grade in MIN_MARK:
        minimum = Decimal(MIN_MARK[target_grade])

        if earned >= minimum:
            need = {"status": "secured"}
        elif remaining == 0:
            need = {"status": "missed", "final_grade": grade_for_mark(earned)}
        else:
            percent = (minimum - earned) / remaining * HUNDRED
            if percent > 100:
                need = {
                    "status": "unreachable",
                    "best_grade": grade_for_mark(earned + remaining),
                }
            else:
                # Rounded UP: 76.831 -> 76.84, never 76.83, so the figure
                # shown is always enough.
                need = {
                    "status": "reachable",
                    "percent": _to_float(percent, 2, ROUND_CEILING),
                }

    return {
        "items": items,
        "target_grade": target_grade,
        "completed_weight": _to_float(graded_weight, 2),
        "remaining_weight": _to_float(remaining, 2),
        "declared_weight": _to_float(declared_weight, 2),
        "pending_names": pending,
        "is_complete": remaining == 0,
        "has_estimate": has_estimate,
        # Truncated, not rounded, so the displayed figure can never sit
        # on the wrong side of a boundary from the grade next to it.
        "current_performance": _to_float(current, 2) if current is not None else None,
        "projected_grade": projected_grade,
        "need": need,
    }


# --------------------------------------------------------------------
# Input validation (shared by the create and edit routes)
# --------------------------------------------------------------------

def validate_course_fields(data, partial=False):
    """Cleaned course fields from a request body; ValueError if invalid."""

    cleaned = {}

    if "course_code" in data or not partial:
        code = (data.get("course_code") or "").strip().upper()
        if not code:
            raise ValueError("Course code is required.")
        if len(code) > 20:
            raise ValueError("Course code is too long (20 characters max).")
        cleaned["course_code"] = code

    if "course_name" in data or not partial:
        name = (data.get("course_name") or "").strip()
        if len(name) > 200:
            raise ValueError("Course name is too long (200 characters max).")
        cleaned["course_name"] = name or None

    if "credit_hour" in data or not partial:
        try:
            credits = float(data.get("credit_hour"))
        except (TypeError, ValueError):
            raise ValueError("Credit hours must be a number.")
        if not 0 < credits <= 20:
            raise ValueError("Credit hours must be between 0 and 20.")
        cleaned["credit_hour"] = credits

    if "target_grade" in data or not partial:
        grade = (data.get("target_grade") or DEFAULT_TARGET_GRADE).strip().upper()
        if grade not in TARGET_GRADES:
            raise ValueError("Target grade must be a passing grade (A+ to C).")
        cleaned["target_grade"] = grade

    return cleaned


def validate_assessment_fields(data, partial=False):
    """Cleaned assessment fields from a request body; ValueError if invalid."""

    cleaned = {}

    if "name" in data or not partial:
        name = (data.get("name") or "").strip()
        if not name:
            raise ValueError("Assessment name is required.")
        if len(name) > 100:
            raise ValueError("Assessment name is too long (100 characters max).")
        cleaned["name"] = name

    if "weight" in data or not partial:
        try:
            weight = float(data.get("weight"))
        except (TypeError, ValueError):
            raise ValueError("Weight must be a number.")
        if not 0 < weight <= 100:
            raise ValueError("Weight must be between 0 and 100.")
        cleaned["weight"] = weight

    if "result" in data:
        raw = data.get("result")
        parse_result(raw)  # raises ValueError if unreadable
        text = str(raw).strip() if raw is not None else ""
        if len(text) > 20:
            raise ValueError("Result is too long.")
        cleaned["result"] = text or None

    return cleaned


# --------------------------------------------------------------------
# Database
# --------------------------------------------------------------------

def _course_payload(course):
    summary = summarize_course(
        [
            {"name": a.name, "weight": a.weight, "result": a.result}
            for a in course.assessments
        ],
        course.target_grade,
    )
    summary["assessments"] = [
        {**item, "assessment_id": a.assessment_id}
        for item, a in zip(summary.pop("items"), course.assessments)
    ]
    summary.update(
        tracked_course_id=course.tracked_course_id,
        course_code=course.course_code,
        course_name=course.course_name,
        credit_hour=course.credit_hour,
    )
    return summary


def build_tracker_state(user_id):
    """
    Everything the Grade Tracker page shows: each course's summary, and
    the semester outlook -- projected semester GPA and CGPA if every
    course finishes at its projected grade.

    The CGPA figure goes through simulate_cgpa(), the same code the
    Per-Course CGPA Simulator uses, so a course the student is retaking
    is scored by the real best-attempt rule.
    """

    courses = (
        TrackedCourse.query.filter_by(user_id=user_id)
        .order_by(TrackedCourse.tracked_course_id)
        .all()
    )

    payloads = [_course_payload(c) for c in courses]

    entries = [
        {
            "type": "current",
            "course_code": p["course_code"],
            "credits": p["credit_hour"],
            "grade": p["projected_grade"],
        }
        for p in payloads
        if p["projected_grade"] is not None
    ]

    outlook = None
    if entries:
        total_credits = sum(Decimal(str(e["credits"])) for e in entries)
        total_points = sum(
            Decimal(str(GRADE_POINTS[e["grade"]])) * Decimal(str(e["credits"]))
            for e in entries
        )
        semester_gpa = (total_points / total_credits).quantize(
            Decimal("0.00"), rounding=ROUND_HALF_UP
        )

        current = calculate_cgpa_credits(user_id)
        projected = simulate_cgpa(user_id, entries)

        outlook = {
            "semester_gpa": float(semester_gpa),
            "projected_cgpa": projected["cgpa"],
            "current_cgpa": current["cgpa"] if current["credits"] > 0 else None,
            "courses_included": len(entries),
            "courses_excluded": len(payloads) - len(entries),
        }

    return {"courses": payloads, "outlook": outlook, "target_grades": TARGET_GRADES}
