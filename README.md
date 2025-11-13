# 🤖 Hack Infinity – AI Study Assistant

A **multi-agent AI platform** built to simplify student learning through automation and personalization.

## 🧩 Features
- 📄 Reads and understands uploaded study PDFs
- 🎴 Auto-generates Flashcards for quick revision
- 📝 Adaptive Quiz Generator
- 📅 Smart Revision Planner
- 💬 AI Chat Agent (RAG-powered) for contextual Q&A
- 💾 Auto-saving of all generated data (JSON format)
- 🌐 Streamlit-based responsive web UI

## 🧰 Tech Stack
**Frontend:** Streamlit  
**Backend:** Python (Multi-Agent Architecture)  
**AI Models:** SentenceTransformer (MiniLM-L6-v2)  
**Storage:** JSON / Local Outputs  

## 🛠️ Run Locally
```bash
git clone https://github.com/<your-username>/HACK_INFINITY.git
cd HACK_INFINITY
pip install -r requirements.txt
streamlit run ui/app.py
