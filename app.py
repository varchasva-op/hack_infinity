# ui/app.py
import streamlit as st
import os, sys, json, datetime, base64, hashlib, tempfile
import google.generativeai as genai

# ---------------------------
# Basic paths & environment
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))  # ui/
ROOT_DIR = os.path.dirname(BASE_DIR)                   # project root
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

OUTPUT_DIR = os.path.join(ROOT_DIR, "outputs")
PDF_DIR = os.path.join(ROOT_DIR, "uploads")
USERS_DIR = os.path.join(OUTPUT_DIR, "users")
for p in (OUTPUT_DIR, PDF_DIR, USERS_DIR):
    os.makedirs(p, exist_ok=True)

# ---------------------------
# UI CSS (kept your styles)
# ---------------------------
st.set_page_config(page_title="📘 Hack Infinity", layout="wide")
st.markdown("""
<style>
/* Your CSS (kept & cleaned) */
html, body, [class*="css"]  {
    font-family: 'Inter', sans-serif !important;
    background-color: #0d1117;
    color: #f0f6fc;
}
.block-container { padding-top: 1rem; padding-left:1rem; padding-right:1rem;}
.nav-tabs {display:flex; gap:10px; padding:15px 0; margin-bottom:25px;}
.nav-item {padding:10px 18px; border-radius:10px; background: rgba(255,255,255,0.06); border:1px solid rgba(255,255,255,0.1); cursor:pointer; transition:0.25s;}
.nav-item:hover {transform:translateY(-3px) scale(1.03); box-shadow:0px 0px 12px #00d2ff; border-color:#00d2ff;}
.nav-active {background: rgba(0,210,255,0.2); border:1px solid #00d2ff; box-shadow:0 0 14px #00d2ff; font-weight:700;}
.flashcard { background: rgba(255,255,255,0.05); padding:20px; border-radius:16px; margin-bottom:25px; border:1px solid rgba(255,255,255,0.15); box-shadow:0px 5px 18px rgba(0,0,0,0.5); transition: transform 0.25s, box-shadow 0.25s;}
.flashcard:hover { transform: translateY(-6px) scale(1.02); box-shadow:0 0 18px #00eaff; border-color:#00eaff;}
.flash-q { font-size:20px; font-weight:600; margin-bottom:6px; color:#7dd3fc; }
.flash-a { font-size:16px; line-height:1.5; color:#e2e8f0; }
.stButton>button { background: linear-gradient(90deg,#00d2ff,#3a7bd5); color:white; border-radius:10px; border:none; padding:10px 20px; transition:.25s; }
.stButton>button:hover { transform:scale(1.05); box-shadow:0 0 15px #00d2ff; }
.stTextInput>div>div>input { background-color: rgba(255,255,255,0.08) !important; color: white !important; border-radius: 8px !important; border:1px solid rgba(255,255,255,0.2) !important; }
.stTextInput>div>div>input:focus { border:1px solid #00d2ff !important; box-shadow:0 0 10px #00d2ff !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------
# Load Gemini API key (from Streamlit secrets)
# ---------------------------
GEMINI_KEY = st.secrets.get("GEMINI_API_KEY", None)
GEN_MODEL = "models/gemini-2.5-flash"  # change if you prefer other family

if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        gen_model = genai.GenerativeModel(GEN_MODEL)
        GEMINI_AVAILABLE = True
    except Exception as e:
        st.warning(f"Gemini init error: {e}")
        gen_model = None
        GEMINI_AVAILABLE = False
else:
    gen_model = None
    GEMINI_AVAILABLE = False
    st.warning("Gemini API key not found in secrets (GEMINI_API_KEY). Running with local fallbacks.")

# ---------------------------
# Helper: base64 loader for background
# ---------------------------
@st.cache_data
def get_image_as_base64(file_path):
    try:
        with open(file_path, "rb") as f:
            return base64.b64encode(f.read()).decode()
    except Exception:
        return None

# ---------------------------
# Agents import (safe)
# ---------------------------
AGENTS_AVAILABLE = True
try:
    from agents.reader import extract_text_from_pdf
    from agents.flashcard import generate_flashcards_from_text
    from agents.quiz import generate_quiz_from_text
    # chat_agent may provide a RAG pipeline; we'll prefer it if available.
    import agents.chat_agent as chat_agent_module
    AGENTS_CHAT_AVAILABLE = hasattr(chat_agent_module, "answer_question")
except Exception as e:
    AGENTS_AVAILABLE = False
    AGENTS_CHAT_AVAILABLE = False
    # provide safe fallbacks so UI still displays
    def extract_text_from_pdf(path):
        return ["(local fallback) Could not read PDF — agents.reader missing."]
    def generate_flashcards_from_text(text, n_cards=5):
        # very small offline fallback
        sents = [s for s in text.split(". ") if s.strip()]
        cards = []
        for i in range(min(n_cards, max(1, len(sents)//2))):
            q = sents[2*i][:80] if 2*i < len(sents) else f"Q{i+1}?"
            a = sents[2*i+1][:200] if 2*i+1 < len(sents) else "Answer hidden"
            cards.append({"question": q, "answer": a})
        return cards
    def generate_quiz_from_text(text, n_questions=5):
        return [{"question":"(fallback) No quiz generated","options":["A","B","C","D"],"answer":"A"}]

# ---------------------------
# Single answer_question wrapper
# ---------------------------
def local_gemini_answer(query, context=None, max_tokens=600):
    """Call Gemini model with prompt; returns text or fallback error."""
    if not GEMINI_AVAILABLE or gen_model is None:
        return "⚠️ Gemini not available — no API key or init failed."
    # build prompt with optional context
    prompt = f"Context:\n{context if context else 'No context.'}\n\nQuestion:\n{query}\n\nAnswer the question concisely and clearly."
    try:
        resp = gen_model.generate_content(prompt)
        # .text or resp.text depending on package version
        text = getattr(resp, "text", None) or (resp and resp.to_dict().get("candidates",[{}])[0].get("content")) or str(resp)
        return text
    except Exception as e:
        return f"⚠️ Gemini error: {e}"

def answer_question_wrapper(query, use_rag=True):
    """Prefer agents.chat_agent RAG if available, otherwise use Gemini or fallback."""
    # If agents chat implementation exists, try using it.
    if AGENTS_CHAT_AVAILABLE:
        try:
            # chat_agent may have load_chunks/build_embeddings etc. If user uploaded text set in session,
            # call chat_agent.load_chunks(st.session_state['text']) before asking.
            if "text" in st.session_state and st.session_state["text"].strip():
                try:
                    # load chunks into agent's memory if function exists
                    if hasattr(chat_agent_module, "load_chunks"):
                        chat_agent_module.load_chunks(st.session_state["text"])
                    if hasattr(chat_agent_module, "build_embeddings"):
                        chat_agent_module.build_embeddings()
                except Exception:
                    pass
            return chat_agent_module.answer_question(query)
        except Exception as e:
            # fall through to Gemini
            fallback_note = f"(agents.chat_agent failed: {e})\n"
    else:
        fallback_note = ""
    # Use Gemini
    gresp = local_gemini_answer(query, context=(st.session_state.get("text") if use_rag else None))
    return fallback_note + gresp

# ---------------------------
# Simple user management & XP
# ---------------------------
SALT = "hack_infinity_salt"
def _hash_password(password: str):
    return hashlib.sha256((SALT + password).encode("utf-8")).hexdigest()

def get_user_file(username):
    safe = "".join(c for c in username if c.isalnum() or c in ("_", "-")).lower()
    return os.path.join(USERS_DIR, f"{safe}.json")

def create_user(username, password):
    path = get_user_file(username)
    if os.path.exists(path):
        return False
    data = {"username": username, "password_hash": _hash_password(password),
            "xp":0,"level":1,"streak":0,"last_active":"","created_at":str(datetime.date.today())}
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)
    return True

def authenticate_user(username, password):
    path = get_user_file(username)
    if not os.path.exists(path):
        return None
    with open(path,"r",encoding="utf-8") as f:
        data = json.load(f)
    if data.get("password_hash") == _hash_password(password):
        return data
    return None

def load_user_data(username):
    path = get_user_file(username)
    if not os.path.exists(path):
        return None
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)

def save_user_data(username, data):
    path = get_user_file(username)
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2)

XP_MAP = {"upload":10,"flashcards":15,"quiz":20,"accuracy_bonus":10,"planner":5,"summary":8}
def update_xp_for_user(username, action):
    user = load_user_data(username)
    if user is None:
        return None
    today = str(datetime.date.today())
    user["xp"] = user.get("xp",0) + XP_MAP.get(action,0)
    if user.get("last_active") != today:
        user["streak"] = user.get("streak",0) + 1
        user["last_active"] = today
    if user["xp"] >= user.get("level",1) * 100:
        user["level"] = user.get("level",1) + 1
        try:
            st.balloons()
            st.success(f"🎉 {username} reached Level {user['level']}!")
        except Exception:
            pass
    save_user_data(username, user)
    return user

# ---------------------------
# JSON helpers
# ---------------------------
def save_json(data, filename):
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path,"w",encoding="utf-8") as f:
        json.dump(data,f,indent=2,ensure_ascii=False)
    return path

def load_json(filename):
    path = os.path.join(OUTPUT_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path,"r",encoding="utf-8") as f:
            s = f.read().strip()
            if not s:
                return None
            return json.loads(s)
    except Exception:
        return None

# ---------------------------
# -----------------------------
# Login UI (centered)
# -----------------------------
def login_ui(background_image_path=None):

    # Apply background image
    if background_image_path:
        img_b64 = get_image_as_base64(os.path.join(BASE_DIR, background_image_path))
    else:
        img_b64 = None

    bg_css = f"""
    body {{
        background: url("data:image/jpeg;base64,{img_b64}") no-repeat center center fixed;
        background-size: cover;
    }}
    """ if img_b64 else ""

    st.markdown(f"""
    <style>
    {bg_css}
    [data-testid="stSidebar"], header, footer {{display: none !important;}}

    .login-card {{
        position: absolute; top: 50%; left: 50%;
        transform: translate(-50%, -50%);
        width: 420px; padding: 36px 28px;
        backdrop-filter: blur(6px);
        background: rgba(0,0,0,0.45);
        color: #fff;
        border-radius: 14px;
        box-shadow: 0 8px 30px rgba(0,0,0,0.6);
        text-align: center;
    }}
    .login-title {{
        font-size: 28px; color: #00eaff; margin-bottom: 12px;
    }}
    .login-desc {{
        color: #d6e6f2; margin-bottom: 18px;
    }}
    </style>
    """, unsafe_allow_html=True)

    # Login card
    st.markdown('<div class="login-card">', unsafe_allow_html=True)
    st.markdown('<div class="login-title">🔐 Hack Infinity</div>', unsafe_allow_html=True)
    st.markdown('<div class="login-desc">AI Study Assistant — Login to Continue</div>', unsafe_allow_html=True)

    username = st.text_input("Username", key="login_user")
    password = st.text_input("Password", type="password", key="login_pass")

    col1, col2 = st.columns(2)

    login_clicked = False

    with col1:
        if st.button("Login"):
            login_clicked = True
            if username and password:
                u = authenticate_user(username, password)
                if u:
                    st.session_state["current_user"] = u["username"]
                    st.session_state["user_data"] = u
                else:
                    st.error("Invalid username or password.")

            else:
                st.warning("Enter both username and password.")

    with col2:
        if st.button("Register"):
            if username and password:
                ok = create_user(username, password)
                if ok:
                    st.success("Account created. Please login.")
                else:
                    st.error("Username already taken.")
            else:
                st.warning("Enter username and password to register.")

    st.markdown("</div>", unsafe_allow_html=True)

    # SAFE RERUN after form actions
    if login_clicked and st.session_state.get("current_user"):
        st.rerun()

# -----------------------------
# LOGIN CHECK
# -----------------------------
if "current_user" not in st.session_state:
    st.session_state["current_user"] = None

if not st.session_state["current_user"]:
    login_ui(background_image_path="loginbg.jpeg")
    st.stop()

# ---------------------------
# Main app after login
# ---------------------------
current_user = st.session_state.get("current_user")
user_data = load_user_data(current_user) or st.session_state.get("user_data")
st.sidebar.write(f"👤 {current_user}")

st.sidebar.header("Navigation")
page = st.sidebar.radio("Go to:", ["Dashboard","Upload Notes","Flashcards","Quiz","Revision Planner","Summarizer","Chatbot","View Saved Data"])

# ---------------------------
# DASHBOARD
# ---------------------------
if page == "Dashboard":
    st.header("📈 Study Progress Dashboard")
    st.subheader("🏆 Global Leaderboard")
    leaderboard = []
    for fname in os.listdir(USERS_DIR):
        if fname.endswith(".json"):
            try:
                with open(os.path.join(USERS_DIR,fname),"r",encoding="utf-8") as f:
                    ud = json.load(f)
                    leaderboard.append({"username":ud.get("username","?"),"xp":ud.get("xp",0),"level":ud.get("level",1),"streak":ud.get("streak",0)})
            except Exception:
                pass
    leaderboard = sorted(leaderboard, key=lambda x:x["xp"], reverse=True)[:10]
    if leaderboard:
        for i,entry in enumerate(leaderboard, start=1):
            medal = "🥇" if i==1 else "🥈" if i==2 else "🥉" if i==3 else f"#{i}"
            st.markdown(f"{medal} **{entry['username']}** — Level {entry['level']} | XP: {entry['xp']} | 🔥 {entry['streak']} days")
    else:
        st.info("No users yet — be the first to register!")

    st.markdown("---")
    ud = user_data or {}
    col1,col2,col3 = st.columns(3)
    col1.metric("Level", ud.get("level",1))
    col2.metric("XP", ud.get("xp",0))
    col3.metric("Streak", f"{ud.get('streak',0)} days")

# ---------------------------
# UPLOAD NOTES
# ---------------------------
elif page == "Upload Notes":
    st.header("Upload your PDFs")
    uploaded_files = st.file_uploader("Upload PDFs", type=['pdf'], accept_multiple_files=True)
    if uploaded_files:
        all_text = ""
        for f in uploaded_files:
            dest = os.path.join(PDF_DIR, f.name)
            with open(dest,"wb") as out:
                out.write(f.getbuffer())
            st.info(f"Saved {f.name}")
            chunks = extract_text_from_pdf(dest)
            all_text += "\n".join(chunks) + "\n\n"
        st.session_state['text'] = all_text
        with open(os.path.join(OUTPUT_DIR,"extracted_text.txt"),"w",encoding="utf-8") as out:
            out.write(all_text)
        st.success("Extraction complete")
        update_xp_for_user(current_user,"upload")

# ---------------------------
# FLASHCARDS
# ---------------------------
elif page == "Flashcards":
    st.markdown("<h1 style='text-align:center;'>📘 Flashcards</h1>", unsafe_allow_html=True)
    if 'text' not in st.session_state or st.session_state['text'].strip() == "":
        st.warning("⚠️ Please upload notes first.")
        st.stop()

    if st.button("✨ Generate Flashcards"):
        with st.spinner("Generating flashcards..."):
            try:
                # try agent function first
                cards = generate_flashcards_from_text(st.session_state.get("text",""), n_cards=6)
                # ensure it's list of dicts
                if isinstance(cards, str):
                    # sometimes model returns raw json text; try parse
                    try:
                        cards = json.loads(cards)
                    except Exception:
                        cards = [{"question":"Error","answer":str(cards)}]
            except Exception as e:
                cards = [{"question":"Error generating","answer":str(e)}]

        st.session_state["flashcards"] = cards
        save_json(cards, "flashcards.json")
        update_xp_for_user(current_user, "flashcards")
        st.success("Flashcards generated successfully!")

    if "flashcards" in st.session_state:
        st.markdown("## 🧠 Your Flashcards")
        for i,card in enumerate(st.session_state["flashcards"], start=1):
            q = card.get("question","No question")
            a = card.get("answer","No answer")
            st.markdown(f"""
            <div class='flashcard'>
                <div class='flash-q'>Flashcard {i}: {q}</div>
                <div class='flash-a'>{a}</div>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"🔊 Listen Flashcard {i}", key=f"listen_{i}"):
                try:
                    from gtts import gTTS
                    audio = gTTS(text=f"Question: {q}. Answer: {a}", lang='en')
                    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
                    audio.save(temp.name)
                    st.audio(temp.name)
                except Exception as e:
                    st.error(f"TTS error: {e}")
            st.markdown("<hr style='opacity:0.2;'>", unsafe_allow_html=True)

# ---------------------------
# QUIZ
# ---------------------------
elif page == "Quiz":
    st.header("Quiz")
    if 'text' not in st.session_state or not st.session_state['text'].strip():
        st.warning("Upload notes first")
        st.stop()
    if st.button("Generate Quiz"):
        try:
            quiz = generate_quiz_from_text(st.session_state['text'], n_questions=5)
            # ensure it's list
            if isinstance(quiz, str):
                try:
                    quiz = json.loads(quiz)
                except:
                    quiz = [{"question":"Error","options":["A","B","C","D"],"answer":"A"}]
            st.session_state['quiz'] = quiz
            save_json(quiz, "quiz.json")
        except Exception as e:
            st.error(f"Quiz generation error: {e}")
            st.session_state['quiz'] = []

    if 'quiz' in st.session_state:
        user_answers, correct = [], []
        for idx,q in enumerate(st.session_state['quiz'], start=1):
            st.markdown(f"**Q{idx}:** {q.get('question')}")
            opts = q.get('options', ["A","B","C","D"])
            ans = st.radio(f"Choose for Q{idx}", opts, key=f"quiz_{idx}")
            user_answers.append(ans)
            correct.append(q.get('answer'))
        if st.button("Submit Quiz"):
            score = sum(1 for a,b in zip(user_answers, correct) if a==b)
            acc = (score/len(correct))*100 if correct else 0
            st.success(f"Score: {score}/{len(correct)} ({acc:.1f}%)")
            save_json({'score':score,'total':len(correct),'accuracy':acc}, 'quiz_results.json')
            update_xp_for_user(current_user,'quiz')
            if acc>=80:
                update_xp_for_user(current_user,'accuracy_bonus')

# ---------------------------
# REVISION PLANNER
# ---------------------------
elif page == "Revision Planner":
    st.header("Revision Planner")
    topics = ["Topic 1","Topic 2","Topic 3"]
    today = datetime.date.today()
    plan = [{'Topic':t,'Revise On':str(today + datetime.timedelta(days=(i+1)*2))} for i,t in enumerate(topics)]
    st.table(plan)
    save_json(plan,'planner.json')
    update_xp_for_user(current_user,'planner')

# ---------------------------
# SUMMARIZER
# ---------------------------
elif page == "Summarizer":
    st.header("Summarizer")
    if 'text' not in st.session_state:
        st.warning("Upload notes first")
        st.stop()
    if st.button("Generate Summary"):
        paragraphs = st.session_state['text'].split('\n\n')
        summaries=[]
        for p in paragraphs[:10]:
            p=p.strip()
            if len(p)<80: continue
            sents=p.split('. ')
            summaries.append('. '.join(sents[:3]) + '.')
        st.session_state['summaries']=summaries
        save_json(summaries,'summaries.json')
        update_xp_for_user(current_user,'summary')
    if 'summaries' in st.session_state:
        for i,s in enumerate(st.session_state['summaries'], start=1):
            st.markdown(f"**Summary {i}:** {s}")

# ---------------------------
# CHATBOT
# ---------------------------
elif page == "Chatbot":
    st.header("Chatbot")
    qry = st.text_input("Ask your question")
    if qry:
        # prefer RAG (agents) if available
        if AGENTS_CHAT_AVAILABLE and 'text' in st.session_state and st.session_state['text'].strip():
            # let agents.chat_agent handle it (we wrapped earlier)
            try:
                # chat agent may expect chunks to be loaded already; wrapper handles that
                ans = answer_question_wrapper(qry, use_rag=True)
            except Exception as e:
                ans = f"(agents failed) {e}\n" + local_gemini_answer(qry, context=st.session_state.get("text"))
        else:
            ans = answer_question_wrapper(qry, use_rag=False)
        st.markdown("**Answer:**")
        st.write(ans)

# ---------------------------
# VIEW SAVED DATA
# ---------------------------
elif page == "View Saved Data":
    st.header("Saved files")
    files = os.listdir(OUTPUT_DIR)
    if not files:
        st.info("No saved files yet.")
    for f in files:
        st.markdown(f"**{f}**")
        if f.endswith(".json"):
            d = load_json(f)
            st.json(d)
        elif f.endswith(".txt"):
            with open(os.path.join(OUTPUT_DIR,f),"r",encoding="utf-8") as fh:
                st.text_area(f, fh.read()[:2000], height=200)

# ---------------------------
# sidebar footer
# ---------------------------
st.sidebar.markdown("---")
st.sidebar.markdown("Hack Infinity — TEAM AXION")
