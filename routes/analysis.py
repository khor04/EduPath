from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models.transcript import Transcript
from models.semester import Semester
from models.target_cgpa import TargetCGPA
from extensions import db
from datetime import datetime
from zoneinfo import ZoneInfo
import json
from dotenv import load_dotenv
from services.gemini_service import generate_academic_plan
from services.cgpa_services import calculate_cgpa_credits

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
            "credits" : int(sem.semester_credits or 0)
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
    status = data.get("status", "")
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
            existing_target.status = status
            existing_target.updated_at = datetime.now(ZoneInfo("Asia/Kuala_Lumpur"))

        else:

            target = TargetCGPA(
                user_id=current_user.user_id,
                target_cgpa=target_cgpa,
                required_gpa=round(required_gpa, 2),
                remaining_credits=remaining_credits,
                status=status,
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
    
#helper function
#identify trend based on first and last recent semester
def detect_trend(history):
    
    if len(history) < 2:
        return "Stable"

    change = history[-1]["gpa"] - history[0]["gpa"]

    if change >= 0.20:
        return "Improving"
    elif change <= -0.20:
        return "Declining"
    else:
        return "Stable"
    

def determine_feasibility(required_gpa, trend, latest_gpa):
    
    if required_gpa > 4.0:
        return "Impossible"

    gap = required_gpa - latest_gpa

    if gap <= 0.15:
        return "Achievable"

    elif trend == "Improving" and gap <= 0.30:
        return "Achievable"

    else:
        return "Challenging" 


#The system does not assume that higher-credit semesters are easier. Instead, it considers that higher-credit semesters have a greater influence on the final CGPA because they carry more weight in the CGPA calculation. Therefore, the GPA targets are distributed with consideration of credit weighting while still keeping the targets realistic and balanced.
#Higher-credit semesters contribute more weight to the final CGPA calculation. Therefore, the AI planner considers credit distribution when allocating GPA targets so that the plan reflects the relative impact of each semester on the student's overall CGPA.
@analysis_bp.route("/generate-ai-plan", methods=["POST"])
@login_required
def generate_ai_plan():

    try:

        data = request.get_json()
        history = data.get("history", [])
        remaining_semesters = data.get(
            "remainingSemesters",
            []
        )
        target_cgpa = data.get("targetCGPA")
        required_gpa = float(data.get("requiredGPA") or 0)
        current_cgpa = data.get("currentCGPA")
        current_credits = data.get("currentCredits")
        trend = detect_trend(history)
        latest_gpa = float(data.get("latestGPA") or 0)
        feasibility = determine_feasibility(required_gpa, trend, latest_gpa)

        prompt = """
You are an academic advisor AI helping a Malaysian university student
plan their remaining semesters realistically.

Student past performance:
"""

        for sem in history:

            prompt += (
                f"\n- Sem {sem['semester']}: "
                f"{sem['gpa']} ({sem['credits']} credits)"
            )

        prompt += f"""
System Detected Trend: {trend}

System Calculated Feasibility: {feasibility}

Current CGPA: {current_cgpa}
Current Credits: {current_credits}

Target CGPA: {target_cgpa}
Required average GPA for remaining credits: {required_gpa}
"""

        for sem in remaining_semesters:

            prompt += (
                f"\n- Sem {sem['sem']}: "
                f"{sem['credits']} credits"
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
  "advice":""
  
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
