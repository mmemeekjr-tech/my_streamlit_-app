# app.py
import streamlit as st
import pandas as pd
import random
import time
import io
from datetime import datetime

# ---- Optional: Google Gemini (example) ----
# ให้ติดตั้ง google-generative-ai (pip install google-generative-ai)
# และใน sidebar ผู้ใช้จะใส่ API key ของ Google Gemini (we'll configure inline).
try:
    import google.generativeai as genai
    HAVE_GENAI = True
except Exception:
    HAVE_GENAI = False

# ---------------- Config ----------------
QUESTIONS_DEFAULT = [
    # 100 ตัวอย่างคำถาม (กรุณาปรับแต่งให้สนุก/เหมาะสม)
    "พี่ชวนไปเที่ยวทะเล แต่งตัวปิคนิคด้วย — รับปะ?",
    "พี่จะให้ตั๋วหนังสองใบ แต่ต้องดูหนังผีกับพี่ — รับปะ?",
    "พี่ขอให้ช่วยกินซูชิคำสุดท้ายของพี่ — รับปะ?",
    "พี่ยอมจ่ายขนมให้ แต่ต้องเล่าเรื่องประหลาดของตัวเอง — รับปะ?",
    "พี่จะสอนเต้น TikTok หน่อย แต่ต้องเต้นหน้ากล้อง — รับปะ?",
    "พี่จะให้ฟังเพลงโปรดทั้งอัลบั้มแบบยาว — รับปะ?",
    "พี่จะไปคาเฟ่แมวด้วยกัน — รับปะ?",
    "พี่เอามะม่วงมาแบ่งครึ่งแต่มีแมลงอยู่ข้างใน — รับปะ?",
    "พี่บอกให้ช่วยเลือกชุดสำคัญ แต่ต้องใส่ไอเท็มตลกหนึ่งชิ้น — รับปะ?",
    "พี่จะทำ dinner surprise แต่อาหารแปลก — รับปะ?",
    # (เติมจนครบ 100 — ผมจะทำเป็นตัวอย่าง 100 ข้อสั้น ๆ)
]

# เติมให้ครบ 100 อัน (ถ้ list สั้นกว่ากำหนด จะวนซ้ำ)
while len(QUESTIONS_DEFAULT) < 100:
    QUESTIONS_DEFAULT += [f"สถานการณ์สนุก ๆ ข้อที่ {len(QUESTIONS_DEFAULT)+1} — รับปะ?"]

# ---------------- Helpers ----------------
def init_session():
    if "questions" not in st.session_state:
        st.session_state.questions = QUESTIONS_DEFAULT.copy()
    if "current_round" not in st.session_state:
        st.session_state.current_round = []
    if "round_index" not in st.session_state:
        st.session_state.round_index = 0
    if "answers" not in st.session_state:
        # store dicts: [{q, answer, timestamp, timed_out}]
        st.session_state.answers = []
    if "play_history" not in st.session_state:
        st.session_state.play_history = []  # list of rounds
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "model_name" not in st.session_state:
        st.session_state.model_name = "gemini-pro"  # example
    if "current_question_idx" not in st.session_state:
        st.session_state.current_question_idx = 0
    if "question_start_time" not in st.session_state:
        st.session_state.question_start_time = None

def sample_round(n=10):
    # sample without replacement from full list
    qbank = st.session_state.questions
    return random.sample(qbank, n)

def start_new_round():
    st.session_state.current_round = sample_round(10)
    st.session_state.current_question_idx = 0
    st.session_state.question_start_time = time.time()
    st.session_state.round_index += 1

def record_answer(question, answer, timed_out=False):
    st.session_state.answers.append({
        "question": question,
        "answer": answer,
        "timed_out": timed_out,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "round": st.session_state.round_index
    })

def summarize_df():
    if not st.session_state.answers:
        return pd.DataFrame()
    df = pd.DataFrame(st.session_state.answers)
    # count choices per question
    summary = df.groupby(["question", "answer"]).size().unstack(fill_value=0)
    # add timed_out count
    timed = df[df["timed_out"] == True].groupby("question").size()
    summary["timed_out"] = timed
    summary = summary.fillna(0).astype(int)
    return summary.reset_index()

# ---------------- UI ----------------
st.set_page_config(page_title="ถ้าหนูถามพี่จะรับปะ — Game", layout="wide")
init_session()

# Sidebar: API key, model
st.sidebar.title("ตั้งค่า API (Google Gemini)")
api_key_input = st.sidebar.text_input("วาง Google API Key (หรือ ENV)", type="password",
                                      value=st.session_state.api_key)
model_input = st.sidebar.text_input("Model name (ตัวอย่าง)", value=st.session_state.model_name)
st.sidebar.markdown("**หมายเหตุ**: ต้องติดตั้ง `google-generative-ai` หากต้องการเรียก LLM จาก backend.")

if api_key_input != st.session_state.api_key:
    st.session_state.api_key = api_key_input

st.session_state.model_name = model_input

if HAVE_GENAI and st.session_state.api_key:
    try:
        genai.configure(api_key=st.session_state.api_key)
    except Exception as e:
        st.sidebar.error(f"ไม่สามารถตั้งค่า API key: {e}")

# Top controls
col1, col2, col3 = st.columns([1,1,2])
with col1:
    if st.button("เริ่มรอบใหม่ (สุ่ม 10 ข้อ)"):
        start_new_round()
        st.success("เริ่มรอบใหม่แล้ว — ตอบให้ทัน 10 วินาทีต่อข้อ!")
with col2:
    if st.button("รีเซ็ตผลทั้งหมด"):
        st.session_state.answers = []
        st.session_state.play_history = []
        st.success("รีเซ็ตข้อมูลเรียบร้อย")
with col3:
    st.write(f"รอบที่เล่น: {st.session_state.round_index}")

st.markdown("---")

# Allow user to upload own question bank CSV/Excel
st.sidebar.markdown("**นำเข้าไฟล์คำถาม (CSV / Excel)**")
upload = st.sidebar.file_uploader("อัปโหลดไฟล์ (คอลัมน์: question)", type=["csv","xlsx","xls"])
if upload:
    try:
        if upload.name.endswith(".csv"):
            df_q = pd.read_csv(upload)
        else:
            df_q = pd.read_excel(upload)
        if "question" in df_q.columns:
            st.session_state.questions = df_q["question"].astype(str).tolist()
            st.sidebar.success(f"โหลดคำถามจากไฟล์มา {len(st.session_state.questions)} ข้อ")
        else:
            st.sidebar.error("ไฟล์ต้องมีคอลัมน์ชื่อ `question`")
    except Exception as e:
        st.sidebar.error(f"อ่านไฟล์ไม่สำเร็จ: {e}")

# If no current round, offer to start
if not st.session_state.current_round:
    st.info("กด 'เริ่มรอบใหม่ (สุ่ม 10 ข้อ)' เพื่อเริ่มเล่น")
    st.stop()

# Display current question (one at a time)
idx = st.session_state.current_question_idx
if idx >= len(st.session_state.current_round):
    st.success("จบรอบแล้ว — ผลสรุปด้านล่าง")
    # store round history
    st.session_state.play_history.append({
        "round": st.session_state.round_index,
        "answers": st.session_state.answers[-10:]  # last 10 answers correspond to this round
    })
else:
    question = st.session_state.current_round[idx]
    st.markdown(f"### ข้อที่ {idx+1}/10")
    st.markdown(f"**{question}**")

    # show remaining time (server-side approximation)
    if st.session_state.question_start_time is None:
        st.session_state.question_start_time = time.time()

    elapsed = time.time() - st.session_state.question_start_time
    remaining = max(0, 10 - int(elapsed))
    st.write(f"เวลาเหลือ: **{remaining}** วินาที (ระบบประมาณการ)")

    # Buttons for answers
    col_a, col_b = st.columns(2)
    answered_now = False
    if col_a.button("✅ รับดิ"):
        # check timeout
        elapsed = time.time() - st.session_state.question_start_time
        if elapsed > 10:
            # timed out
            record_answer(question, None, timed_out=True)
            st.warning("ตอบช้า — ข้ามคำถาม (นับเป็น timed out).")
        else:
            record_answer(question, "รับดิ", timed_out=False)
            st.success("เลือก: รับดิ")
        # move to next question
        st.session_state.current_question_idx += 1
        st.session_state.question_start_time = time.time()
        st.experimental_rerun()

    if col_b.button("❌ ไม่รับดีกว่า"):
        elapsed = time.time() - st.session_state.question_start_time
        if elapsed > 10:
            record_answer(question, None, timed_out=True)
            st.warning("ตอบช้า — ข้ามคำถาม (n/a).")
        else:
            record_answer(question, "ไม่รับดีกว่า", timed_out=False)
            st.success("เลือก: ไม่รับดีกว่า")
        st.session_state.current_question_idx += 1
        st.session_state.question_start_time = time.time()
        st.experimental_rerun()

    # If time passed and user didn't click (on any rerun), we auto-timeout here
    # Note: this auto-timeout triggers only when page reruns (e.g., from other button presses or refresh).
    # For deterministic client-side timeout you'd use a JS component (see notes below).
    if elapsed > 10:
        # mark timed out and advance
        record_answer(question, None, timed_out=True)
        st.info("หมดเวลา — ข้ามคำถาม (ถูกบันทึกเป็น timed out).")
        st.session_state.current_question_idx += 1
        st.session_state.question_start_time = time.time()
        st.experimental_rerun()

st.markdown("---")

# Show DataFrame summary
st.subheader("สรุปผล (DataFrame)")
summary = summarize_df()
if summary.empty:
    st.write("ยังไม่มีคำตอบ — เล่นสักรอบแล้วจะเห็นสรุปที่นี่")
else:
    st.dataframe(summary)

    # download buttons
    csv = summary.to_csv(index=False).encode("utf-8")
    st.download_button("ดาวน์โหลด CSV", data=csv, file_name="summary.csv", mime="text/csv")

    # Excel
    towrite = io.BytesIO()
    with pd.ExcelWriter(towrite, engine="xlsxwriter") as writer:
        summary.to_excel(writer, index=False, sheet_name="summary")
        writer.save()
    towrite.seek(0)
    st.download_button("ดาวน์โหลด Excel", data=towrite, file_name="summary.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

# Option: send aggregated results to LLM (example prompt)
st.markdown("---")
st.subheader("วิเคราะห์ผลด้วย LLM (ตัวอย่าง)")

if not HAVE_GENAI:
    st.info("ถ้าต้องการเรียก Google Gemini ให้ติดตั้ง `google-generative-ai` และให้ใส่ API key ใน sidebar")
else:
    if st.button("เรียก LLM สรุปแนวโน้มจากคำตอบล่าสุด"):
        # Make a prompt that asks LLM to summarize the most popular choices and craft 3 fun insights
        df_small = summary.copy().head(20).to_dict(orient="records")
        prompt = (
            "ฉันมีสรุปตารางคำถาม-คำตอบ (question + counts of choices). โปรดสรุปใจความสำคัญ 3 ข้อแบบเป็นภาษาไทย "
            "และให้คำแนะนำเชิงสร้างสรรค์ 3 ข้อสำหรับปรับคำถามให้น่าสนใจขึ้น (short bullets). "
            f"ตาราง: {df_small}"
        )
        try:
            resp = genai.generate_text(model=st.session_state.model_name, prompt=prompt, max_output_tokens=512)
            st.markdown("**LLM สรุป:**")
            st.write(resp.text)
        except Exception as e:
            st.error(f"เรียก LLM ไม่สำเร็จ: {e}")

st.markdown("---")
st.caption("App ตัวอย่าง — ปรับแต่งคำถาม/UX/การเรียก LLM ให้เหมาะสมกับ assignment ได้ตามต้องการ.")
