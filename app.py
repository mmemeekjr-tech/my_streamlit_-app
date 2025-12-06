import streamlit as st
import pandas as pd
import time
import json
from openai import OpenAI
import google.generativeai as genai

# -----------------------------
# Sidebar: API Keys
# -----------------------------
st.sidebar.title("🔑 API Settings")

openai_key = st.sidebar.text_input("OpenAI API Key", type="password")
gemini_key = st.sidebar.text_input("Google Gemini API Key", type="password")

# Validate API
if openai_key:
    openai_client = OpenAI(api_key=openai_key)

if gemini_key:
    genai.configure(api_key=gemini_key)

st.title("🎮 เกม: ถ้าหนูถามพี่จะรับปะ?")
st.markdown("**ตอบคำถามสถานการณ์สนุก ๆ ภายใน 10 วินาที**")


# -----------------------------
# Load Prompt Template
# -----------------------------
def load_prompt():
    with open("questions_prompt.txt", "r", encoding="utf-8") as f:
        return f.read()

prompt_template = load_prompt()


# -----------------------------
# Generate Questions with LLM
# -----------------------------
def generate_questions_with_llm():
    """Generate 10 NLP questions using OpenAI or Gemini."""
    try:
        response = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt_template}]
        )
        text = response.choices[0].message.content
        questions = json.loads(text)
        return questions
    except Exception:
        # fallback to Gemini
        model = genai.GenerativeModel("gemini-pro")
        response = model.generate_content(prompt_template)
        questions = json.loads(response.text)
        return questions


# -----------------------------
# Game Session
# -----------------------------
if "questions" not in st.session_state:
    st.session_state.questions = None
    st.session_state.answers = []
    st.session_state.index = 0


if st.button("เริ่มเกม 🎯"):
    if not openai_key and not gemini_key:
        st.error("กรุณาใส่อย่างน้อย 1 API Key ก่อนเริ่มเกม!")
    else:
        st.session_state.questions = generate_questions_with_llm()
        st.session_state.answers = []
        st.session_state.index = 0
        st.success("เริ่มเกมแล้ว! เลื่อนลงด้านล่างเพื่อเล่น")


# -----------------------------
# Show Question Section
# -----------------------------
if st.session_state.questions:

    q_index = st.session_state.index

    if q_index < len(st.session_state.questions):
        q = st.session_state.questions[q_index]

        st.subheader(f"ข้อ {q['id']}: {q['question']}")

        # --------------------
        # Countdown Timer
        # --------------------
        start = time.time()
        placeholder = st.empty()

        for sec in range(10, 0, -1):
            placeholder.info(f"⏳ เหลือเวลา {sec} วินาที")
            time.sleep(1)
        placeholder.empty()

        # --------------------
        # Answer Buttons
        # --------------------
        col1, col2 = st.columns(2)
        clicked = st.session_state.get("clicked", False)

        if not clicked:
            with col1:
                if st.button("รับก็ 👍"):
                    st.session_state.answers.append(
                        {"question": q["question"], "answer": "รับก็",
                         "time_used": round(time.time() - start, 2), "skipped": False}
                    )
                    st.session_state.clicked = True
            with col2:
                if st.button("ไม่รับดีกว่า 👎"):
                    st.session_state.answers.append(
                        {"question": q["question"], "answer": "ไม่รับดีกว่า",
                         "time_used": round(time.time() - start, 2), "skipped": False}
                    )
                    st.session_state.clicked = True

        # Auto skip if timeout
        if not clicked:
            st.warning("หมดเวลา! ข้ามข้อนี้ไปเลยนะ")
            st.session_state.answers.append(
                {"question": q["question"], "answer": None,
                 "time_used": None, "skipped": True}
            )

        if st.session_state.clicked or True:
            st.session_state.index += 1
            st.session_state.clicked = False
            st.rerun()

    else:
        st.success("🎉 จบเกมแล้ว!")
        df = pd.DataFrame(st.session_state.answers)
        st.dataframe(df)

        # Download CSV
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("ดาวน์โหลดผลลัพธ์ CSV", csv, "results.csv")

        # Download Excel
        excel = df.to_excel("results.xlsx", index=False)
        with open("results.xlsx", "rb") as f:
            st.download_button("ดาวน์โหลดผลลัพธ์ Excel", f, "results.xlsx")

        # Analyze Personality
        if openai_key:
            analysis_prompt = f"""
วิเคราะห์บุคลิกจากการเล่นเกมนี้ จากข้อมูล: {df.to_dict()}    
สรุปแบบสนุก ๆ และตรงไปตรงมา ไม่ต้องยาวมาก
"""
            res = openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": analysis_prompt}]
            )
            st.subheader("🧠 ผลวิเคราะห์บุคลิก")
            st.write(res.choices[0].message.content)
