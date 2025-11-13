import google.generativeai as genai
import os

# Load your API key
GEMINI_API_KEY = "AIzaSyDWIke_yHhzUW2P6kJPCjd5YOpf_RnMDOQ"

genai.configure(api_key=GEMINI_API_KEY)

# Recommended fast model
MODEL = genai.GenerativeModel("gemini-1.5-flash")
