from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.transcript import Transcript
from models.semester import Semester
from models.course import Course
from models.target_cgpa import TargetCGPA
from extensions import db
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from dotenv import load_dotenv
from services.gemini_service import generate_academic_plan
from services.cgpa_services import calculate_cgpa_credits, simulate_cgpa

analysis_bp = Blueprint("analysis", __name__)

load_dotenv()

@analysis_bp.route("/analysis")
@login_required
def analysis():

    semesters = (
        Semester.query
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == current_user.user_id)
        .all()
    )

    semesters = sorted(
        semesters,
        key=lambda s:(
            s.academic_session,
            s.semester_no
        )
    )

    # GPA trend chart data
    gpa_labels = [f"Sem {s.semester_no} ({s.academic_session})"
                  for s in semesters]
    gpa_values = [
    float(sem.semester_gpa or 0)
    for sem in semesters
    ]

    # Latest CGPA and completed credits
    cgpa_result = calculate_cgpa_credits(current_user.user_id)

    current_cgpa = cgpa_result["cgpa"]
    current_credits = cgpa_result["credits"]


    semester_history = []

    for sem in semesters:
        semester_history.append({
            "semester" : sem.semester_no,
            "gpa" : float(sem.semester_gpa or 0),
        })

    return render_template(
        "analysis.html",
        active_page="analysis",
        semesters=semesters,   
        gpa_labels=gpa_labels,
        gpa_values=gpa_values,
        current_cgpa=current_cgpa,
        current_credits=current_credits,
        semester_history=json.dumps(semester_history)
    )

@analysis_bp.route("/save-target-cgpa", methods=["POST"])
@login_required
def save_target_cgpa():

    data = request.get_json()

    if not data:
        return jsonify({
            "success": False,
            "message": "No target CGPA data received."
        })

    target_cgpa = float(data.get("target_cgpa") or 0)
    required_gpa = float(data.get("required_gpa") or 0)
    remaining_credits = int(data.get("remaining_credits") or 0)
    # Validation
    if target_cgpa <= 0:
        return jsonify({
            "success": False,
            "message": "Invalid target CGPA."
        })

    if remaining_credits <= 0:
        return jsonify({
            "success": False,
            "message": "Remaining credits must be greater than 0."
        })

    if required_gpa > 4.005:
        return jsonify({
            "success": False,
            "message": "Target CGPA plan cannot be saved because the goal is not achievable."
        })

    try:

        # ================================
        # UPDATE EXISTING TARGET PLAN
        # OR CREATE NEW TARGET PLAN
        # ================================
        existing_target = TargetCGPA.query.filter_by(
            user_id=current_user.user_id
        ).first()

        if existing_target:

            existing_target.target_cgpa = target_cgpa
            existing_target.required_gpa = round(required_gpa, 2)
            existing_target.remaining_credits = remaining_credits
            existing_target.updated_at = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))

        else:

            target = TargetCGPA(
                user_id=current_user.user_id,
                target_cgpa=target_cgpa,
                required_gpa=round(required_gpa, 2),
                remaining_credits=remaining_credits,
                updated_at=datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))
            )

            db.session.add(target)

        db.session.commit()

        return jsonify({
            "success": True,
            "message": "Target CGPA plan saved successfully."
        })

    except Exception as e:

        db.session.rollback()

        return jsonify({
            "success": False,
            "message": f"Failed to save target CGPA plan: {str(e)}"
        })


@analysis_bp.route("/api/my-courses")
@login_required
def my_courses():

    courses = (
        db.session.query(Course)
        .join(Semester, Course.semester_id == Semester.semester_id)
        .join(Transcript, Semester.transcript_id == Transcript.transcript_id)
        .filter(Transcript.user_id == current_user.user_id)
        .order_by(
            Semester.academic_session,
            Semester.semester_no,
            Course.course_code
        )
        .all()
    )

    return jsonify([
        {
            "course_id": c.course_id,
            "course_code": c.course_code,
            "course_name": c.course_name,
            "credit_hour": c.credit_hour,
            "grade": c.grade
        }
        for c in courses
    ])


@analysis_bp.route("/api/simulate-cgpa", methods=["POST"])
@login_required
def simulate_cgpa_route():

    data = request.get_json()

    if not data or "entries" not in data:
        return jsonify({
            "success": False,
            "message": "No simulation data received."
        })

    entries = data["entries"]

    if not entries:
        return jsonify({
            "success": False,
            "message": "Add at least one course to simulate."
        })

    try:
        current = calculate_cgpa_credits(current_user.user_id)
        projected = simulate_cgpa(current_user.user_id, entries)

        return jsonify({
            "success": True,
            "current_cgpa": current["cgpa"],
            "projected_cgpa": projected["cgpa"],
            "change": round(projected["cgpa"] - current["cgpa"], 2)
        })

    except ValueError as e:
        return jsonify({
            "success": False,
            "message": str(e)
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"Failed to simulate CGPA: {str(e)}"
        })


#helper function
def detect_trend(history):
    if len(history) < 2:
        return "Stable"

    gpas = [h["gpa"] for h in history] #eg:gpas = [3.53,3.81,4.0,4.0]
    deltas = [gpas[i+1] - gpas[i] for i in range(len(gpas)-1)] #detect semester-to-semester changes(represent improvement or decline) eg:[0.28,0.19,0]
    avg_change = sum(deltas) / len(deltas) #eg: 0.16

    #count positive & negative changes
    #ignore changes=0, because unchanged semester treated as stable
    positive = sum(1 for d in deltas if d > 0) #2
    negative = sum(1 for d in deltas if d < 0) #0
    non_zero = positive + negative #2

    #identify substantial fluctuations between semesters, distinguish normal academic variation from significant performance instability
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
    
    #0.75 defined to consider at least 75% of semester changes are positive
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
    
def determine_feasibility(current_cgpa, target_cgpa, remaining_sems_credits, trend, required_gpa):
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


@analysis_bp.route("/generate-ai-plan", methods=["POST"])
@login_required
def generate_ai_plan():

    try:

        data = request.get_json()
        history = data.get("history", [])
        remaining_semesters = data.get("remainingSemesters", [])
        target_cgpa = data.get("targetCGPA")
        required_gpa = float(data.get("requiredGPA") or 0)
        current_cgpa = data.get("currentCGPA")
        current_credits = data.get("currentCredits")

        trend = detect_trend(history)
        remaining_sems_credits = [s.get("credits", 0) for s in remaining_semesters]
        feasibility = determine_feasibility(
            current_cgpa=float(current_cgpa),
            target_cgpa=float(target_cgpa),
            remaining_sems_credits=remaining_sems_credits,
            trend=trend,
            required_gpa=required_gpa

        )

        trend_meanings = {
            "Improving":          "GPA has been consistently rising across most semesters.",
            "Slightly Improving": "GPA shows a small but consistent upward movement.",
            "Stable":             "GPA has remained relatively consistent with no clear direction.",
            "Volatile":           "GPA fluctuates significantly up and down between semesters.",
            "Slightly Declining": "GPA shows a small but consistent downward movement.",
            "Declining":          "GPA has been consistently dropping across most semesters.",
        }

        prompt = """You are an academic advisor AI helping a Malaysian university student
plan their remaining semesters realistically.

Student past performance:
"""

        for sem in history:
            prompt += (
                f"\n- Sem {sem.get('semester', '-')}: "
                f"{sem.get('gpa', 0)} ({sem.get('credits', 0)} credits)"
            )

        prompt += f"""

System Detected Trend: {trend}
Trend Meaning: {trend_meanings.get(trend, "")}
System Calculated Feasibility: {feasibility}

Current CGPA: {current_cgpa}
Current Credits: {current_credits}

Target CGPA: {target_cgpa}
Required average GPA for remaining credits: {required_gpa}

Remaining semesters:
"""

        for sem in remaining_semesters:
            prompt += (
                f"\n- Semester {sem.get('sem', '-')}: "
                f"{sem.get('credits', 0)}"
            )

        prompt += """

Rules:
1. Distribute GPA conservatively.
2. Distribute GPA targets according to semester credit weight and overall CGPA impact.
3. Avoid assigning disproportionately high GPA targets to lower-credit semesters solely to compensate for higher-credit semesters.
4. Maintain balanced and realistic GPA targets across all semesters.
5. Keep GPA targets realistic and achievable based on the student's trend.
6. No GPA target may exceed 4.00.
7. Do not generate trend or feasibility values. They are provided by the system.
8. The weighted average GPA across all remaining semesters must be approximately equal to the required GPA.

Advice rules — follow STRICTLY:
9. Write advice as EXACTLY 4 bullet points, each starting with "•".
10. Each bullet point must be ONE sentence only, no sub-points.
11. Follow this exact structure for the 4 points:
    • Point 1: State the student's trend and what it means for their goal.
    • Point 2: Mention the heaviest semester and why it matters most for CGPA.
    • Point 3: Give one specific study/performance tip relevant to their situation.
    • Point 4: End with an encouraging but realistic closing statement about feasibility.
12. Do NOT include calculations, raw numbers outside context, or extra paragraphs.

Return JSON only:

{
  "trend": "",
  "feasibility": "",
  "semesters": [
    {
      "sem": 0,
      "credits": 0,
      "minimumGPARequired": 0
    }
  ],
  "advice": ""
}
"""

        result = generate_academic_plan(prompt)
        result["trend"] = trend
        result["feasibility"] = feasibility

        return jsonify(result)

    except Exception as e:

        return jsonify({
            "success": False,
            "message": str(e)
        }), 500