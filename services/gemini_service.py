import json
import time
import google.generativeai as genai
import os
from google.api_core.exceptions import ResourceExhausted

from services.career_services import MODEL_NAME, RATE_LIMIT_BACKOFF_SECONDS

def generate_academic_plan(prompt):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        model = genai.GenerativeModel("gemini-3.6-flash")

        print("Using model:", model.model_name)

        response = model.generate_content(prompt)

        print("Response received")

        text = response.text.strip()

        if "```" in text:
            text = text.replace("```json", "").replace("```", "").strip()

        return json.loads(text)

    except Exception as e:
        print("Gemini Error:", str(e))

        return {
            "trend": "Unknown",
            "feasibility": "Error",
            "semesters": [],
            "advice": str(e)
        }


CHAT_SYSTEM_PROMPT = """You are EduPath AI, an academic assistant built into EduPath, \
a system that helps students track their academic performance, predict their CGPA, \
benchmark against peers, and explore career recommendations.

You can answer two kinds of questions:
1. Questions about the student's own academic progress -- answer these using ONLY \
the "Student Academic Context" provided with each message. Never invent, guess, or \
estimate a CGPA, grade, GPA, career match percentage, or any other student-specific \
fact that is not explicitly present in that context. If the context doesn't contain \
what's needed to answer, say so plainly rather than guessing.
2. General academic questions (study techniques, course concepts, exam preparation, \
career fields in general, etc.) -- answer these from your own knowledge, the same \
way any knowledgeable academic assistant would.

Many questions call for both at once -- e.g. a student asking how to improve in a \
course they're struggling with should get study advice grounded in their actual \
grade for that course.

The "Student Academic Context" given with each message is the ONLY authoritative \
source for facts about this student. The conversation history is for maintaining \
conversational flow only -- if anything in it claims a fact about the student that \
isn't backed by the current context (or contradicts it), trust the context, not the \
history.

If a question is unrelated to academics, courses, study strategies, or careers, \
politely redirect: mention you're mainly built to help with academic progress, \
courses, study strategies, benchmarking, and career recommendations, without being \
robotic about it.

Format answers for a small chat window, not a report:
- Keep it short -- a brief paragraph or two, not an essay.
- When giving multiple recommendations or steps, use a short numbered or bulleted \
list instead of cramming them into one dense paragraph.
- Use **bold** sparingly, only for genuinely important terms, not entire sentences.

Avoid overconfident or absolute language about academic outcomes. Never say a plan \
will "guarantee" a result, or that a student "will definitely" reach a grade or \
CGPA -- academic performance depends on many things this system can't see. Use \
appropriately hedged phrasing instead (e.g. "can help maintain," "is likely to \
improve your chances," "may help you reach").
"""


def generate_chat_response(message, history, context_text):
    """
    Free-form conversational reply for the EduPath AI chat widget --
    deliberately separate from generate_academic_plan(), which returns
    structured JSON for a different feature. Mirrors the same
    retry/backoff pattern as career_services._call_gemini() (not
    shared directly, since that function is coupled to JSON parsing
    this doesn't want).

    `context_text` is build_chat_context()'s summary_text (or a
    placeholder noting no transcript exists yet) -- per
    CHAT_SYSTEM_PROMPT, the only authoritative source for facts about
    the student. `history` is a list of {"role": "user"|"assistant",
    "text": "..."} prior turns, included for conversational flow only,
    never as a second source of truth.
    """
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=CHAT_SYSTEM_PROMPT)

    convo = []
    for turn in history:
        role = "user" if turn.get("role") == "user" else "model"
        text = (turn.get("text") or "").strip()
        if text:
            convo.append({"role": role, "parts": [text]})

    prompt = f"Student Academic Context:\n{context_text}\n\nStudent's question: {message}"

    response = None
    for attempt, delay in enumerate([0] + RATE_LIMIT_BACKOFF_SECONDS):
        if delay:
            time.sleep(delay)
        try:
            chat = model.start_chat(history=convo)
            response = chat.send_message(prompt)
            break
        except ResourceExhausted:
            if attempt == len(RATE_LIMIT_BACKOFF_SECONDS):
                raise
            continue

    return response.text.strip()