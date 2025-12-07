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
"""

import streamlit as st
import pandas as pd
import random
import time
import sqlite3
from datetime import datetime
import io
import os
import xlsxwriter  # required by pandas ExcelWriter engine

# Optional: Gemini (google.generativeai)
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except Exception:
    HAVE_GENAI = False

# ----------------- CONFIG -----------------
APP_TITLE = "ถ้าหนูถามพี่จะรับปะ?"
DB_FILENAME = "game_leaderboard.db"
QUESTIONS_FILENAME = "questions_bank.csv"
DEFAULT_MODEL = "gemini-pro"

# ----------------- PAGE SETUP -----------------
st.set_page_config(page_title=APP_TITLE, layout="centered", initial_sidebar_state="expanded")

# Blue/Dark styling
st.markdown("""
<style>
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
</style>
""", unsafe_allow_html=True)

st.title(f"🎮 {APP_TITLE}")
st.write("ธีม: Blue / Dark — เล่นง่าย ส่งงานได้ทันที")

# ----------------- QUESTIONS: 100 แบบจริง ๆ -----------------
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

# ----------------- DATABASE (SQLite) -----------------
def init_db():
    conn = sqlite3.connect(DB_FILENAME, check_same_thread=False)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS leaderboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player TEXT,
        score INTEGER,
        last_played TEXT
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
    if not timed_out and answer is not None:
        st.session_state.last_round_score += 1

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
        return ("🔥 กล้าเสี่ยง (Risk-taker)", "คุณค่อนข้างกล้า 'ได้ดิ' บ่อย — เปิดใจลองสิ่งใหม่ๆ เยอะ")
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
st.sidebar.subheader("นำเข้าคำถาม (CSV)")
upload = st.sidebar.file_uploader("อัปโหลดไฟล์คำถาม (ต้องมีคอลัมน์ 'question')", type=["csv", "xlsx"])
if upload is not None:
    try:
        dfq = pd.read_csv(upload) if upload.name.lower().endswith(".csv") else pd.read_excel(upload)
        if "question" in dfq.columns:
            st.session_state.questions = dfq["question"].astype(str).tolist()
            dfq.to_csv(QUESTIONS_FILENAME, index=False)
