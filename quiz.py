import google.generativeai as genai
import json
import re

genai.configure(api_key="YOUR_API_KEY")

MODEL = "models/gemini-2.5-flash"   # Confirmed working from your test

def clean_json(text):
    """Remove markdown fences, stray characters, fix malformed JSON."""
    text = text.strip()

    # Remove ```json or ``` blocks
    text = re.sub(r"```json|```", "", text).strip()

    # Sometimes Gemini wraps JSON inside text — extract part between [ ... ]
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        text = match.group(0)

    return text


def generate_quiz_from_text(text, n_questions=5):
    prompt = f"""
Generate {n_questions} high-quality MCQ questions from the text below.

Return ONLY valid JSON in this format:

[
  {{
   "question": "string",
   "options": ["A","B","C","D"],
   "answer": "A"
  }}
]

TEXT:
{text}
"""

    try:
        model = genai.GenerativeModel(MODEL)
        response = model.generate_content(prompt)

        raw = response.text
        cleaned = clean_json(raw)

        quiz = json.loads(cleaned)   # <-- Fixed JSON parsing
        return quiz

    except Exception as e:
        return [{
            "question": "Error generating quiz",
            "options": [],
            "answer": str(e)
        }]
