import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import google.generativeai as genai
import json
import re

# -----------------------------
# Thai translations
# -----------------------------
sentiment_map_th = {
    "positive": "เชิงบวก",
    "negative": "เชิงลบ",
    "neutral": "เป็นกลาง"
}

emotion_map_th = {
    "joy": "สุข",
    "anger": "โกรธ",
    "sadness": "เศร้า",
    "fear": "กลัว",
    "surprise": "ประหลาดใจ",
    "disgust": "ขยะแขยง",
    "neutral": "เป็นกลาง"
}

# -----------------------------
# Fallback rule-based classifier
# -----------------------------
def rule_based_classify(text):
    text_lower = text.lower()

    positive_keywords = ["good", "great", "love", "happy", "excellent", "ดี", "ชอบ", "สุดยอด"]
    negative_keywords = ["bad", "terrible", "hate", "angry", "sad", "แย่", "เกลียด", "โกรธ", "เศร้า"]

    emotions_map = {
        "joy": ["good", "great", "love", "happy", "ดี", "ชอบ"],
        "anger": ["angry", "โกรธ"],
        "sadness": ["sad", "เศร้า"],
        "disgust": ["disgust", "ขยะแขยง"]
    }

    score_pos = sum([1 for w in positive_keywords if w in text_lower])
    score_neg = sum([1 for w in negative_keywords if w in text_lower])

    if score_pos == 0 and score_neg == 0:
        return None  # no strong clue → cannot override

    if score_pos > score_neg:
        sentiment = "positive"
    elif score_neg > score_pos:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    emo = []
    for e, words in emotions_map.items():
        if any(w in text_lower for w in words):
            emo.append(e)

    if not emo:
        emo = ["neutral"]

    reason = f"Rule-based detection: pos={score_pos}, neg={score_neg}"

    return sentiment, emo, reason


# -----------------------------
# Gemini API (real implementation)
# -----------------------------
import google.generativeai as genai
import json, re

def get_available_model(api_key):
    """ดึงชื่อโมเดลจริงจาก API เพื่อป้องกัน 404"""
    genai.configure(api_key=api_key)
    models = genai.list_models()
    
    # เลือกโมเดลที่รองรับ generateContent
    for m in models:
        if "generateContent" in m.supported_generation_methods:
            if "gemini-1.5" in m.name:
                return m.name  # เช่น models/gemini-1.5-flash-001
    
    # fallback
    return "models/gemini-1.5-flash"

def call_gemini(text, api_key):
    try:
        genai.configure(api_key=api_key)

        model_name = get_available_model(api_key)
        model = genai.GenerativeModel(model_name)

        prompt = f"""
You are a multilingual sentiment + emotion classifier (Thai + English).
Classify this text:
{text}

Respond in valid JSON only:
{{
  "sentiment_en": "",
  "sentiment_th": "",
  "emotion_en": "",
  "emotion_th": "",
  "explanation_en": "",
  "explanation_th": ""
}}
"""

        response = model.generate_content(prompt)

        clean = re.sub(r"```json|```", "", response.text).strip()
        return json.loads(clean)

    except Exception as e:
        return {
            "sentiment_en": "neutral",
            "sentiment_th": "เป็นกลาง",
            "emotion_en": "neutral",
            "emotion_th": "เป็นกลาง",
            "explanation_en": f"LLM error: {e}",
            "explanation_th": f"เกิดข้อผิดพลาด: {e}"
        }


# -----------------------------
# Streamlit UI
# -----------------------------
st.set_page_config(page_title="Sentiment & Emotion Dashboard", layout="wide")

st.title("📊 Sentiment + Emotion Dashboard (TH/EN)")

# Sidebar API key
st.sidebar.header("🔑 API Key Settings")
api_key = st.sidebar.text_input("Google Gemini API Key", type="password")

st.sidebar.markdown("---")


# -----------------------------
# Upload or text input
# -----------------------------
st.subheader("Input")

input_type = st.radio("เลือกประเภท input", ["กรอกข้อความ", "อัปโหลดไฟล์ CSV/Excel"])

texts = []

if input_type == "กรอกข้อความ":
    user_text = st.text_area("พิมพ์ข้อความที่ต้องการวิเคราะห์", height=150)
    if user_text.strip():
        texts = [user_text]

else:
    uploaded = st.file_uploader("อัปโหลดไฟล์", type=["csv", "xlsx"])
    if uploaded:
        if uploaded.name.endswith(".csv"):
            df_in = pd.read_csv(uploaded)
        else:
            df_in = pd.read_excel(uploaded)

        if "text" not in df_in.columns:
            st.error("ไฟล์ต้องมีคอลัมน์ชื่อ 'text'")
        else:
            texts = df_in["text"].astype(str).tolist()


# -----------------------------
# Process Button (ENTER)
# -----------------------------
process = st.button("▶ เริ่มประมวลผล", use_container_width=True)

if process:

    if not api_key:
        st.error("กรุณากรอก Gemini API key ที่ sidebar ก่อน")
        st.stop()

    if not texts:
        st.warning("ยังไม่มีข้อมูลให้วิเคราะห์")
        st.stop()

    results = []

    for txt in texts:

        # Call LLM
        result = call_gemini(txt, api_key)

        sentiment = result["sentiment_en"].lower().strip()
        emotion = result["emotion_en"].lower().strip().split(",")
        explanation = result["explanation_en"]

        # If LLM failed or returned neutral → use fallback
        need_rb = False
        if sentiment == "neutral" or emotion == ["neutral"] or "LLM error" in explanation:
            need_rb = True

        if need_rb:
            rb = rule_based_classify(txt)
            if rb is not None:
                s_rb, e_rb, reason_rb = rb
                sentiment = s_rb
                emotion = e_rb
                explanation += f"\n[Rule-based override: {reason_rb}]"

        # Translate Thai
        sentiment_th = f"({sentiment_map_th.get(sentiment, 'เป็นกลาง')})"
        emotion_th = f"({emotion_map_th.get(emotion[0], 'เป็นกลาง')})"

        results.append({
            "text": txt,
            "sentiment_en": sentiment,
            "sentiment_th": sentiment_th,
            "emotion_en": ", ".join(emotion),
            "emotion_th": emotion_th,
            "explanation_en": explanation
        })

    # DataFrame
    df_out = pd.DataFrame(results)
    df_out.index = pd.RangeIndex(start=1, stop=len(df_out) + 1)

    st.subheader("Results")
    st.dataframe(df_out, use_container_width=True)

    # Download CSV
    csv = df_out.to_csv().encode("utf-8-sig")
    st.download_button("Download CSV", csv, "results.csv", "text/csv")

    # -----------------------------
    # Charts
    # -----------------------------
    st.subheader("Charts")

    col1, col2 = st.columns(2)

    # Bar chart for sentiment
    with col1:
        st.write("Sentiment Distribution")
        counts = df_out["sentiment_en"].value_counts()

        fig1 = plt.figure()
        counts.plot(kind="bar")
        plt.title("Sentiment Count")
        plt.ylabel("Frequency")
        st.pyplot(fig1)

    # Pie chart for emotion
    with col2:
        st.write("Emotion Distribution")
        emo_counts = df_out["emotion_en"].value_counts()

        fig2 = plt.figure()
        emo_counts.plot(kind="pie", autopct="%1.1f%%")
        plt.title("Emotions")
        st.pyplot(fig2)

