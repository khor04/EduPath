import json
import google.generativeai as genai
import os

def generate_academic_plan(prompt):
    genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")

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