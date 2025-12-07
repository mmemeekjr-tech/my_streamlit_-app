# Sentiment + Emotion Dashboard (Streamlit)
# Updated: numbering from 1, improved OpenAI wrapper (new/legacy SDK support), stricter prompt,
# better parsing & retry logic, fixes for chart generation, and clearer error reporting.

import streamlit as st
import pandas as pd
import io
import os
import time
import json
import math
import requests
from typing import List, Dict, Any
import matplotlib.pyplot as plt
from collections import Counter

# Optional: import openai if available
OPENAI_INSTALLED = False
try:
    import openai
    OPENAI_INSTALLED = True
except Exception:
    try:
        # Some environments use the newer OpenAI client package
        from openai import OpenAI as OpenAIClient
        OPENAI_INSTALLED = True
        openai = None
        OpenAIClientAvailable = True
    except Exception:
        OpenAIClientAvailable = False
        OPENAI_INSTALLED = False

# -----------------------------
# Utility functions
# -----------------------------

def translate_label_to_th(label: str) -> str:
    """Simple translations for sentiment/emotion labels to Thai."""
    s = str(label).lower()
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
    if not isinstance(s, str):
        return None
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
# Improved prompt and LLM wrappers
# -----------------------------

def build_prompt_for_single(text: str) -> str:
    """Stricter prompt asking for EXACT JSON schema.

    We instruct the model to ALWAYS respond with only JSON and show a short example.
    """
    schema = {
        "sentiment": "one of [positive, negative, neutral]",
        "emotion": "one or more from [joy, anger, sadness, fear, surprise, disgust, neutral] (as a list)",
        "explanation_en": "short 1-2 sentence explanation in English",
        "explanation_th": "short 1-2 sentence translation in Thai"
    }
    prompt = (
        "You are a JSON-only responder. Given the following user text (which may be Thai or English), "
        "return a STRICT JSON object with these keys exactly: sentiment, emotion, explanation_en, explanation_th.\n"
        "- sentiment: one of [positive, negative, neutral]\n"
        "- emotion: a JSON list (even if one item) chosen from [joy, anger, sadness, fear, surprise, disgust, neutral]\n"
        "- explanation_en: 1-2 short sentences in English explaining the choice\n"
        "- explanation_th: same explanation translated into Thai\n\n"
        "Return ONLY the JSON object and nothing else. Example output format:\n"
        "{" + '\"sentiment\": \"positive\", \"emotion\": [\"joy\"], \"explanation_en\": \"Because...\", \"explanation_th\": \"เพราะ...\"}\n'
        "User text:\n" + text + "\n"
    )
    return prompt


def call_openai_chat_completion(api_key: str, prompt: str, model: str = 'gpt-4o-mini') -> str:
    """Try to support both new and legacy openai client styles.

    New style (openai>=1.0):
      from openai import OpenAI
      client = OpenAI(api_key=...)
      r = client.chat.completions.create(model=model, messages=[{"role":"user","content":prompt}], temperature=0)

    Legacy style:
      import openai
      openai.api_key=...
      r = openai.ChatCompletion.create(...)

    This wrapper attempts new client first, then falls back.
    """
    # First try newer OpenAI client if available
    try:
        # New client
        if 'OpenAIClient' in globals() and OpenAIClientAvailable:
            client = OpenAIClient(api_key=api_key)
            r = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0)
            # response text extraction depends on model - try common paths
            if isinstance(r, dict) and r.get('choices'):
                return r['choices'][0]['message']['content']
            # Some client objects return objects with attributes
            try:
                return r.choices[0].message.content
            except Exception:
                return str(r)

        # Fallback legacy
        if OPENAI_INSTALLED and openai is not None:
            openai.api_key = api_key
            r = openai.ChatCompletion.create(model=model, messages=[{"role": "user", "content": prompt}], temperature=0)
            return r['choices'][0]['message']['content']

    except Exception as e:
        # surface error for debuggingdef
        raise RuntimeError(f"OpenAI call failed: {e}")

    raise RuntimeError("No compatible OpenAI client available in this environment. Install openai or provide a compatible client.")

import requests
import json

def call_gemini_api(api_key, prompt_text):
    """
    Call Gemini API (Google AI Studio) using API key.
    Works for models: gemini-1.5-flash, gemini-1.5-pro
    """
    if not api_key:
        return {"error": "Missing Gemini API key"}

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

    headers = {
        "Content-Type": "application/json"
    }

    body = {
        "contents": [
            {
                "parts": [
                    {"text": prompt_text}
                ]
            }
        ]
    }

    full_url = f"{url}?key={api_key}"
    res = requests.post(full_url, headers=headers, data=json.dumps(body))

    try:
        result = res.json()
    except:
        return {"error": "Gemini output parse error", "raw": res.text}

    # Extract text
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        return {"error": "Gemini returned unexpected format", "raw": result}


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
        # Process sequentially; you can batch or parallelize for speed later
        for i, txt in enumerate(texts):
            try:
                prompt = build_prompt_for_single(txt)
                raw = None
                # Try up to 2 attempts for transient errors
                last_err = None
                for attempt in range(2):
                    try:
                        if backend == 'openai':
                            raw = call_openai_chat_completion(openai_key, prompt, model=model_choice)
                        else:
                            raw = call_gemini_api(gemini_key, prompt)
                        break
                    except NotImplementedError as nie:
                        raise
                    except Exception as e:
                        last_err = e
                        time.sleep(0.3)
                if raw is None:
                    raise RuntimeError(f"LLM call failed after retries: {last_err}")

                parsed = safe_parse_json(raw)
                if parsed is None:
                    # fallback: attempt to heuristically read lines
                    parsed = {}
                    parsed['sentiment'] = 'neutral'
                    parsed['emotion'] = ['neutral']
                    parsed['explanation_en'] = f"LLM returned non-JSON response: {str(raw)[:200]}"
                    parsed['explanation_th'] = ''

                # normalize fields
                sentiment = parsed.get('sentiment') if isinstance(parsed.get('sentiment'), str) else str(parsed.get('sentiment'))
                emotion = parsed.get('emotion') if isinstance(parsed.get('emotion'), (list, str)) else str(parsed.get('emotion'))
                explanation_en = parsed.get('explanation_en', '')
                explanation_th = parsed.get('explanation_th', '')

            except NotImplementedError as nie:
                st.error(str(nie))
                st.stop()
            except Exception as e:
                sentiment = 'neutral'
                emotion = ['neutral']
                explanation_en = f"LLM error: {e}"
                explanation_th = ''

            # ensure list for emotion
            if isinstance(emotion, list):
                emotion_list = [str(x).strip() for x in emotion if str(x).strip()]
            else:
                emotion_list = [p.strip() for p in str(emotion).split(',') if p.strip()]

            emotion_str = ", ".join(emotion_list)

            # Thai translations in parentheses
            sentiment_th = translate_label_to_th(sentiment)
            emotion_th = ", ".join([translate_label_to_th(e.strip()) or '' for e in emotion_list]).strip()

            results.append({
                'id': i+1,
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
            # optional small sleep so UI updates smoothly
            time.sleep(0.03)

        df_out = pd.DataFrame(results)
        # Reorder columns for nicer display
        cols_order = ['id','text','sentiment_en','sentiment_th','emotion_en','emotion_th','explanation_en','explanation_th']
        df_out = df_out[cols_order]

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
            # Ensure consistent order: positive, neutral, negative if present
            ordered_keys = [k for k in ['positive','neutral','negative'] if k in sent_counts]
            other_keys = [k for k in sent_counts.keys() if k not in ordered_keys]
            final_keys = ordered_keys + other_keys
            labels_sent = [f"{k} ({translate_label_to_th(k)})" for k in final_keys]
            values_sent = [sent_counts[k] for k in final_keys]

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
                # sort by frequency
                emo_items = emo_counts.most_common()
                labels_emo = [f"{k} ({translate_label_to_th(k)})" for k,_ in emo_items]
                values_emo = [v for _,v in emo_items]
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
st.write("• The prompt requires the LLM to return strict JSON; in practice you may need to refine the prompt or handle non-JSON responses. The code now attempts stricter prompting and will report raw LLM responses in the explanation if parsing fails.")


# End of file
