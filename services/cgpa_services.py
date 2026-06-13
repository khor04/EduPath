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

    total_registered_credits = Decimal("0")
    earned_credits = Decimal("0")
    total_points = Decimal("0")

    for c in courses:

        credit = Decimal(str(c.credit_hour or 0))
        gp = Decimal(str(c.grade_point or 0))

        total_registered_credits += credit
        total_points += gp

        if c.grade not in FAIL_GRADES:
            earned_credits += credit

    if total_registered_credits == 0:
        return {
            "cgpa": 0.0,
            "credits": 0
        }

    cgpa = total_points / total_registered_credits
    cgpa_rounded = float(
        cgpa.quantize(
            Decimal("0.00"),
            rounding=ROUND_HALF_UP
        )
    )

    return {
        "cgpa": cgpa_rounded,
        "credits": int(earned_credits)
    }