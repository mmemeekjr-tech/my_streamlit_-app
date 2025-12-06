# app.py
import streamlit as st
import pandas as pd
import json
import google.generativeai as genai
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
        texts.append(user_text)

elif input_option == "Upload CSV/Excel":
    uploaded_file = st.file_uploader("Upload CSV or Excel file", type=["csv", "xlsx"])
    if uploaded_file:
        try:
            if uploaded_file.name.endswith(".csv"):
                df_input = pd.read_csv(uploaded_file)
            else:
                df_input = pd.read_excel(uploaded_file)
            
            # Check if 'text' column exists
            if "text" not in df_input.columns:
                st.error("Uploaded file must contain a column named 'text'")
                st.stop()
            
            texts = df_input['text'].astype(str).tolist()
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()

if not texts:
    st.info("Please enter text or upload a file to analyze.")
    st.stop()

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
        response = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0
        )
        content = response.choices[0].message.content
        data = json.loads(content)
        return data
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
st.info("Analyzing texts... This may take a few seconds per text.")
results = []

for txt in texts:
    res = analyze_text(txt)
    res["text"] = txt
    results.append(res)

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
fig, ax = plt.subplots()
sentiment_counts.plot(kind='bar', color=['green','gray','red'], ax=ax)
ax.set_title("Sentiment Count")
ax.set_ylabel("Number of texts")
st.pyplot(fig)

# Emotion Count
emotion_counts = df_results['emotion_en'].value_counts()
fig2, ax2 = plt.subplots()
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