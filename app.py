"""
Streamlit app: ถ้าหนูถามพี่จะรับปะ (Theme A — Pastel Pink)
Features:
- Python-only (no JS)
- 10 questions per round (random from a bank of 100)
- 10-second timer logic handled server-side as allowed by Streamlit (timeout on rerun)
- Buttons: "รับดิ" / "ไม่รับดีกว่า"
- Leaderboard (SQLite) to store username + cumulative score
- LLM (Google Gemini via google.generativeai) can generate extra questions (optional)
- Import/export questions via CSV/Excel
- Export summary CSV/Excel
- UI styled pastel-pink via CSS
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
except Exception:
    HAVE_GENAI = False

# ----------------- CONFIG -----------------
APP_TITLE = "🎀 ถ้าหนูถามพี่จะรับปะ"
DB_FILENAME = "game_leaderboard.db"
QUESTIONS_FILENAME = "questions_bank.csv"  # auto-save
DEFAULT_MODEL = "gemini-pro"  # example

# ----------------- PAGE SETUP -----------------
st.set_page_config(page_title=APP_TITLE, layout="centered", initial_sidebar_state="expanded")

# Pastel pink styling
st.markdown(
    """
    <style>
    :root{
        --main-bg: #fff7fb;
        --card-bg: #fff0f6;
        --accent: #ff6fb5;
        --muted: #8c6b7b;
    }
    .stApp {
        background: linear-gradient(180deg, var(--main-bg), #fff);
    }
    .card {
        background: var(--card-bg);
        border-radius: 14px;
        padding: 18px;
        box-shadow: 0 6px 18px rgba(247, 174, 211, 0.15);
        border: 1px solid rgba(255,111,181,0.08);
    }
    .question-box {
        background: white;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
        border-left: 6px solid var(--accent);
    }
    .small-muted { color: var(--muted); font-size:12px; }
    .pink-btn { background-color: var(--accent); color: white; border-radius: 10px; padding: 8px 12px; }
    </style>
    """,
    unsafe_allow_html=True
)

st.title(APP_TITLE)
st.write("ธีม: Pastel Pink — UI น่ารัก เหมาะส่งงาน assignment")

# ----------------- SESSION INIT -----------------
def init_session():
    if "questions" not in st.session_state:
        # prepare 100 default fun scenarios
        st.session_state.questions = [
            "พี่ชวนไปเที่ยวทะเล แต่งตัวปิคนิคด้วย — รับปะ?",
            "พี่จะให้ตั๋วหนังสองใบ แต่ต้องดูหนังผีกับพี่ — รับปะ?",
            "พี่ขอให้ช่วยกินซูชิคำสุดท้ายของพี่ — รับปะ?",
            "พี่อยากให้ช่วยเล่นเกมเขินๆ หน้าไลฟ์ — รับปะ?",
            "พี่บอกว่าจะสอนเต้น แต่ต้องเต้นหน้ากล้อง — รับปะ?",
            "พี่ให้ตั๋วคอนเสิร์ตแต่ต้องไปตอนดึก — รับปะ?",
            "พี่จะพาไปคาเฟ่แมว แต่แมวอาจจะข่วน — รับปะ?",
            "พี่สัญญาจะซื้อขนม แต่ต้องกินด้วยกันอย่างเห็นแก่ตัว — รับปะ?",
            "พี่ให้ช่วยแต่งคอมเมนต์หวานๆ ใต้รูปพี่ — รับปะ?",
            "พี่ขอให้ช่วยลองแฟชั่นแปลกๆ หน่อย — รับปะ?",
        ]
        # make 100 by appending numbered fillers
        i = 11
        while len(st.session_state.questions) < 100:
            st.session_state.questions.append(f"สถานการณ์น่าทดลอง ข้อที่ {i} — รับปะ?")
            i += 1

    if "round_questions" not in st.session_state:
        st.session_state.round_questions = []
    if "q_index" not in st.session_state:
        st.session_state.q_index = 0
    if "answers" not in st.session_state:
        st.session_state.answers = []  # list of dicts
    if "start_time" not in st.session_state:
        st.session_state.start_time = None
    if "player" not in st.session_state:
        st.session_state.player = ""
    if "model_name" not in st.session_state:
        st.session_state.model_name = DEFAULT_MODEL
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
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
    # store cumulative: we'll just insert a new row for each play
    c.execute("INSERT INTO leaderboard (player, score, last_played) VALUES (?, ?, ?)", (player, score, ts))
    conn.commit()

def get_leaderboard_df():
    df = pd.read_sql_query("SELECT player, SUM(score) as total_score, MAX(last_played) as last_played FROM leaderboard GROUP BY player ORDER BY total_score DESC", conn)
    return df

# ----------------- HELPERS -----------------
def new_round():
    st.session_state.round_questions = random.sample(st.session_state.questions, 10)
    st.session_state.q_index = 0
    st.session_state.answers = []
    st.session_state.start_time = time.time()
    st.session_state.last_round_score = 0

def record_answer(question, answer, timed_out=False):
    rec = {
        "question": question,
        "answer": answer if answer is not None else "TIMEOUT",
        "timed_out": bool(timed_out),
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }
    st.session_state.answers.append(rec)
    # scoring: answered (not timeout) => 1 point
    if not timed_out and answer is not None:
        st.session_state.last_round_score += 1

def summary_df_from_answers(answers=None):
    if answers is None:
        answers = st.session_state.answers
    if not answers:
        return pd.DataFrame()
    df = pd.DataFrame(answers)
    # pivot counts
    cnt = df.groupby(["question", "answer"]).size().unstack(fill_value=0)
    timed = df[df["timed_out"]==True].groupby("question").size()
    cnt["timed_out"] = timed
    cnt = cnt.fillna(0).astype(int)
    cnt = cnt.reset_index()
    return cnt

# ----------------- SIDEBAR -----------------
st.sidebar.header("ตั้งค่า / Import / LLM")
st.session_state.player = st.sidebar.text_input("ชื่อผู้เล่น (จะเก็บคะแนน)", value=st.session_state.player)
st.session_state.api_key = st.sidebar.text_input("Google Gemini API Key (optional)", type="password", value=st.session_state.api_key)
st.session_state.model_name = st.sidebar.text_input("Model name (example)", value=st.session_state.model_name)

st.sidebar.markdown("**นำเข้าคำถาม** (CSV/Excel) — ต้องมีคอลัมน์ `question`")
uploaded = st.sidebar.file_uploader("อัปโหลดไฟล์คำถาม", type=["csv","xlsx","xls"])
if uploaded:
    try:
        if uploaded.name.lower().endswith(".csv"):
            dfq = pd.read_csv(uploaded)
        else:
            dfq = pd.read_excel(uploaded)
        if "question" in dfq.columns:
            st.session_state.questions = dfq["question"].astype(str).tolist()
            st.sidebar.success(f"โหลดคำถาม {len(st.session_state.questions)} ข้อแล้ว")
            # save to local CSV
            pd.DataFrame({"question": st.session_state.questions}).to_csv(QUESTIONS_FILENAME, index=False)
        else:
            st.sidebar.error("ไฟล์ต้องมีคอลัมน์ชื่อ `question`")
    except Exception as e:
        st.sidebar.error(f"อ่านไฟล์ล้มเหลว: {e}")

# LLM generate questions (optional)
if HAVE_GENAI and st.session_state.api_key:
    try:
        genai.configure(api_key=st.session_state.api_key)
    except Exception:
        st.sidebar.error("ไม่สามารถตั้งค่า API key กับ google.generativeai")
if st.sidebar.button("ให้ AI สร้างคำถามเพิ่ม (10 ข้อ)"):
    if not HAVE_GENAI or not st.session_state.api_key:
        st.sidebar.error("ต้องติดตั้ง google-generativeai และใส่ API key ใน sidebar")
    else:
        # Example prompt to generate 10 playful scenario questions in Thai
        prompt = (
            "สร้างคำถามสถานการณ์สั้นๆ เป็นภาษาไทย จำนวน 10 ข้อ ให้เป็นประโยคเดียวจบ เน้นสนุก ขี้เล่น และลงท้ายด้วย '— รับปะ?' "
            "ตอบเป็น JSON array ของ strings เท่านั้น"
        )
        try:
            resp = genai.generate_text(model=st.session_state.model_name, prompt=prompt, max_output_tokens=800)
            # naive extraction: try parse lines or eval as list
            text = resp.text.strip()
            # attempt to find JSON-like array
            import json
            try:
                arr = json.loads(text)
            except Exception:
                # fallback: split by newline and take non-empty lines
                arr = [line.strip('- ').strip() for line in text.splitlines() if line.strip()]
            # append to question bank
            for q in arr:
                if isinstance(q, str) and q not in st.session_state.questions:
                    st.session_state.questions.append(q)
            st.sidebar.success(f"AI สร้างคำถามเพิ่ม {len(arr)} ข้อ (อาจต้องตรวจสอบความสมเหตุสมผล)")
            # save
            pd.DataFrame({"question": st.session_state.questions}).to_csv(QUESTIONS_FILENAME, index=False)
        except Exception as e:
            st.sidebar.error(f"สร้างคำถามด้วย LLM ล้มเหลว: {e}")

# export questions
if st.sidebar.button("ดาวน์โหลดคำถามปัจจุบัน (CSV)"):
    dfq = pd.DataFrame({"question": st.session_state.questions})
    csv = dfq.to_csv(index=False).encode("utf-8")
    st.sidebar.download_button("Download questions.csv", csv, "questions.csv", "text/csv")

st.sidebar.markdown("---")
st.sidebar.markdown("**ข้อมูล**")
st.sidebar.write(f"คำถามทั้งหมด: {len(st.session_state.questions)}")
st.sidebar.write("โปรดทราบ: Timer เป็นแบบ server-side (ถ้าไม่กดอะไรและไม่มี rerun จะถือว่ารออยู่).")

# ----------------- MAIN UI -----------------
col_left, col_right = st.columns([2,1])

with col_left:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    if st.button("เริ่มรอบใหม่ (สุ่ม 10 ข้อ)", key="newround"):
        new_round()
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    if not st.session_state.round_questions:
        st.info("กด 'เริ่มรอบใหม่' เพื่อเล่น (ระบบจะสุ่ม 10 ข้อให้)")
    else:
        # show progress
        total = 10
        idx = st.session_state.q_index
        st.progress(min(1.0, idx / total))
        # current question
        if idx >= total:
            st.success("🎉 จบรอบแล้ว — ดูสรุปและบันทึกคะแนนด้านล่าง")
        else:
            q = st.session_state.round_questions[idx]
            st.markdown(f'<div class="question-box"><h4>คำถามข้อที่ {idx+1}/{total}</h4><p style="font-size:18px;"><b>{q}</b></p></div>', unsafe_allow_html=True)

            # start time logic
            if st.session_state.start_time is None:
                st.session_state.start_time = time.time()
            elapsed = time.time() - st.session_state.start_time
            remaining = max(0, 10 - int(elapsed))
            st.write(f"⏳ เวลาเหลือ (ประมาณ): **{remaining}** วินาที")
            st.write('<div class="small-muted">หมายเหตุ: ถ้ากดตอบหลังเวลา จะถูกบันทึกเป็น timeout</div>', unsafe_allow_html=True)

            # answer buttons
            a1, a2 = st.columns(2)
            if a1.button("✅ รับดิ"):
                # check timeout
                if elapsed > 10:
                    record_answer(q, None, timed_out=True)
                    st.warning("ตอบช้า — บันทึกเป็น TIMEOUT (0 คะแนน)")
                else:
                    record_answer(q, "รับดิ", timed_out=False)
                    st.success("บันทึก: รับดิ (+1 คะแนน)")
                # prepare next
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()
            if a2.button("❌ ไม่รับดีกว่า"):
                if elapsed > 10:
                    record_answer(q, None, timed_out=True)
                    st.warning("ตอบช้า — บันทึกเป็น TIMEOUT (0 คะแนน)")
                else:
                    record_answer(q, "ไม่รับดีกว่า", timed_out=False)
                    st.success("บันทึก: ไม่รับดีกว่า (+1 คะแนน)")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.rerun()

            # server-side timeout detection on rerun
            if elapsed > 10:
                record_answer(q, None, timed_out=True)
                st.info("หมดเวลา → ข้ามข้อนี้ (บันทึก TIMEOUT)")
                st.session_state.q_index += 1
                st.session_state.start_time = time.time()
                st.experimental_rerun()

with col_right:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🏅 Leaderboard & Score")
    if st.session_state.player:
        st.write(f"ผู้เล่น: **{st.session_state.player}**")
    else:
        st.info("กรอกชื่อผู้เล่นใน sidebar เพื่อบันทึกคะแนน")
    st.write(f"คะแนนรอบนี้ (ปัจจุบัน): **{st.session_state.last_round_score}**")
    if st.button("บันทึกคะแนนรอบนี้"):
        if not st.session_state.player:
            st.warning("กรุณากรอกชื่อผู้เล่นใน sidebar ก่อนบันทึก")
        else:
            update_leaderboard(st.session_state.player, st.session_state.last_round_score)
            st.success(f"บันทึกแล้ว: {st.session_state.player} +{st.session_state.last_round_score} คะแนน")
    st.markdown("**ตารางรวมคะแนน**")
    df_lb = get_leaderboard_df()
    if df_lb.empty:
        st.write("ยังไม่มีคะแนน")
    else:
        st.dataframe(df_lb)

    st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")
st.subheader("📊 สรุปผลการตอบและดาวน์โหลด")

# if round finished, show summary and allow export
if st.session_state.answers:
    df_summary = summary_df_from_answers()
    st.dataframe(df_summary)

    # download summary CSV
    csv = df_summary.to_csv(index=False).encode("utf-8")
    st.download_button("ดาวน์โหลดสรุป (CSV)", csv, "summary.csv", "text/csv")
    # excel
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine="xlsxwriter") as writer:
        df_summary.to_excel(writer, index=False, sheet_name="summary")
        writer.save()
    towrite.seek(0)
    st.download_button("ดาวน์โหลดสรุป (Excel)", towrite, "summary.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.write("ยังไม่มีคำตอบในรอบนี้ — เริ่มรอบแล้วตอบคำถามเพื่อเห็นสรุป")

# quick export of full question bank
st.markdown("---")
st.subheader("🗂️ ข้อมูลคำถาม (Question Bank)")
st.write(f"จำนวนคำถามทั้งหมด: {len(st.session_state.questions)}")
if st.button("บันทึกคำถามลงไฟล์ (questions_bank.csv)"):
    pd.DataFrame({"question": st.session_state.questions}).to_csv(QUESTIONS_FILENAME, index=False)
    st.success(f"บันทึกแล้ว: {QUESTIONS_FILENAME}")
if os.path.exists(QUESTIONS_FILENAME):
    with open(QUESTIONS_FILENAME, "rb") as f:
        st.download_button("ดาวน์โหลด questions_bank.csv", f.read(), file_name=QUESTIONS_FILENAME, mime="text/csv")

st.markdown("---")
st.caption("App นี้ออกแบบมาให้ใช้งานได้ทันทีสำหรับ assignment — Python only, Streamlit-based, มี LLM integration แบบ optional, และมี leaderboard เก็บคะแนน")

# ----------------- CLEANUP / NOTES -----------------
st.markdown("""  
**หมายเหตุสำคัญเกี่ยวกับ Timer / UX (Python-only)**  
- Streamlit ใช้การ rerun เป็นหลัก — ถ้าผู้เล่นไม่กดอะไรเลย ระบบจะไม่สามารถ 'เปลี่ยนหน้า' อัตโนมัติโดยไม่มีการ rerun.  
- โค้ดนี้ใช้แนวปฏิบัติ common สำหรับ assignment: ถ้ากดตอบหลัง 10 วินาที จะถูกบันทึกเป็น TIMEOUT.  
""")
