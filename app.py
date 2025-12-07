"""
Streamlit app: ถ้าหนูถามพี่จะรับปะ? (Blue/Dark Theme)
Features:
- Python only
- 10 questions per round (random from question bank)
- 10-second timeout
- Buttons: รับดิ / ไม่รับดีกว่า
- Leaderboard (SQLite)
- Import/export questions
- Export summary CSV/Excel
- Optional Gemini API
"""

import streamlit as st
import pandas as pd
import random
import time
import sqlite3
from datetime import datetime
import io
import os

# Optional: Gemini
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except:
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

# ----------------- SESSION INIT -----------------
def init_session():
    if "questions" not in st.session_state:
        # Only REAL questions (no dummy “สถานการณ์ทดลอง…”)
        st.session_state.questions = [
            "พี่ชวนไปทะเลแต่ต้องใส่ชุดคู่ — รับปะ?",
            "พี่ให้ตั๋วหนังสองใบ แต่ต้องนั่งติดพี่ — รับปะ?",
            "พี่ให้ช่วยกินซูชิคำสุดท้ายของพี่ — รับปะ?",
            "พี่อยากให้ช่วยเล่นเกมหน้าไลฟ์ — รับปะ?",
            "พี่จะสอนเต้นท่าเขิน ๆ — รับปะ?",
            "พี่จะพาไปร้านกาแฟเปิดใหม่ — รับปะ?",
            "พี่ขอให้ช่วยเลือกเสื้อผ้าแบบใกล้ชิด — รับปะ?",
            "พี่ให้พาไปส่งบ้านตอนดึก — รับปะ?",
            "พี่อยากให้ช่วยถ่ายรูปคู่น่ารัก ๆ — รับปะ?",
            "พี่ชวนไปเดินห้างตอนวาเลนไทน์ — รับปะ?",
        ]

        # Load bank file if exists (override)
        if os.path.exists(QUESTIONS_FILENAME):
            try:
                df = pd.read_csv(QUESTIONS_FILENAME)
                if "question" in df.columns:
                    st.session_state.questions = df["question"].astype(str).tolist()
            except:
                pass

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
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "model_name" not in st.session_state:
        st.session_state.model_name = DEFAULT_MODEL
    if "last_round_score" not in st.session_state:
        st.session_state.last_round_score = 0

init_session()


# ----------------- DATABASE -----------------
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
    st.session_state.round_questions = random.sample(st.session_state.questions, 10)
    st.session_state.q_index = 0
    st.session_state.answers = []
    st.session_state.start_time = time.time()
    st.session_state.last_round_score = 0

def record_answer(question, answer, timed_out=False):
    st.session_state.answers.append({
        "question": question,
        "answer": answer if answer else "TIMEOUT",
        "timed_out": bool(timed_out),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    })

    if not timed_out and answer is not None:
        st.session_state.last_round_score += 1

def summary_df_from_answers():
    if not st.session_state.answers:
        return pd.DataFrame()
    df = pd.DataFrame(st.session_state.answers)
    cnt = df.groupby(["question", "answer"]).size().unstack(fill_value=0)
    return cnt.reset_index()


# ----------------- SIDEBAR -----------------
st.sidebar.header("ตั้งค่าเกม")
st.session_state.player = st.sidebar.text_input("ชื่อผู้เล่น", value=st.session_state.player)

st.sidebar.subheader("นำเข้าคำถาม")
upload = st.sidebar.file_uploader("อัปโหลดไฟล์คำถาม (CSV/Excel)", type=["csv", "xlsx"])
if upload:
    dfq = pd.read_csv(upload) if upload.name.endswith(".csv") else pd.read_excel(upload)
    if "question" in dfq.columns:
        st.session_state.questions = dfq["question"].astype(str).tolist()
        dfq.to_csv(QUESTIONS_FILENAME, index=False)
        st.sidebar.success("โหลดคำถามสำเร็จ!")
    else:
        st.sidebar.error("ต้องมีคอลัมน์ชื่อ question")


# ----------------- MAIN UI -----------------
colL, colR = st.columns([2,1])

with colL:
    st.markdown('<div class="card">', unsafe_allow_html=True)

    if st.button("เริ่มรอบใหม่ (สุ่ม 10 ข้อ)"):
        new_round()
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

    if not st.session_state.round_questions:
        st.info("กด 'เริ่มรอบใหม่' เพื่อเริ่มเล่น")
    else:
        idx = st.session_state.q_index
        total = 10
        st.progress(idx/total)

        if idx >= total:
            st.success("✔ จบรอบแล้ว ดูสรุปด้านล่าง")
        else:
            q = st.session_state.round_questions[idx]

            st.markdown(f'<div class="question-box"><h4>ข้อที่ {idx+1}/{total}</h4><p>{q}</p></div>',
                        unsafe_allow_html=True)

            # timer
            if st.session_state.start_time is None:
                st.session_state.start_time = time.time()

            elapsed = time.time() - st.session_state.start_time
            remain = max(0, 10 - int(elapsed))
            st.write(f"⏳ เหลือเวลา {remain} วินาที")

            a1, a2 = st.columns(2)
            if a1.button("รับดิ"):
                if elapsed > 10:
                    record_answer(q, None, True)
                else:
                    record_answer(q, "รับดิ")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()

            if a2.button("ไม่รับดีกว่า"):
                if elapsed > 10:
                    record_answer(q, None, True)
                else:
                    record_answer(q, "ไม่รับดีกว่า")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()

            if elapsed > 10:
                record_answer(q, None, True)
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()


with colR:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏆 Leaderboard")
    if st.session_state.player:
        st.write(f"ผู้เล่น: {st.session_state.player}")
    st.write(f"คะแนนรอบนี้: {st.session_state.last_round_score}")

    if st.button("บันทึกคะแนน"):
        if st.session_state.player:
            update_leaderboard(st.session_state.player, st.session_state.last_round_score)
            st.success("บันทึกคะแนนสำเร็จ!")
        else:
            st.warning("กรุณากรอกชื่อผู้เล่น")

    df_lb = get_leaderboard_df()
    st.dataframe(df_lb)
    st.markdown('</div>', unsafe_allow_html=True)


# ----------------- SUMMARY -----------------
st.subheader("📊 สรุปผลรอบนี้")
if st.session_state.answers:
    df_sum = summary_df_from_answers()
    st.dataframe(df_sum)

    # export CSV
    csv = df_sum.to_csv(index=False).encode("utf-8")
    st.download_button("ดาวน์โหลดสรุป (CSV)", csv, "summary.csv", "text/csv")

    # export Excel
    bio = io.BytesIO()
    with pd.ExcelWriter(bio, engine="xlsxwriter") as w:
        df_sum.to_excel(w, index=False, sheet_name="summary")
    bio.seek(0)
    st.download_button("ดาวน์โหลดสรุป (Excel)", bio, "summary.xlsx",
                       "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("ยังไม่มีคำตอบ — เริ่มรอบใหม่ก่อน!")


# ----------------- QUESTION BANK -----------------
st.subheader("📘 Question Bank")
st.write(f"จำนวนคำถาม: {len(st.session_state.questions)}")

if st.button("บันทึกคำถามเป็นไฟล์"):
    pd.DataFrame({"question": st.session_state.questions}).to_csv(QUESTIONS_FILENAME, index=False)
    st.success("บันทึกคำถามแล้ว!")

if os.path.exists(QUESTIONS_FILENAME):
    with open(QUESTIONS_FILENAME, "rb") as f:
        st.download_button("ดาวน์โหลด questions_bank.csv", f.read(),
                           file_name=QUESTIONS_FILENAME, mime="text/csv")
