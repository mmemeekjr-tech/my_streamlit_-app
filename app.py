# app.py
import streamlit as st
import random
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

# -----------------------
# Config & Helpers
# -----------------------
DATA_FILE = Path("decisions.json")

st.set_page_config(
    page_title="Will You Accept? 🎲",
    page_icon="🤔",
    layout="centered",
)

# Initialize session state
if "history" not in st.session_state:
    st.session_state.history = []
if "current" not in st.session_state:
    st.session_state.current = None
if "accepted_streak" not in st.session_state:
    st.session_state.accepted_streak = 0
if "rejected_streak" not in st.session_state:
    st.session_state.rejected_streak = 0

# Load persistent history if exists
def load_data():
    if DATA_FILE.exists():
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_data(history):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        st.warning(f"ไม่สามารถบันทึกไฟล์ได้: {e}")

# Scenario building
PERSONA = [
    "เพื่อนซี้", "เจ้านายสุดโหด", "แม่ของเพื่อน", "คนแปลกหน้าในคาเฟ่", "AI ในอนาคต", "คุณยายที่ชอบเล่าเรื่อง"
]

BENEFITS = [
    "ได้รับเงิน {amount} บาททันที",
    "ตั๋วเครื่องบินไป-กลับประเทศที่คุณอยากไป",
    "ขนมฟรีตลอดเดือน",
    "สิทธิ์ซื้อของลด 90% หนึ่งครั้ง",
    "โอกาสได้เล่นเกมเวทีทีวี (ถ้าชนะได้เงินแสน)",
    "โอกาสได้พบคนมีชื่อเสียงสักหนึ่งครั้ง"
]

COSTS = [
    "ต้องทำงาน 7 วันติดโดยไม่มีวันหยุด",
    "ต้องเลี้ยงหมาที่ไม่ได้อาบน้ำเป็นเวลา 3 เดือน",
    "ห้ามใช้โทรศัพท์ 24 ชั่วโมงทุกสัปดาห์เป็นเวลา 1 เดือน",
    "ต้องกินเผ็ดทุกมื้อเป็นเวลา 2 สัปดาห์",
    "ต้องสวมชุดแฟนซีที่เขาเลือกให้ไปทำงานหนึ่งวัน",
    "ต้องยอมรับให้คนแปลกหน้าส่งของถึงบ้านทุกสัปดาห์เป็นเวลา 2 เดือน"
]

WEIRD = [
    "แต่ทุกครั้งที่พูดคำว่า 'สวัสดี' จะมีเสียงหัวเราะในห้องดังขึ้น",
    "แต่จะมีนกชอบมานอนบนหมวกคุณทุกเช้า",
    "แต่คุณจะลืมชื่อเพลงที่กำลังฮิตอยู่ตอนนี้",
    "แต่รองเท้าจะกลายเป็นสีชมพูในตอนเที่ยงคืน",
    "แต่ทุกภาพถ่ายจากโทรศัพท์จะมีรอยนิ้วมือที่มองไม่เห็น",
    "แต่คุณจะฝันว่ากินข้าวกล่องทุกคืน"
]

TEMPLATES = [
    "มีคนเสนอว่า {benefit} ให้คุณ {cost}. {weird}",
    "{persona} บอกว่า: '{benefit} แลกกับ {cost}'.",
    "โอกาสแบบนี้มีครั้งเดียว: {benefit}. ข้อแม้: {cost}. {weird}"
]

def generate_scenario(surprise=False, difficulty=1):
    persona = random.choice(PERSONA)
    benefit_template = random.choice(BENEFITS)
    cost_template = random.choice(COSTS)
    weird_template = random.choice(WEIRD)

    # vary amounts based on difficulty
    if "{amount}" in benefit_template:
        base = random.choice([500, 1000, 5000, 10000, 50000])
        amount = int(base * (1 + difficulty * 0.6))
        benefit = benefit_template.format(amount=amount)
    else:
        benefit = benefit_template

    if surprise:
        # mix more weird items
        weird = "และ " + " ".join(random.sample(WEIRD, k=2))
    else:
        weird = weird_template

    # sometimes add an extra constraint if difficulty higher
    if difficulty >= 3:
        # append a second cost
        extra_cost = random.choice(COSTS)
        cost = f"{cost_template} และ {extra_cost}"
    else:
        cost = cost_template

    template = random.choice(TEMPLATES)
    scenario = template.format(persona=persona, benefit=benefit, cost=cost, weird=weird)
    return scenario

# -----------------------
# UI layout
# -----------------------
st.markdown("""
<style>
.big-title {font-size:34px; font-weight:700;}
.scenario {background: linear-gradient(90deg,#fff7f0,#fff3f8); padding:18px; border-radius:12px; margin-top:10px;}
.buttons-row > div {display:inline-block; margin-right:10px;}
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="big-title">จะรับไหม? — Will You Accept? 🤔🎲</div>', unsafe_allow_html=True)
st.caption("กดปุ่มเพื่อสุ่มสถานการณ์ แล้วตัดสินใจว่าจะรับหรือไม่รับ — จะรับไหม? มาเล่นกับเพื่อนด้วยกันได้เลย 🎉")

col1, col2 = st.columns([3,1])
with col2:
    surprise = st.checkbox("Surprise mode (สถานการณ์แปลก)", value=False, help="เพิ่มความประหลาดให้สถานการณ์")
    difficulty = st.slider("Difficulty", min_value=1, max_value=4, value=1, help="ยิ่งสูงยิ่งมีข้อผูกมัดมากกว่า")
    if st.button("สุ่มสถานการณ์ใหม่ 🔄", key="new"):
        st.session_state.current = generate_scenario(surprise=surprise, difficulty=difficulty)

with col1:
    if st.session_state.current is None:
        st.session_state.current = generate_scenario(surprise=surprise, difficulty=difficulty)

    st.markdown(f'<div class="scenario"><strong>สถานการณ์:</strong><div style="margin-top:8px; font-size:18px;">{st.session_state.current}</div></div>', unsafe_allow_html=True)

# Decision buttons
cola, colb, colc = st.columns([1,1,1])
with cola:
    if st.button("✅ รับ", key="accept"):
        record = {
            "timestamp": datetime.now().isoformat(),
            "scenario": st.session_state.current,
            "decision": "accept",
            "difficulty": difficulty,
            "surprise": surprise
        }
        st.session_state.history.append(record)
        # update streaks
        st.session_state.accepted_streak += 1
        st.session_state.rejected_streak = 0
        save_data(st.session_state.history)

        # new scenario right away
        st.session_state.current = generate_scenario(surprise=surprise, difficulty=difficulty)
        st.experimental_rerun()

with colb:
    if st.button("❌ ไม่รับ", key="reject"):
        record = {
            "timestamp": datetime.now().isoformat(),
            "scenario": st.session_state.current,
            "decision": "reject",
            "difficulty": difficulty,
            "surprise": surprise
        }
        st.session_state.history.append(record)
        st.session_state.rejected_streak += 1
        st.session_state.accepted_streak = 0
        save_data(st.session_state.history)

        st.session_state.current = generate_scenario(surprise=surprise, difficulty=difficulty)
        st.experimental_rerun()

with colc:
    if st.button("❤️ แชร์ผล", key="share"):
        # prepare share text
        share_text = f"ฉันเจอสถานการณ์นี้: {st.session_state.current}\nแล้วฉันเลือก: — คุณลองเล่นดูสิ!"
        st.success("ข้อความแชร์ถูกสร้างด้านล่าง — กดคัดลอกหรือดาวน์โหลดได้เลย")
        st.session_state.share_text = share_text

# Display share area if exists
if "share_text" in st.session_state:
    st.text_area("ข้อความที่จะแชร์ (คัดลอกได้เลย):", value=st.session_state.share_text, height=100)
    st.download_button("ดาวน์โหลดข้อความ (.txt)", data=st.session_state.share_text, file_name="will_you_accept_share.txt")

# -----------------------
# Stats
# -----------------------
st.markdown("---")
st.subheader("สถิติของคุณ 📊")

# combine session history + saved file to ensure persistent
persistent = load_data()
# if session history empty but persistent has data, load it
if st.session_state.history == [] and persistent:
    st.session_state.history = persistent

df = pd.DataFrame(st.session_state.history)
if df.empty:
    st.info("ยังไม่มีการตัดสินใจเลย — กด 'รับ' หรือ 'ไม่รับ' เพื่อเริ่มเล่น!")
else:
    # basic counts
    total = len(df)
    accepts = (df["decision"] == "accept").sum()
    rejects = (df["decision"] == "reject").sum()
    st.metric("จำนวนการตัดสินใจรวม", total)
    st.metric("รับ", f"{accepts} ✅", delta=f"{round(accepts/total*100,1)}%")
    st.metric("ไม่รับ", f"{rejects} ❌", delta=f"{round(rejects/total*100,1)}%")

    # decisions over time
    df_time = df.copy()
    df_time["timestamp"] = pd.to_datetime(df_time["timestamp"])
    df_time = df_time.set_index("timestamp")
    counts = df_time["decision"].resample("D").apply(lambda x: (x=="accept").sum())
    st.line_chart(counts.rename("จำนวนรับต่อวัน"))

    # pie chart for decision distribution
    dist = df["decision"].value_counts()
    st.bar_chart(dist)

    # streaks
    st.write(f"สตรีครับปัจจุบัน: {st.session_state.accepted_streak} 🔥  |  สตรีคไม่รับ: {st.session_state.rejected_streak} ❄️")

    # history table (most recent first)
    st.subheader("ประวัติการตัดสินใจ (ล่าสุดด้านบน)")
    st.dataframe(df.sort_values("timestamp", ascending=False).reset_index(drop=True))

    # download CSV
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("ดาวน์โหลดประวัติเป็น CSV", csv, "will_you_accept_history.csv", "text/csv")

# -----------------------
# Useful tips & extras
# -----------------------
st.markdown("---")
with st.expander("คำแนะนำ / วิธีเล่น (กดดู)"):
    st.markdown("""
- เล่นกับเพื่อนได้: ให้เพื่อนทายว่าคุณจะรับหรือไม่รับ แล้วเทียบกับการตัดสินใจจริง\n
- ปรับ **Difficulty** ให้สถานการณ์ยากขึ้น ถ้าชอบ drama\n
- เปิด **Surprise mode** เพื่อเพิ่มความแปลกประหลาด (ไว้ใช้ตอนอยากฮา)\n
- ดาวน์โหลดประวัติแล้วเอาไปทำ dataset สร้าง challenge แบบกลุ่มได้\n
    """)
