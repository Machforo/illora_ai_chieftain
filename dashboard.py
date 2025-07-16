# app/admin/dashboard.py

import pandas as pd
import streamlit as st
import os
import plotly.express as px
import re
from datetime import datetime

LOG_FILE = "logs/bot.log"

st.set_page_config(page_title="AI Chieftain Admin", layout="wide")
st.title("📊 AI Chieftain – Admin Dashboard")

if not os.path.exists(LOG_FILE):
    st.warning("No logs found yet.")
    st.stop()

# --- Parse bot.log file ---
log_lines = []
with open(LOG_FILE, "r", encoding="utf-8") as f:
    for line in f:
        parts = [part.strip() for part in line.strip().split("|")]
        if len(parts) >= 7:
            timestamp = parts[0]
            source = parts[3]
            session_id = parts[4]
            user_input = parts[5]
            response = parts[6]
            intent_match = re.search(r"Intent: (.+)", line)
            intent = intent_match.group(1) if intent_match else "Unknown"
            log_lines.append([timestamp, source, session_id, user_input, response, intent])

df = pd.DataFrame(log_lines, columns=["Timestamp", "Source", "Session ID", "User Input", "Response", "Intent"])
df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce")
df["Date"] = df["Timestamp"].dt.date

# --- Sidebar Filters ---
st.sidebar.header("🔍 Filters")
source_filter = st.sidebar.selectbox("Filter by Source", ["All"] + sorted(df["Source"].unique().tolist()))
intent_filter = st.sidebar.selectbox("Filter by Intent", ["All"] + sorted(df["Intent"].unique().tolist()))

filtered_df = df.copy()
if source_filter != "All":
    filtered_df = filtered_df[filtered_df["Source"] == source_filter]
if intent_filter != "All":
    filtered_df = filtered_df[filtered_df["Intent"] == intent_filter]

# --- KPIs ---
col1, col2, col3 = st.columns(3)
col1.metric("🗣️ Total Messages", len(filtered_df))
col2.metric("🙋 Unique Sessions", filtered_df["Session ID"].nunique())
col3.metric("🎯 Unique Intents", filtered_df["Intent"].nunique())

st.markdown("---")

# --- 📊 Message Distribution by Source ---
st.subheader("📊 Message Source Distribution")
source_counts = filtered_df["Source"].value_counts().reset_index()
source_counts.columns = ["Source", "Messages"]
fig = px.pie(source_counts, names="Source", values="Messages", title="Message Share by Source")
st.plotly_chart(fig, use_container_width=True)

# --- 📈 Daily Messages ---
st.subheader("📅 Daily Message Volume")
daily = filtered_df.groupby("Date").size().reset_index(name="Messages")
fig2 = px.line(daily, x="Date", y="Messages", markers=True, title="Daily Message Volume")
st.plotly_chart(fig2, use_container_width=True)

# --- 📊 Top Intents ---
st.subheader("🎯 Top Detected Intents")
intent_counts = filtered_df["Intent"].value_counts().reset_index()
intent_counts.columns = ["Intent", "Count"]
fig3 = px.bar(intent_counts, x="Intent", y="Count", title="Top Intents", color="Intent")
st.plotly_chart(fig3, use_container_width=True)

# --- 📊 Session Activity ---
st.subheader("🧾 Messages per Session")
session_counts = filtered_df["Session ID"].value_counts().reset_index()
session_counts.columns = ["Session ID", "Message Count"]
fig4 = px.bar(session_counts, x="Session ID", y="Message Count", title="Activity by Session")
st.plotly_chart(fig4, use_container_width=True)

# --- 🔍 Raw Logs Table ---
st.subheader("📜 Raw Chat Log")
st.dataframe(filtered_df)

# --- 📥 Download ---
st.download_button("📥 Download Logs as CSV", filtered_df.to_csv(index=False), file_name="filtered_chat_logs.csv")
