# agents/chat_agent.py
import google.generativeai as genai
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

genai.configure(api_key="AIzaSyDWIke_yHhzUW2P6kJPCjd5YOpf_RnMDOQ")

MODEL = "gemini-2.5-flash"

CHUNKS = []
EMBEDDINGS = []


# ------------------------
# SIMPLE EMBEDDING
# ------------------------
def simple_embed(text):
    vec = np.array([ord(c) for c in text[:300]])
    return np.array([vec.mean()]) if len(vec) else np.zeros(1)


# ------------------------
# LOAD CHUNKS FROM NOTES
# ------------------------
def load_chunks(text):
    global CHUNKS, EMBEDDINGS

    if not text or text.strip() == "":
        CHUNKS = []
        EMBEDDINGS = []
        return

    CHUNKS = text.split("\n\n")[:50]
    CHUNKS = [c.strip() for c in CHUNKS if len(c.strip()) > 30]  # remove garbage chunks

    EMBEDDINGS = [simple_embed(c) for c in CHUNKS]


# ------------------------
# MAIN QA FUNCTION
# ------------------------
def answer_question(query):
    model = genai.GenerativeModel(MODEL)

    # CASE 1: No PDF uploaded → full Gemini answer
    if not CHUNKS:
        resp = model.generate_content(
            f"Explain this clearly and in simple terms:\n\n{query}"
        )
        return resp.text.strip()

    # CASE 2: Use RAG (find most relevant chunk)
    q_embed = simple_embed(query)
    sims = [cosine_similarity([q_embed], [e])[0][0] for e in EMBEDDINGS]

    best_index = int(np.argmax(sims))
    context = CHUNKS[best_index][:800]

    prompt = f"""
You are an expert tutor. Use the following study note to answer the question.

STUDY NOTE:
{context}

QUESTION:
{query}

Give a clear, beginner-friendly answer. 
If the note is insufficient, add extra explanation.
"""

    resp = model.generate_content(prompt)
    return resp.text.strip()
