# Sentiment + Emotion Dashboard (Streamlit)
# Features:
# - Accepts Thai and English input (text area or CSV/XLSX upload)
# - Sidebar for API keys (OpenAI and Google Gemini)
# - Option to choose backend LLM (openai or gemini)
# - Button "Enter" to start processing
# - Uses LLM to classify sentiment (pos/neg/neu) and emotion (joy, anger, sadness, neutral, etc.)
# - Shows English results with Thai translations in parentheses
# - Displays pandas DataFrame, allows download and plots (bar & pie)
# - Includes short explanations from LLM

import streamlit as st
import pandas as pd
import io
import os
import time
import json
import math
from typing import List, Dict, Any
import matplotlib.pyplot as plt
from collections import Counter

# Optional: import openai if available
try:
    import openai
    OPENAI_INSTALLED = True
except Exception:
    OPENAI_INSTALLED = False

# -----------------------------
# Utility functions
# -----------------------------

def translate_label_to_th(label: str) -> str:
    """Simple translations for sentiment/emotion labels to Thai."""
    s = label.lower()
    mapping = {
        'positive': 'บวก',
        'negative': 'ลบ',
        'neutral': 'เป็นกลาง',
        'pos': 'บวก',
        'neg': 'ลบ',
        'joy': 'ยินดี/ดีใจ',
        'anger': 'โกรธ',
        'sadness': 'เศร้า',
        'fear': 'กลัว',
        'surprise': 'ประหลาดใจ',
        'disgust': 'รังเกียจ',
        'neutral_emotion': 'เป็นกลาง'
    }
    return mapping.get(s, '')


def safe_parse_json(s: str) -> Any:
    # Try direct json loads, otherwise try to extract a json-looking substring.
    try:
        return json.loads(s)
    except Exception:
        # find first { and last }
        try:
            start = s.index('{')
            end = s.rindex('}')
            return json.loads(s[start:end+1])
        except Exception:
            return None

# -----------------------------
# LLM wrappers (OpenAI & Gemini placeholders)
# -----------------------------

def build_prompt_for_single(text: str) -> str:
    """Prompt asks the model to return a JSON with fields:
       sentiment (positive/negative/neutral),
       emotion (choose one or more from joy, anger, sadness, fear, surprise, disgust, neutral),
       explanation: short reason in English and Thai separately.
    """
    p = f"""
You are an assistant that reads a single short user text (can be Thai or English) and outputs a JSON only, with these fields:
- sentiment: one of [positive, negative, neutral]
- emotion: one or more emotions from [joy, anger, sadness, fear, surprise, disgust, neutral]
- explanation_en: a short (1-2 sentence) explanation in English why you chose the sentiment/emotion
- explanation_th: the same explanation in Thai

Return STRICT JSON only, with keys exactly as above. Do not return any extra text.

User text: """ + text + """
"""
    return p


def call_openai_chat_completion(api_key: str, prompt: str, model: str = 'gpt-4o-mini') -> str:
    """Call OpenAI ChatCompletion. Requires openai package and API key.
       This function is a best-effort example and may need adjustment depending on the OpenAI SDK version.
    """
    if not OPENAI_INSTALLED:
        raise RuntimeError("openai package not installed")
    openai.api_key = api_key
    # We'll use the chat completions interface (older/newer kits may differ)
    messages = [{"role": "user", "content": prompt}]
    resp = openai.ChatCompletion.create(model=model, messages=messages, temperature=0)
    # extract text
    try:
        return resp['choices'][0]['message']['content']
    except Exception:
        return str(resp)


def call_gemini_placeholder(api_key: str, prompt: str, model: str = 'gemini-pro') -> str:
    """Placeholder for calling Google Gemini API.
       The real Google Gemini REST call requires proper auth (OAuth2 or API key), an endpoint,
       and up-to-date client libraries. Replace this function body with actual request logic
       (e.g., using google-auth and googleapiclient or the official gemini-client when available).

       For now this function raises NotImplementedError so students know to implement it for their environment.
    """
    raise NotImplementedError("Please implement call_gemini_placeholder() with your project's Gemini call.\n"
                              "Typical approach: use google-auth to create credentials, then call the models.generate endpoint\n"
                              "and return the text result. See Google's official docs for the current client usage.")

# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title="Sentiment + Emotion Dashboard", layout='wide')
st.title("Sentiment + Emotion Dashboard")
st.markdown("รับ input ภาษาไทยและอังกฤษ — แสดงผลภาษาอังกฤษและภาษาไทย (ในวงเล็บ)")

# Sidebar: API keys and settings
with st.sidebar:
    st.header("API keys & Settings")
    openai_key = st.text_input("OpenAI API key (for optional OpenAI backend)", value="", type="password")
    gemini_key = st.text_input("Google Gemini API key / token (optional)", value="", type="password")
    backend = st.selectbox("LLM backend", options=["openai", "gemini"], index=0)
    model_choice = st.text_input("Model (backend-specific)", value="gpt-4o-mini" if backend=='openai' else "gemini-pro")
    st.markdown("---")
    st.write("Tips:")
    st.write("• ใส่ API key ในช่องที่เกี่ยวข้อง ถ้าใช้ Gemini ให้กรอก gemini key และเลือก backend เป็น gemini")
    st.write("• ถ้าไม่มี key ใส่ไว้ แต่ยังอยากทดสอบ ให้ใช้ตัวอย่างสั้นๆ ในหน้าเว็บ")

# Input area
st.subheader("Input")
col1, col2 = st.columns([2,1])
with col1:
    uploaded_file = st.file_uploader("Upload CSV or Excel (optional)", type=['csv','xlsx','xls'])
    text_input = st.text_area("Or paste / type text (one review per line)", height=200)
    # Provide an example
    if st.checkbox("Use example data"):
        example_texts = [
            "I love this product! It's fantastic and arrived quickly.",
            "แย่มาก ใช้ไม่ได้เลย เสียเวลาและเงิน", 
            "The food was okay, not great but not bad either.",
            "บริการดี แต่ราคาสูงเกินไป"
        ]
        text_input = "\n".join(example_texts)

with col2:
    st.write("Config")
    text_column_name = st.text_input("If file uploaded: column name containing texts (leave empty to auto-detect)", value="")
    sample_n = st.number_input("Preview rows (max)", min_value=1, max_value=1000, value=5)

st.markdown("---")

# The Enter button to start processing
start_processing = st.button("Enter — Start processing")

# Load texts from uploaded file if present
texts: List[str] = []
original_df = None
if uploaded_file is not None:
    try:
        if uploaded_file.type == 'text/csv' or uploaded_file.name.lower().endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
        original_df = df.copy()
        st.write(f"Uploaded file shape: {df.shape}")
        # detect column
        if text_column_name and text_column_name in df.columns:
            texts = df[text_column_name].astype(str).fillna("").tolist()
        else:
            # try to auto detect a likely column
            candidates = [c for c in df.columns if df[c].dtype == object or df[c].dtype == "string"]
            if len(candidates) == 0:
                st.warning("Cannot find a text column automatically. Please enter the column name.")
            else:
                chosen = candidates[0]
                st.info(f"Auto-detected text column: {chosen} — change the column name in config to override")
                texts = df[chosen].astype(str).fillna("").tolist()
    except Exception as e:
        st.error(f"Failed to read uploaded file: {e}")

# If no uploaded file, read from text area (split by lines)
if uploaded_file is None and text_input.strip():
    # treat each non-empty line as separate example
    lines = [l.strip() for l in text_input.splitlines() if l.strip()]
    texts = lines

# Preview
if texts:
    st.subheader("Preview of inputs")
    st.write(pd.DataFrame({'text': texts[:sample_n]}))
else:
    st.info("No input yet. Upload a CSV/Excel or paste text (one per line) and then press Enter to start.")

# Main processing
if start_processing:
    if not texts:
        st.error("No texts to process — please upload a file or paste text first.")
    else:
        # Validate API keys according to backend
        if backend == 'openai' and not openai_key:
            st.warning("OpenAI backend selected but OpenAI API key not provided. Please enter key in sidebar.")
        if backend == 'gemini' and not gemini_key:
            st.warning("Gemini backend selected but Gemini API key not provided. Please enter key in sidebar.")

        n = len(texts)
        st.write(f"Processing {n} texts with backend: {backend}")
        progress = st.progress(0)
        results = []
        batch_size = 8
        for i, txt in enumerate(texts):
            try:
                prompt = build_prompt_for_single(txt)
                if backend == 'openai':
                    if not OPENAI_INSTALLED:
                        raise RuntimeError("openai package not installed in this environment. Install it or choose Gemini backend.")
                    raw = call_openai_chat_completion(openai_key, prompt, model=model_choice)
                else:
                    # Gemini path - student should implement call_gemini_placeholder
                    raw = call_gemini_placeholder(gemini_key, prompt, model=model_choice)

                parsed = safe_parse_json(raw)
                if parsed is None:
                    # fallback: attempt to heuristically read lines
                    parsed = {}
                    parsed['sentiment'] = 'neutral'
                    parsed['emotion'] = 'neutral'
                    parsed['explanation_en'] = raw[:200]
                    parsed['explanation_th'] = ''

                # normalize fields
                sentiment = parsed.get('sentiment') if isinstance(parsed.get('sentiment'), str) else str(parsed.get('sentiment'))
                emotion = parsed.get('emotion') if isinstance(parsed.get('emotion'), (str, list)) else str(parsed.get('emotion'))
                explanation_en = parsed.get('explanation_en', '')
                explanation_th = parsed.get('explanation_th', '')

            except NotImplementedError as nie:
                st.error(str(nie))
                st.stop()
            except Exception as e:
                sentiment = 'neutral'
                emotion = 'neutral'
                explanation_en = f"LLM error: {e}"
                explanation_th = ''

            # ensure string
            if isinstance(emotion, list):
                emotion_str = ", ".join(emotion)
            else:
                emotion_str = str(emotion)

            # Thai translations in parentheses
            sentiment_th = translate_label_to_th(sentiment)
            emotion_th = ", ".join([translate_label_to_th(e.strip()) or '' for e in emotion_str.split(',')]).strip()

            results.append({
                'text': txt,
                'sentiment_en': sentiment,
                'sentiment_th': f"({sentiment_th})" if sentiment_th else '',
                'emotion_en': emotion_str,
                'emotion_th': f"({emotion_th})" if emotion_th else '',
                'explanation_en': explanation_en,
                'explanation_th': explanation_th
            })

            # update progress
            progress.progress(math.floor((i+1)/n*100))
            # optional small sleep so UI updates smoothly when testing with few items
            time.sleep(0.05)

        df_out = pd.DataFrame(results)

        st.subheader("Results")
        st.dataframe(df_out)

        # Allow download
        csv_bytes = df_out.to_csv(index=False).encode('utf-8')
        st.download_button("Download CSV", data=csv_bytes, file_name="sentiment_emotion_results.csv", mime='text/csv')

        # If original_df exists and had more columns, attach results to it for download
        if original_df is not None:
            try:
                original_df = original_df.reset_index(drop=True)
                results_df_full = original_df.copy()
                # append new columns (if number matches)
                if len(results_df_full) == len(df_out):
                    results_df_full['sentiment_en'] = df_out['sentiment_en']
                    results_df_full['sentiment_th'] = df_out['sentiment_th']
                    results_df_full['emotion_en'] = df_out['emotion_en']
                    results_df_full['emotion_th'] = df_out['emotion_th']
                    results_df_full['explanation_en'] = df_out['explanation_en']
                    results_df_full['explanation_th'] = df_out['explanation_th']
                    st.download_button("Download merged results (CSV)", data=results_df_full.to_csv(index=False).encode('utf-8'), file_name='merged_results.csv')
                else:
                    st.info("Uploaded file row count differs from processed texts; merged download not provided.")
            except Exception as e:
                st.warning(f"Could not merge results with original file: {e}")

        # Plots: sentiment distribution and emotion distribution
        with st.expander("Charts"):
            # sentiment counts
            sent_counts = Counter(df_out['sentiment_en'].fillna('neutral').tolist())
            sent_items = list(sent_counts.items())
            labels_sent = [f"{k} ({translate_label_to_th(k)})" for k,_ in sent_items]
            values_sent = [v for _,v in sent_items]

            fig1, ax1 = plt.subplots()
            ax1.bar(labels_sent, values_sent)
            ax1.set_title('Sentiment distribution')
            ax1.set_ylabel('Count')
            plt.xticks(rotation=30, ha='right')
            st.pyplot(fig1)

            # emotion distribution
            # expand multiple emotions separated by comma
            all_emotions = []
            for e in df_out['emotion_en'].fillna('neutral'):
                for part in str(e).split(','):
                    ep = part.strip()
                    if ep:
                        all_emotions.append(ep)
            emo_counts = Counter(all_emotions)
            if emo_counts:
                labels_emo = [f"{k} ({translate_label_to_th(k)})" for k,_ in emo_counts.items()]
                values_emo = list(emo_counts.values())
                fig2, ax2 = plt.subplots()
                ax2.pie(values_emo, labels=labels_emo, autopct='%1.1f%%')
                ax2.set_title('Emotion distribution')
                st.pyplot(fig2)
            else:
                st.info("No emotion labels to plot")

        st.success("Processing complete")

# Footer / notes
st.markdown("---")
st.write("Notes:")
st.write("• This app calls a large language model: ensure you have an API key and check model usage/costs.")
st.write("• The Gemini integration is a placeholder: students should replace the call_gemini_placeholder() with their project's Gemini request logic (Google-auth, REST call to the models.generate endpoint, etc.).")
st.write("• The prompt requires the LLM to return strict JSON; in practice you may need to refine the prompt or parse free-text outputs.")


# End of file
