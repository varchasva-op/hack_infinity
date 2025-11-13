import google.generativeai as genai
import json
import re

genai.configure(api_key="AIzaSyDWIke_yHhzUW2P6kJPCjd5YOpf_RnMDOQ")

MODEL = "gemini-2.5-flash"


def clean_json(text):
    """Extract strict JSON from Gemini output."""
    # Remove markdown ```
    text = text.replace("```json", "").replace("```", "").strip()

    # Find JSON array
    match = re.search(r"\[.*\]", text, re.DOTALL)
    if match:
        return match.group(0)
    return text  # fallback


def generate_flashcards_from_text(text, n_cards=5):
    prompt = f"""
Generate {n_cards} flashcards from the text.
Format STRICT JSON like this:

[
  {{"question": "...", "answer": "..."}}
]

TEXT:
{text[:4000]}
"""

    try:
        model = genai.GenerativeModel(MODEL)
        resp = model.generate_content(prompt)
        cleaned = clean_json(resp.text)

        cards = json.loads(cleaned)
        return cards

    except Exception as e:
        return [{"question": "Error", "answer": str(e)}]
