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

def calculate_cgpa_credits(user_id):
    
    courses = (
        db.session.query(Course)
        .join(Semester)
        .join(Transcript)
        .filter(Transcript.user_id == user_id)
        .all()
    )

    # Group courses by course code to handle retakes
    courses_by_code = {}
    for c in courses:
        code = c.course_code.strip().upper()
        courses_by_code.setdefault(code, []).append(c)

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