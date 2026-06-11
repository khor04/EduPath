from models.course import Course
from models.semester import Semester
from models.transcript import Transcript
from extensions import db

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

    total_registered_credits = 0
    earned_credits = 0
    total_points = 0

    for c in courses:

        credit = float(c.credit_hour or 0)
        gp = float(c.grade_point or 0)

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

    return {
        "cgpa": round(cgpa, 2),
        "credits": earned_credits
    }