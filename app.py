# app.py

import streamlit as st
import pandas as pd
import json
import re
import time
import random
from openai import OpenAI
import matplotlib.pyplot as plt

# -----------------------------
# Sidebar: API Key Input
# -----------------------------
st.sidebar.title("API Settings")
openai_api_key = st.sidebar.text_input("Enter OpenAI API Key", type="password")

if not openai_api_key:
    st.warning("Please enter your OpenAI API Key to use the app.")
    st.stop()

# Initialize OpenAI client
client = OpenAI(api_key=openai_api_key)

# -----------------------------
# App Title
# -----------------------------
st.title("AI Sentiment & Emotion Dashboard")
st.write("Analyze text for sentiment and emotion (English + Thai)")

# -----------------------------
# Input: Text or File
# -----------------------------
input_option = st.radio("Choose input type:", ("Type Text", "Upload CSV/Excel"))

texts = []

if input_option == "Type Text":
    user_text = st.text_area("Enter your text here:", height=150)
    if user_text:
        texts.append(user_text.strip())

elif input_option == "Upload CSV/Excel":
    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.lower().endswith(".csv"):
                df_input = pd.read_csv(uploaded_file)
            else:
                df_input = pd.read_excel(uploaded_file)

            # Check if 'text' column exists
            if "text" not in df_input.columns:
                st.error("Uploaded file must contain a column named 'text'")
                st.stop()

            texts = df_input['text'].astype(str).str.strip().tolist()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()

if not texts:
    st.info("Please enter text or upload a file to analyze.")
    st.stop()

# -----------------------------
# Helpers: parse JSON from model output and retry logic
# -----------------------------
def extract_json_from_text(text):
    """
    Try to extract the first JSON object from a text response.
    Handles cases where model wraps JSON in ```json ... ``` or code fences.
    """
    if not text:
        return None
    # Try to find a JSON block between braces
    # First, remove markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", text)
    cleaned = re.sub(r"```\s*", "", cleaned)
    # Find the first {...} JSON object
    match = re.search(r"\{(?:[^{}]|(?R))*\}", cleaned, flags=re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except Exception:
            # fallback: try to fix common issues (e.g., single quotes)
            try:
                fixed = match.group(0).replace("'", '"')
                return json.loads(fixed)
            except Exception:
                return None
    # If no braces found, maybe it's a plain JSON-like line-by-line key:value pairs
    try:
        return json.loads(cleaned.strip())
    except Exception:
        return None

def call_with_retries(prompt, max_retries=5, base_delay=1.0):
    """
    Call the OpenAI chat completion with exponential backoff on 429 or transient errors.
    Returns the raw text content on success, or raises the last exception.
    """
    attempt = 0
    while True:
        try:
            response = client.chat.completions.create(
                model="gpt-4.1-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0
            )
            # Access content robustly
            content = ""
            if hasattr(response, "choices") and len(response.choices) > 0:
                # Some SDKs return message under .message.content
                choice = response.choices[0]
                if hasattr(choice, "message") and hasattr(choice.message, "content"):
                    content = choice.message.content
                elif hasattr(choice, "text"):
                    content = choice.text
                else:
                    # fallback to string conversion
                    content = str(choice)
            else:
                content = str(response)
            return content
        except Exception as e:
            err_str = str(e).lower()
            attempt += 1
            # If rate limit or transient network error, retry
            if ("429" in err_str or "rate limit" in err_str or "timeout" in err_str or attempt <= max_retries):
                if attempt > max_retries:
                    raise
                # exponential backoff with jitter
                sleep_time = base_delay * (2 ** (attempt - 1)) + random.uniform(0, 0.5)
                time.sleep(sleep_time)
                continue
            else:
                # non-retriable error
                raise

# -----------------------------
# Function: Analyze Sentiment & Emotion
# -----------------------------
def analyze_text(text):
    prompt = f"""
You are an advanced NLP assistant.

Task:
1. Classify the sentiment of the following text: choose ONLY from ["positive", "neutral", "negative"].
2. Classify the emotion: choose ONLY from ["joy", "sadness", "anger", "fear", "surprise", "disgust", "neutral"].
3. Provide both English and Thai translations for sentiment and emotion.
4. Explain briefly why in 2–3 sentences.

Output strictly in JSON format like:
{{
    "sentiment_en": "",
    "sentiment_th": "",
    "emotion_en": "",
    "emotion_th": "",
    "explanation": ""
}}

Text: \"\"\"{text}\"\"\"
"""
    try:
        raw = call_with_retries(prompt)
        parsed = extract_json_from_text(raw)
        if parsed is None:
            # If parsing failed, return an informative error structure
            return {
                "sentiment_en": "error",
                "sentiment_th": "error",
                "emotion_en": "error",
                "emotion_th": "error",
                "explanation": "Failed to parse JSON from model response. Raw response: " + (raw[:1000] if raw else "empty")
            }
        # Ensure all keys exist
        for k in ["sentiment_en", "sentiment_th", "emotion_en", "emotion_th", "explanation"]:
            if k not in parsed:
                parsed[k] = ""
        return parsed
    except Exception as e:
        return {
            "sentiment_en": "error",
            "sentiment_th": "error",
            "emotion_en": "error",
            "emotion_th": "error",
            "explanation": str(e)
        }

# -----------------------------
# Analyze all texts
# -----------------------------
st.info("Analyzing texts... This may take a few seconds per text (retries enabled for transient errors).")
results = []

progress_bar = st.progress(0)
total = len(texts)

for i, txt in enumerate(texts, start=1):
    res = analyze_text(txt)
    res["text"] = txt
    results.append(res)
    progress_bar.progress(i / total)

# Create DataFrame
df_results = pd.DataFrame(results)[['text', 'sentiment_en', 'sentiment_th', 'emotion_en', 'emotion_th', 'explanation']]

st.subheader("Analysis Results")
st.dataframe(df_results, use_container_width=True)

# -----------------------------
# Visualization
# -----------------------------
st.subheader("Summary Charts")

# Sentiment Count
sentiment_counts = df_results['sentiment_en'].value_counts()
if sentiment_counts.empty:
    st.write("No sentiment data to plot.")
else:
    # Map colors dynamically to present categories
    color_map = {
        "positive": "#2ca02c",  # green
        "neutral": "#7f7f7f",   # gray
        "negative": "#d62728",  # red
        "error": "#9467bd"      # purple for errors
    }
    colors = [color_map.get(k, "#1f77b4") for k in sentiment_counts.index]

    fig, ax = plt.subplots()
    sentiment_counts.plot(kind='bar', color=colors, ax=ax)
    ax.set_title("Sentiment Count")
    ax.set_ylabel("Number of texts")
    ax.set_xlabel("")
    ax.set_xticklabels(sentiment_counts.index, rotation=0)
    st.pyplot(fig)

# Emotion Count
emotion_counts = df_results['emotion_en'].value_counts()
if emotion_counts.empty:
    st.write("No emotion data to plot.")
else:
    # For pie chart, ensure there are at least two categories or handle single slice
    fig2, ax2 = plt.subplots()
    if len(emotion_counts) == 1:
        # Single slice: draw a bar instead for clarity
        single_label = emotion_counts.index[0]
        fig3, ax3 = plt.subplots()
        ax3.bar([single_label], [emotion_counts.iloc[0]], color="#1f77b4")
        ax3.set_title("Emotion Distribution")
        ax3.set_ylabel("Number of texts")
        st.pyplot(fig3)
    else:
        emotion_counts.plot(kind='pie', autopct='%1.1f%%', startangle=140, ax=ax2)
        ax2.set_ylabel("")
        ax2.set_title("Emotion Distribution")
        st.pyplot(fig2)

# -----------------------------
# Download CSV
# -----------------------------
csv = df_results.to_csv(index=False)
st.download_button(
    label="Download CSV",
    data=csv,
    file_name="sentiment_emotion_analysis.csv",
    mime="text/csv"
)
