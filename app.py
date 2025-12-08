"""
Streamlit app: ถ้าหนูถามพี่จะรับปะ? (Blue/Dark Theme)
Features:
- Python only
- 10 questions per round (random from question bank)
- 10-second timeout (server-side style)
- Buttons: ได้ดิ / อาจจะยัง
- Leaderboard (SQLite)
- Import/export questions
- Export summary CSV/Excel
- Optional Gemini/OpenAI API for analysis or generating questions
- Bar charts and personality tiers
- Aggregate answer counts persisted in DB (for "ผลรวมของทุกคน")
"""

import streamlit as st
import pandas as pd
import random
import time
import sqlite3
from datetime import datetime
import io
import os

        
# Optional: Gemini (google.generativeai)
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except Exception:
    HAVE_GENAI = False

# Optional: Altair for nicer charts
try:
    import altair as alt
    HAVE_ALTAIR = True
except Exception:
    HAVE_ALTAIR = False

# ----------------- CONFIG -----------------
APP_TITLE = "ถ้าหนูถามพี่จะรับปะ?"
DB_FILENAME = "game_leaderboard.db"
QUESTIONS_FILENAME = "questions_bank.csv"
DEFAULT_MODEL = ""

# ----------------- PAGE SETUP -----------------
st.set_page_config(page_title=APP_TITLE, layout="centered", initial_sidebar_state="expanded")

# Blue/Dark styling
st.markdown("""<style>
:root{
    --dark-bg: #0d1117;
    --card-bg: #161b22;
    --accent: #2f81f7;
    --text-main: #e6edf3;
    --text-muted: #8b949e;
}
.stApp {
    background: var(--dark-bg);
    color: var(--text-main);
}
.card {
    background: var(--card-bg);
    padding: 18px;
    border-radius: 14px;
    border: 1px solid #30363d;
}
.question-box {
    background: #0f141a;
    padding: 16px;
    border-radius: 12px;
    border-left: 6px solid var(--accent);
}
.small-muted { color: var(--text-muted); font-size:12px; }
.blue-btn {
    background-color: var(--accent);
    color: white !important;
    border-radius: 10px;
    padding: 10px 14px;
}
</style>""", unsafe_allow_html=True)

st.title(f"🎮 {APP_TITLE}")
st.markdown("เกมตอบคำถามแบบเลือก 2 ตัวเลือก ที่ออกแบบมาเพื่อความสนุกสนาน ทดสอบนิสัย วิธีคิด และสไตล์การตอบของผู้เล่น โดยแต่ละคำถามเป็น “สถานการณ์สมมติ” ผู้เล่นต้องตอบภายใน 10 วินาที หากหมดเวลาจะถือว่า ข้าม (Timeout)")


# ----------------- QUESTIONS: default list -----------------
DEFAULT_QUESTIONS = [
    "ถ้าหนูชวนพี่ไปกินข้าวเย็นพิเศษ พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ช่วยถ่ายรูปให้ในงานสำคัญ พี่จะรับปะ?",
    "ถ้าหนูอยากให้พี่ช่วยพาไปงานวันเกิดเพื่อน พี่จะรับปะ?",
    "ถ้าหนูขอยืมหนังสือเล่มโปรดของพี่ พี่จะยอมให้ยืมไหม?",
    "ถ้าหนูถามพี่เรื่องความรัก พี่จะตอบจริงไหม?",
    "ถ้าหนูขอให้พี่เลี้ยงน้องหมาสักคืน พี่จะรับปะ?",
    "ถ้าหนูอยากให้พี่ช่วยติวสอบหนึ่งชั่วโมง พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่แชร์รหัส Wi-Fi ชั่วคราว พี่จะให้ไหม?",
    "ถ้าหนูอยากให้พี่ลองเมนูอาหารแปลก ๆ ด้วยกัน พี่จะรับปะ?",
    "ถ้าหนูชวนพี่ไปร้านกาแฟเปิดใหม่ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่เป็นเพื่อนคุยตอนเครียด พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ช่วยเลือกชุดไปราตรี พี่จะช่วยไหม?",
    "ถ้าหนูฝากของไว้กับพี่หนึ่งวัน พี่จะดูแลไหม?",
    "ถ้าหนูขอให้พี่เล่นเกมออนไลน์ด้วยกัน พี่จะเล่นไหม?",
    "ถ้าหนูชวนพี่ไปดูหนังสยองขวัญ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ร้องเพลงให้ฟัง พี่จะร้องไหม?",
    "ถ้าหนูจะให้พี่ลองทำเบเกอรีตามสูตร พี่จะทำไหม?",
    "ถ้าหนูขอคำแนะนำเรื่องสัมภาษณ์งาน พี่จะช่วยให้ไหม?",
    "ถ้าหนูต้องการคนไปงานเเต่งงานเป็นเพื่อน พี่จะไปไหม?",
    "ถ้าหนูอยากให้พี่ช่วยออกแบบโปสเตอร์ พี่จะรับปะ?",
    "ถ้าหนูลากพี่ไปเที่ยวสั้น ๆ ตอนวันหยุด พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่สอนทักษะใหม่ ๆ สักครั้ง พี่จะสอนไหม?",
    "ถ้าหนูขอให้พี่เป็นคนโหวตให้ในงานประกวด พี่จะโหวตไหม?",
    "ถ้าหนูอยากให้พี่ลองเมนูต่างประเทศด้วยกัน พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ช่วยยืมของใช้เล็ก ๆ พี่จะให้ไหม?",
    "ถ้าหนูขอให้พี่ช่วยติดต่อร้านค้าให้ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่แลกเพลงโปรดกัน พี่จะแลกไหม?",
    "ถ้าหนูขอให้พี่สอนเต้นสั้น ๆ หน่อย พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ทำเซอร์ไพรส์เล็ก ๆ ให้เพื่อน พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยรีวิวงานเขียน พี่จะทำไหม?",
    "ถ้าหนูขอให้พี่ไปวิ่งออกกำลังกายด้วยกัน พี่จะไปไหม?",
    "ถ้าหนูอยากให้พี่แนะนำหนังสือดี ๆ สักเล่ม พี่จะให้ไหม?",
    "ถ้าหนูชวนพี่ไปเดินห้างตอนกลางคืน พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยเทสต์แอปใหม่ พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ทำชาเลนจ์ตลก ๆ พี่จะร่วมไหม?",
    "ถ้าหนูขอให้พี่ช่วยแปลภาษาสั้น ๆ พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ไปงานอีเวนต์ด้วยกัน พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยเตรียมของขวัญ พี่จะช่วยไหม?",
    "ถ้าหนูชวนพี่ไปถ่ายรูปฮา ๆ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยออกแบบโลโก้เล็ก ๆ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่เป็นเพื่อนอ่านหนังสือ พี่จะรับปะ?",
    "ถ้าหนูอยากให้พี่ช่วยทำวิดีโอสั้น ๆ พี่จะช่วยไหม?",
    "ถ้าหนูชวนพี่ไปฟังคอนเสิร์ตอินดี้ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยสอนทำอาหารพื้นบ้าน พี่จะรับปะ?",
    "ถ้าหนูอยากให้พี่ช่วยหาไอเดียโปรเจกต์ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยรีวิวโค้ดสั้น ๆ พี่จะทำไหม?",
    "ถ้าหนูชวนพี่ไปวัด/ทำบุญ พี่จะไปไหม?",
    "ถ้าหนูอยากให้พี่พาไปกินของโปรด พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ช่วยถือของชั่วคราว พี่จะรับไหม?",
    "ถ้าหนูอยากให้พี่ช่วยเตรียมสคริปต์พูด พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยประสานงานกับเพื่อน พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่เป็นโค้ชสั้น ๆ พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่พูดคำชมในที่สาธารณะ พี่จะทำไหม?",
    "ถ้าหนูชวนพี่ไปฮันนีมูนปลอม ๆ เพื่อถ่ายรูป พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยสอนภาษาอังกฤษพื้นฐาน พี่จะรับไหม?",
    "ถ้าหนูอยากให้พี่ช่วยติวภาษาไทย พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่เป็นเพื่อนดูละครทีวี พี่จะรับปะ?",
    "ถ้าหนูอยากให้พี่ช่วยจัดงานเล็ก ๆ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยหาเพลงเปิดตัว พี่จะช่วยไหม?",
    "ถ้าหนูชวนพี่ไปปาร์ตี้ธีมคอสเพลย์ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยลองของแฟชั่นแปลก ๆ พี่จะลองไหม?",
    "ถ้าหนูอยากให้พี่ช่วยถอดบทสนทนา พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยปรับพอร์ตโฟลิโอ พี่จะรับไหม?",
    "ถ้าหนูชวนพี่ไปดูดาวกลางคืน พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยเป็นกรรมการตัดสินของเล่น พี่จะทำไหม?",
    "ถ้าหนูอยากให้พี่ลองเมนูแปลก ๆ ในตลาด พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ช่วยออกแบบการ์ด พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ไปช่วยงานเปิดตัวผลิตภัณฑ์ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยจัดรายการเพลงสำหรับรถ พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่สวมชุดคู่ถ่ายรูป พี่จะรับปะ?",
    "ถ้าหนูขอให้พี่ลองเล่นกีฬาแปลก ๆ พี่จะลองไหม?",
    "ถ้าหนูชวนพี่ไปทำ workshop สั้น ๆ พี่จะไปร่วมไหม?",
    "ถ้าหนูขอให้พี่ช่วยออกแบบเทมเพลต พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยทดลองไอเดียขายของ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ลองเมคอัพลุคใหม่ ๆ พี่จะลองไหม?",
    "ถ้าหนูชวนพี่ไปดูนิทรรศการศิลปะ พี่จะไปไหม?",
    "ถ้าหนูอยากให้พี่ช่วยหาคำคมโพสต์ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยจัดคอนเทนต์สั้น ๆ พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยเทสต์เกมมือถือ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่พาไปสถานที่ประหลาด พี่จะไปไหม?",
    "ถ้าหนูอยากให้พี่ช่วยรีวิวร้านอาหาร พี่จะทำไหม?",
    "ถ้าหนูชวนพี่ไปแคมป์ปิ้งสั้น ๆ พี่จะไปไหม?",
    "ถ้าหนูขอให้พี่ช่วยเป็นพี่เลี้ยงเด็กชั่วคราว พี่จะรับไหม?",
    "ถ้าหนูอยากให้พี่ช่วยจัดแผนเที่ยวสั้น ๆ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยเขียนคำอธิบายสินค้า พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยจัด playlist งานเลี้ยง พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยถ่ายทอดสดสั้น ๆ พี่จะทำไหม?",
    "ถ้าหนูชวนพี่ไปลองอาหารริมทาง พี่จะไปไหม?",
    "ถ้าหนูอยากให้พี่ช่วยซัพพอร์ตโปรเจกต์เล็ก ๆ พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยเทรนสั้น ๆ พี่จะรับไหม?",
    "ถ้าหนูอยากให้พี่ช่วยหาโลเคชันถ่ายรูป พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยเตรียมคำพูดสำคัญ พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยออกแบบโปสการ์ด พี่จะช่วยไหม?",
    "ถ้าหนูขอให้พี่ช่วยจัดกิจกรรมจิ๋ว ๆ พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยดูแลบูธสั้น ๆ พี่จะรับไหม?",
    "ถ้าหนูขอให้พี่ช่วยประสานงานกับร้านค้า พี่จะช่วยไหม?",
    "ถ้าหนูอยากให้พี่ช่วยแลกเปลี่ยนสูตรอาหาร พี่จะรับไหม?",
    "ถ้าหนูขอให้พี่เป็นที่ปรึกษาเล็ก ๆ พี่จะทำไหม?",
    "ถ้าหนูอยากให้พี่ช่วยเขียนแคปชันสั้น ๆ พี่จะช่วยไหม?",
]

# ----------------- SESSION INIT -----------------
def init_session():
    if "questions" not in st.session_state:
        # Load saved bank if exists; otherwise use DEFAULT_QUESTIONS
        if os.path.exists(QUESTIONS_FILENAME):
            try:
                df = pd.read_csv(QUESTIONS_FILENAME)
                if "question" in df.columns:
                    st.session_state.questions = df["question"].astype(str).tolist()
                else:
                    st.session_state.questions = DEFAULT_QUESTIONS.copy()
            except Exception:
                st.session_state.questions = DEFAULT_QUESTIONS.copy()
        else:
            st.session_state.questions = DEFAULT_QUESTIONS.copy()

    if "round_questions" not in st.session_state:
        st.session_state.round_questions = []
    if "q_index" not in st.session_state:
        st.session_state.q_index = 0
    if "answers" not in st.session_state:
        st.session_state.answers = []
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "player" not in st.session_state:
        st.session_state.player = ""
    if "openai_key" not in st.session_state:
        st.session_state.openai_key = ""
    if "gemini_key" not in st.session_state:
        st.session_state.gemini_key = ""
    if "model_name" not in st.session_state:
        st.session_state.model_name = DEFAULT_MODEL
    if "last_round_score" not in st.session_state:
        st.session_state.last_round_score = 0

init_session()

# ----------------- FIXED: Gemini (google.generativeai) -----------------
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except Exception:
    HAVE_GENAI = False


def list_gemini_models():
    """Return ONLY models that support generateContent for google.generativeai >= 0.8.5."""
    if not HAVE_GENAI:
        return []

    usable = []

    try:
        models = genai.list_models()
        for m in models:
            # get model name
            name = getattr(m, "name", None)
            if not name and isinstance(m, dict):
                name = m.get("name") or m.get("model") or m.get("id")

            if not name:
                continue

            # filter only models that support generateContent
            supported = getattr(m, "supported_generation_methods", None)
            if supported and "generateContent" in supported:
                usable.append(name)

        # if we found valid models
        if usable:
            return usable

    except Exception:
        pass

    # fallback (safe defaults)
    return [
        "models/gemini-2.5-flash",
        "models/gemini-2.5-pro",
    ]


def generate_with_genai(model_name, prompt):
    """Unified safe call for google.generativeai 0.8.5+."""
    if not HAVE_GENAI:
        raise RuntimeError("Gemini not available")

    if not model_name:
        # Safe fallback model
        model_name = "models/gemini-2.5-flash"

    # New API (0.8.0+)
    try:
        Model = getattr(genai, "GenerativeModel", None)
        if callable(Model):
            gm = Model(model_name)

            if hasattr(gm, "generate_content"):
                return gm.generate_content(prompt)

            if hasattr(gm, "generate"):  # very old alternative
                return gm.generate(prompt)
    except Exception as e:
        last_error = e

    # Very old API fallback (not used in 0.8.5)
    try:
        if hasattr(genai, "generate_content"):
            return genai.generate_content(model=model_name, prompt=prompt)
        if hasattr(genai, "generate_text"):
            return genai.generate_text(model=model_name, prompt=prompt)
    except Exception as e:
        last_error = e

    raise last_error

# ----------------- DATABASE (SQLite) -----------------
def init_db():
    conn = sqlite3.connect(DB_FILENAME, check_same_thread=False)
    c = conn.cursor()
    # leaderboard stores individual round entries; aggregated per-player via SQL
    c.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player TEXT,
        score INTEGER,
        last_played TEXT
    )
    """)
    # answer_counts stores total counts of each answer across all rounds/players
    c.execute("""
    CREATE TABLE IF NOT EXISTS answer_counts (
        answer TEXT PRIMARY KEY,
        cnt INTEGER
    )
    """)
    conn.commit()
    return conn

conn = init_db()

def update_leaderboard(player, score):
    ts = datetime.utcnow().isoformat() + "Z"
    c = conn.cursor()
    c.execute("INSERT INTO leaderboard (player, score, last_played) VALUES (?, ?, ?)",
              (player, score, ts))
    conn.commit()

def get_leaderboard_df():
    df = pd.read_sql_query("""
        SELECT player, SUM(score) as total_score, MAX(last_played) as last_played
        FROM leaderboard
        GROUP BY player
        ORDER BY total_score DESC
    """, conn)
    return df

def increment_answer_count(answer, increment=1):
    if answer is None:
        answer = "TIMEOUT"
    c = conn.cursor()
    # upsert: if exists, increment, else insert
    c.execute("""
    INSERT INTO answer_counts (answer, cnt)
    VALUES (?, ?)
    ON CONFLICT(answer) DO UPDATE SET cnt = cnt + excluded.cnt
    """, (answer, increment))
    conn.commit()

def get_aggregate_answer_counts():
    df = pd.read_sql_query("SELECT answer, cnt FROM answer_counts ORDER BY cnt DESC", conn)
    return df

# ----------------- HELPERS -----------------
def new_round():
    # ensure we have at least 10 questions
    if len(st.session_state.questions) < 10:
        st.error("ต้องมีคำถามอย่างน้อย 10 ข้อใน question bank")
        return
    st.session_state.round_questions = random.sample(st.session_state.questions, 10)
    st.session_state.q_index = 0
    st.session_state.answers = []
    st.session_state.start_time = time.time()
    st.session_state.last_round_score = 0

def record_answer(question, answer, timed_out=False, elapsed_sec=None):
    rec = {
        "player": st.session_state.player if st.session_state.player else "anonymous",
        "question": question,
        "answer": answer if (answer is not None) else "TIMEOUT",
        "timed_out": bool(timed_out),
        "elapsed_sec": int(elapsed_sec) if elapsed_sec is not None else None,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    st.session_state.answers.append(rec)
    # increase round score only when non-timeout and has explicit answer
    if not timed_out and answer is not None:
        st.session_state.last_round_score += 1

    # update aggregate counts in DB
    # we count "ได้ดิ", "อาจจะยัง", and "TIMEOUT" where appropriate
    ans_key = answer if (answer is not None) else "TIMEOUT"
    increment_answer_count(ans_key, increment=1)

def summary_df_from_answers():
    if not st.session_state.answers:
        return pd.DataFrame()
    df = pd.DataFrame(st.session_state.answers)
    # Keep only the questions that were in this round (just in case)
    if st.session_state.round_questions:
        df = df[df["question"].isin(st.session_state.round_questions)]
    return df

def compute_answer_stats():
    answers = st.session_state.answers or []
    n = len(answers)
    got = sum(1 for a in answers if a["answer"] == "ได้ดิ")
    maybe = sum(1 for a in answers if a["answer"] == "อาจจะยัง")
    timeout = sum(1 for a in answers if a["answer"] == "TIMEOUT" or a.get("timed_out"))
    avg_time = None
    times = [a.get("elapsed_sec") for a in answers if a.get("elapsed_sec") is not None]
    if times:
        avg_time = sum(times)/len(times)
    return {"total": n, "ได้ดิ": got, "อาจจะยัง": maybe, "timeout": timeout, "avg_time": avg_time}

def personality_tier(stats):
    # Determine tier based on % ของ "ได้ดิ"
    total_answered = stats["ได้ดิ"] + stats["อาจจะยัง"] + stats["timeout"]
    if total_answered == 0:
        return ("ยังไม่มีข้อมูล", "ตอบน้อยไป — ลองเล่นสักรอบก่อนนะ!")
    pct_yes = (stats["ได้ดิ"] / total_answered) * 100
    if pct_yes >= 70:
        return ("🔥 กล้าเสี่ยง (Risk-taker)", "คุณค่อนข้างใจกล้าเลยนะเนี่ย 'ได้ดิ' บ่อย — เปิดใจลองสิ่งใหม่ ๆ เยอะ")
    if pct_yes >= 40:
        return ("⚖️ กลางๆ (Balanced)", "มีทั้งได้และไม่ ได้ — เป็นคนพิจารณาก่อนตัดสินใจ")
    return ("🛡️ ระมัดระวัง (Cautious)", "มักตอบ 'อาจจะยัง' หรือหมดเวลา — ระวังและคิดรอบคอบ")

# ----------------- SIDEBAR -----------------
st.sidebar.header("ตั้งค่าเกม / API Keys")
st.session_state.player = st.sidebar.text_input("ชื่อผู้เล่น", value=st.session_state.player)
st.session_state.openai_key = st.sidebar.text_input("OpenAI API Key (optional)", type="password", value=st.session_state.openai_key)
st.session_state.gemini_key = st.sidebar.text_input("Google Gemini API Key (optional)", type="password", value=st.session_state.gemini_key)
st.session_state.model_name = st.sidebar.text_input("Model name (for Gemini)", value=st.session_state.model_name)



st.sidebar.markdown("---")
if st.sidebar.button("เริ่มเกม"):
    new_round()
    st.rerun()

st.sidebar.markdown("**Note:** Timer เป็น server-side (ถ้าไม่กดอะไรและไม่มี rerun จะรออยู่)")

# ----------------- SIDEBAR: SHOW QUESTION BANK -----------------
st.sidebar.markdown("---")
st.sidebar.subheader(f"📚 Question Bank ({len(st.session_state.questions)} ข้อ)")
st.sidebar.write("สามารถดาวน์โหลดคำถามทั้งหมดได้ที่นี่")
try:
    csv_bytes = pd.DataFrame({"question": st.session_state.questions}).to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("ดาวน์โหลด questions_bank.csv", csv_bytes, file_name=QUESTIONS_FILENAME, mime="text/csv")
except Exception:
    st.sidebar.write("ไม่สามารถเตรียมไฟล์สำหรับดาวน์โหลดได้ขณะนี้")

# If user provided Gemini key and package available, configure
if HAVE_GENAI and st.session_state.gemini_key:
    try:
        genai.configure(api_key=st.session_state.gemini_key)
    except Exception:
        st.sidebar.error("ไม่สามารถตั้งค่า Gemini API ด้วยคีย์นี้")

# ----------------- MAIN UI -----------------
colL, colR = st.columns([2,1])

with colL:

    if not st.session_state.round_questions:
        # Centered start button when no round is active
        c1, c2, c3 = st.columns([1,2,1])
        with c2:
            if st.button("เริ่มเกม"):
                new_round()
                st.rerun()
    else:
        idx = st.session_state.q_index
        total = len(st.session_state.round_questions)
        # avoid division by zero
        if total > 0:
            st.progress(idx/total)
        else:
            st.progress(0.0)

        if idx >= total:
            st.success("✔ จบรอบแล้ว — ดูสรุปด้านล่าง")
        else:
            q = st.session_state.round_questions[idx]

            st.markdown(f'<div class="question-box"><h4>ข้อที่ {idx+1}/{total}</h4><p style="font-size:16px;">{q}</p></div>',
                        unsafe_allow_html=True)

            # timer start
            if st.session_state.start_time is None:
                st.session_state.start_time = time.time()

            elapsed = time.time() - st.session_state.start_time
            remain = max(0, 10 - int(elapsed))
            st.write(f"⏳ เวลาเหลือ (โดยประมาณ): **{remain}** วินาที")
            st.write('<div class="small-muted">หมายเหตุ: ถ้าตอบหลังเวลาจะถูกบันทึกเป็น TIMEOUT</div>', unsafe_allow_html=True)

            a1, a2 = st.columns(2)
            if a1.button("✅ ได้ดิ"):
                if elapsed > 10:
                    record_answer(q, None, timed_out=True, elapsed_sec=elapsed)
                    st.warning("ตอบช้า — บันทึกเป็น TIMEOUT")
                else:
                    record_answer(q, "ได้ดิ", timed_out=False, elapsed_sec=elapsed)
                    st.success("บันทึก: ได้ดิ (+1 คะแนน)")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()

            if a2.button("❌ อาจจะยัง"):
                if elapsed > 10:
                    record_answer(q, None, timed_out=True, elapsed_sec=elapsed)
                    st.warning("ตอบช้า — บันทึกเป็น TIMEOUT")
                else:
                    record_answer(q, "อาจจะยัง", timed_out=False, elapsed_sec=elapsed)
                    st.success("บันทึก: อาจจะยัง (+1 คะแนน)")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()

            # server-side timeout detection (when rerun occurs)
            if elapsed > 10:
                # record timeout and move on
                record_answer(q, None, timed_out=True, elapsed_sec=elapsed)
                st.info("หมดเวลา → ข้ามข้อนี้ (บันทึก TIMEOUT)")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()

    # card wrapper removed to simplify layout

with colR:
    st.subheader("🏆 Leaderboard & Score")
    if st.session_state.player:
        st.write(f"ผู้เล่น: **{st.session_state.player}**")
    else:
        st.write("ผู้เล่น: (anonymous)")
    # Cap displayed score to number of questions in the round to avoid accidental over-counting
    displayed_score = st.session_state.last_round_score
    try:
        if st.session_state.round_questions:
            displayed_score = min(displayed_score, len(st.session_state.round_questions))
    except Exception:
        pass
    st.write(f"คะแนนรอบนี้: **{displayed_score}**")

    if st.button("บันทึกคะแนนรอบนี้"):
        if st.session_state.player:
            # ensure we don't save more than the number of questions in the round
            save_score = displayed_score
            update_leaderboard(st.session_state.player, save_score)
            st.success("บันทึกคะแนนสำเร็จ")
        else:
            st.warning("กรุณากรอกชื่อผู้เล่นใน sidebar เพื่อบันทึก")

    # Note about saving scores
    st.caption("หมายเหตุ: หากไม่กด 'บันทึกคะแนนรอบนี้' คะแนนรอบนี้จะไม่ถูกรวมเข้ากับคะแนนรวมของผู้เล่นอื่น")

    df_lb = get_leaderboard_df()
    if df_lb.empty:
        st.write("ยังไม่มีคะแนน")
    else:
        # display leaderboard with 1-based rank index
        try:
            df_display = df_lb.copy()
            df_display.index = range(1, len(df_display) + 1)
            st.dataframe(df_display)
        except Exception:
            st.dataframe(df_lb)
# card wrapper removed to simplify layout

# ----------------- SUMMARY -----------------
st.markdown("---")
st.subheader("📊 สรุปผลรอบนี้")
if st.session_state.answers:
    df_sum: pd.DataFrame = summary_df_from_answers()
    # show columns in nice order
    cols_order = ["player", "question", "answer", "timed_out", "elapsed_sec", "timestamp"]
    df_sum = df_sum[[c for c in cols_order if c in df_sum.columns]]

    # present summary with 1-based index for readability
    try:
        df_sum_display = df_sum.copy()
        df_sum_display.index = range(1, len(df_sum_display) + 1)
        st.dataframe(df_sum_display)
    except Exception:
        st.dataframe(df_sum)

    # stats & charts
    stats = compute_answer_stats()
    st.markdown("**สถิติ (รอบนี้):**")
    st.write(f"- ตอบทั้งหมด: {stats['total']}")
    st.write(f"- ได้ดิ: {stats['ได้ดิ']}  |  อาจจะยัง: {stats['อาจจะยัง']}  |  หมดเวลา: {stats['timeout']}")
    if stats["avg_time"] is not None:
        st.write(f"- เวลาเฉลี่ยต่อคำตอบ: {stats['avg_time']:.1f} วินาที")

    # bar chart (this round)
    chart_df = pd.DataFrame({
        "คำตอบ": ["ได้ดิ", "อาจจะยัง", "หมดเวลา"],
        "จำนวน": [stats["ได้ดิ"], stats["อาจจะยัง"], stats["timeout"]]
    })

    # Try Altair for gray bar chart with vertical labels
    if HAVE_ALTAIR:
        # gray palette for bar chart
        color_scale = alt.Scale(domain=["ได้ดิ", "อาจจะยัง", "หมดเวลา"],
                                range=["#808080", "#A9A9A9", "#696969"])  # gray tones
        bar = alt.Chart(chart_df).mark_bar().encode(
            x=alt.X("คำตอบ:N", title="คำตอบ", axis=alt.Axis(labelAngle=90)),
            y=alt.Y("จำนวน:Q", title="จำนวน"),
            color=alt.Color("คำตอบ:N", scale=color_scale, legend=None),
            tooltip=["คำตอบ", "จำนวน"]
        ).properties(height=250)
        st.altair_chart(bar, use_container_width=True)
    else:
        st.bar_chart(chart_df.set_index("คำตอบ"))

    # pie chart (altair) - light blue colors
    if HAVE_ALTAIR:
        pie = alt.Chart(chart_df).mark_arc().encode(
            theta=alt.Theta(field="จำนวน", type="quantitative"),
            color=alt.Color(field="คำตอบ", type="nominal", scale=alt.Scale(range=["#1E40AF", "#2563EB", "#1D4ED8"])),
            tooltip=["คำตอบ", "จำนวน"]
        )
        st.altair_chart(pie, use_container_width=True)
    else:
        # skip pie if altair not available
        pass

    # personality tier
    tier, tier_msg = personality_tier(stats)
    st.markdown(f"### ระดับนิสัย (Personality tier): **{tier}**")
    st.write(tier_msg)

    # download CSV
    csv = df_sum.to_csv(index=False).encode("utf-8")
    st.download_button("ดาวน์โหลดสรุป (CSV)", csv, "summary.csv", "text/csv")

    # export Excel (use BytesIO)
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as w:
        df_sum.to_excel(w, index=False, sheet_name="summary")
    bio.seek(0)
    st.download_button(
        "ดาวน์โหลดสรุป (Excel)",
        bio.getvalue(),
        "summary.xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
else:
    st.info("ยังไม่มีคำตอบ — เริ่มรอบใหม่และตอบคำถามเพื่อดูสรุป")

# ----------------- AGGREGATE CHART: results across all players -----------------
st.markdown("---")
st.subheader("📈 ภาพรวมการตอบของทุกคน")

df_agg = get_aggregate_answer_counts()

if df_agg.empty:
    st.info("ยังไม่มีสถิติรวมจากผู้เล่นทั้งหมด — คำตอบจะถูกเก็บเมื่อผู้เล่นตอบคำถาม")
else:
    # Make sure the common categories are present in the plot (for consistent ordering)
    expected = ["ได้ดิ", "อาจจะยัง", "TIMEOUT"]
    # merge so missing ones appear with 0
    df_base = pd.DataFrame({"answer": expected})
    df_plot = df_base.merge(df_agg, how="left", left_on="answer", right_on="answer").fillna(0)
    df_plot["cnt"] = df_plot["cnt"].astype(int)
    # If there are other answers, append them
    others = df_agg[~df_agg["answer"].isin(expected)]
    if not others.empty:
        df_plot = pd.concat([df_plot, others.rename(columns={"cnt":"cnt"})], ignore_index=True, sort=False).fillna(0)
        df_plot["cnt"] = df_plot["cnt"].astype(int)

    # Altair gray color mapping with vertical labels
    if HAVE_ALTAIR:
        # define gray palette
        mapping = {
            "ได้ดิ": "#808080",
            "อาจจะยัง": "#A9A9A9",
            "TIMEOUT": "#696969"
        }
        color_scale = alt.Scale(domain=list(mapping.keys()), range=list(mapping.values()))
        bar = alt.Chart(df_plot).mark_bar().encode(
            x=alt.X("answer:N", title="คำตอบ", axis=alt.Axis(labelAngle=90)),
            y=alt.Y("cnt:Q", title="จำนวน (รวม)"),
            color=alt.Color("answer:N", scale=color_scale, legend=None),
            tooltip=["answer", "cnt"]
        ).properties(height=280)
        st.altair_chart(bar, use_container_width=True)
    else:
        st.bar_chart(df_plot.set_index("answer")["cnt"])

    # Provide downloadable summary (aggregate answers + leaderboard)
    try:
        df_answers_all = df_agg.copy()
        df_leader = get_leaderboard_df()

        # overall metrics
        total_answers = int(df_answers_all['cnt'].sum()) if not df_answers_all.empty else 0
        overall = {
            'metric': ['total_answers'],
            'value': [total_answers]
        }
        df_overall = pd.DataFrame(overall)

        # prepare Excel with multiple sheets
        bio = io.BytesIO()
        with pd.ExcelWriter(bio, engine="xlsxwriter") as writer:
            df_answers_all.to_excel(writer, sheet_name="aggregate_answers", index=False)
            df_leader.to_excel(writer, sheet_name="leaderboard", index=False)
            df_overall.to_excel(writer, sheet_name="overall", index=False)
        bio.seek(0)

        st.download_button("ดาวน์โหลดสรุปการวิเคราะห์ (Excel)", data=bio.getvalue(), file_name="summary_analysis.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        # CSV of aggregate answers
        csv_agg = df_answers_all.to_csv(index=False).encode('utf-8')
        st.download_button("ดาวน์โหลดสรุปการวิเคราะห์ (CSV: aggregate answers)", data=csv_agg, file_name="aggregate_answers.csv", mime="text/csv")
    except Exception as e:
        st.error(f"ไม่สามารถเตรียมไฟล์สรุปได้: {e}")

# (Question Bank is available via sidebar download)

# ----------------- OPTIONAL: ANALYZE WITH LLM -----------------
# ----------------- OPTIONAL: ANALYZE WITH LLM -----------------
st.markdown("---")
st.subheader("🧠 วิเคราะห์สไตล์การตอบ")

if st.session_state.openai_key or (st.session_state.gemini_key and HAVE_GENAI):
    prompt = f"สรุปสไตล์การตอบของผู้เล่น {st.session_state.player or 'anonymous'} จากตารางนี้:\n\n"
    if st.session_state.answers:
        prompt += pd.DataFrame(st.session_state.answers).to_string()
    else:
        prompt += "ยังไม่มีคำตอบ"

    if st.button("กดเพื่อดูผลวิเคราะห์เลย!"):
        out = ""
        # Prefer OpenAI if key provided
        if st.session_state.openai_key:
            try:
                import openai
                openai.api_key = st.session_state.openai_key
                resp = openai.ChatCompletion.create(
                    model="gpt-4.1-mini",
                    messages=[{"role":"user","content":prompt}],
                    max_tokens=400
                )
                out = resp["choices"][0]["message"]["content"]
                st.markdown("**ผลวิเคราะห์ (OpenAI):**")
                st.write(out)
            except Exception as e:
                st.error(f"OpenAI วิเคราะห์ไม่ได้: {e}")
        elif st.session_state.gemini_key and HAVE_GENAI:
            try:
                genai.configure(api_key=st.session_state.gemini_key)
                available = list_gemini_models()
                if available:
                    if not st.session_state.model_name or st.session_state.model_name not in available:
                        st.session_state.model_name = available[0]
                resp = generate_with_genai(st.session_state.model_name, prompt)

                # parse response
                if hasattr(resp, "text"):
                    out = resp.text
                elif isinstance(resp, dict):
                    if "candidates" in resp and resp["candidates"]:
                        out = resp["candidates"][0].get("content") or str(resp)
                    elif "outputs" in resp and resp["outputs"]:
                        out = resp["outputs"][0].get("content") or str(resp)
                    else:
                        out = str(resp)
                else:
                    out = str(resp)

                st.markdown("**ผลวิเคราะห์ (Gemini):**")
                st.write(out)
            except Exception as e:
                st.error(f"Gemini วิเคราะห์ไม่ได้: {e}")

        # ----------------- NEW: SAVE to session & download -----------------
        if out:
            st.session_state.ai_analysis_text = out
            # TXT
            st.download_button(
                "ดาวน์โหลดผลวิเคราะห์ AI (TXT)",
                data=out,
                file_name=f"ai_analysis_{st.session_state.player or 'anonymous'}.txt",
                mime="text/plain"
            )
            # CSV
            df_ai = pd.DataFrame([{
                "player": st.session_state.player or "anonymous",
                "ai_analysis": out
            }])
            csv_ai = df_ai.to_csv(index=False).encode("utf-8")
            st.download_button(
                "ดาวน์โหลดผลวิเคราะห์ AI (CSV)",
                data=csv_ai,
                file_name=f"ai_analysis_{st.session_state.player or 'anonymous'}.csv",
                mime="text/csv"
            )
            # Excel
            bio_ai = io.BytesIO()
            with pd.ExcelWriter(bio_ai, engine="xlsxwriter") as writer:
                df_ai.to_excel(writer, index=False, sheet_name="AI Summary")
            bio_ai.seek(0)
            st.download_button(
                "ดาวน์โหลดผลวิเคราะห์ AI (Excel)",
                data=bio_ai.getvalue(),
                file_name=f"ai_analysis_{st.session_state.player or 'anonymous'}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
else:
    st.info("กรอก OpenAI API Key หรือ Google Gemini API Key ใน sidebar เพื่อทำการวิเคราะห์")




# 🎉 ข้อความขอบคุณธีมน้ำเงิน-ดำ-เทา
st.markdown("""
<hr>

<div style="
    background: linear-gradient(135deg, #0d1117, #1b2735);
    padding: 20px;
    border-radius: 14px;
    text-align: center;
    font-size: 18px;
    border: 1px solid #2d3a4a;
    color: #d6e2f0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.35);
">
~~~~~~~~~~ ขอบคุณที่มาเล่นกันนะ ~~~~~~~~~~
</div>

<hr>
""", unsafe_allow_html=True)
