from flask import Blueprint, request, jsonify, url_for
from flask_login import login_required, current_user

from services.chat_services import build_chat_context, get_deep_link_module
from services.gemini_service import generate_chat_response

chat_bp = Blueprint("chat", __name__)

# History is capped here -- not just trusted from the client -- so a
# long-running conversation can't grow the prompt (and cost) unbounded.
MAX_HISTORY_TURNS = 10

MODULE_ENDPOINTS = {
    "analysis": ("analysis.analysis", "View Academic Analysis"),
    "career": ("career.career", "View Career Recommendations"),
    "benchmark": ("benchmark.benchmark", "View Peer Benchmarking"),
}

NO_TRANSCRIPT_CONTEXT = (
    "This student hasn't uploaded a transcript yet, so no personal academic data "
    "is available. You can still answer general academic questions, but say so if "
    "asked about their own progress."
)


@chat_bp.route("/api/chat", methods=["POST"])
@login_required
def chat():
    data = request.get_json(silent=True) or {}

    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"success": False, "message": "Message is required."}), 400

    history = (data.get("history") or [])[-MAX_HISTORY_TURNS:]

    # current_user.user_id only -- any "user_id" the client might send
    # is never read. A question is always answered using the
    # authenticated user's own data, never a client-supplied identity.
    context = build_chat_context(current_user.user_id)
    context_text = context["summary_text"] if context["has_data"] else NO_TRANSCRIPT_CONTEXT

    try:
        answer = generate_chat_response(message, history, context_text)
    except Exception as e:
        print("EduPath AI chat error:", type(e).__name__, ":", e)
        return jsonify({
            "success": False,
            "message": "The assistant is temporarily unavailable. Please try again shortly."
        }), 503

    link = None
    module_key = get_deep_link_module(message)
    if module_key:
        endpoint, label = MODULE_ENDPOINTS[module_key]
        link = {"url": url_for(endpoint), "label": label}

    return jsonify({"success": True, "response": answer, "link": link})


@chat_bp.route("/api/chat/suggestions")
@login_required
def chat_suggestions():
    """
    Starter questions shown when the chat widget first opens, tailored
    to what the student's data actually contains -- e.g. only suggest
    a target-CGPA question if they've saved a target plan. Reuses the
    has_target/top_career_title build_chat_context() already computes
    as a byproduct of the summary, rather than recomputing them.
    """
    context = build_chat_context(current_user.user_id)

    if not context["has_data"]:
        return jsonify({"suggestions": [
            "What is the difference between GPA and CGPA?",
            "What is the Pomodoro technique?",
            "How can I take better lecture notes?",
        ]})

    suggestions = []
    suggestions.append(
        "Am I on track to reach my target CGPA?" if context["has_target"]
        else "How can I improve my CGPA?"
    )
    suggestions.append("Why did my CGPA change this semester?")
    if context["top_career_title"]:
        suggestions.append(f"Why was {context['top_career_title']} recommended for me?")
    suggestions.append("How should I study more effectively?")

    return jsonify({"suggestions": suggestions[:4]})
