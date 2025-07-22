# app/admin/dashboard.py

import pandas as pd
import streamlit as st
import os
import plotly.express as px
import re
from datetime import datetime
import json

LOG_FILE = "logs/bot.log"
SUMMARY_PATH = 'logs/summary_log.jsonl'

# --- Set page title and layout ---
st.set_page_config(page_title="LUXORIA SUITES – Admin Console", layout="wide")
st.title("🏨 LUXORIA SUITES – Concierge AI Admin Dashboard")
st.markdown("_Monitor interactions, understand guest needs, and enhance luxury service._")

# --- Check for log file existence ---
if not os.path.exists(LOG_FILE):
    st.warning("No logs found yet.")
    st.stop()

# --- Parse bot.log file ---
log_lines = []
with open(LOG_FILE, "r", encoding="ISO-8859-1") as f:
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
st.sidebar.header("🔍 Filter Interactions")
source_filter = st.sidebar.selectbox("📱 Channel", ["All"] + sorted(df["Source"].unique().tolist()))
intent_filter = st.sidebar.selectbox("🎯 Intent", ["All"] + sorted(df["Intent"].unique().tolist()))

filtered_df = df.copy()
if source_filter != "All":
    filtered_df = filtered_df[filtered_df["Source"] == source_filter]
if intent_filter != "All":
    filtered_df = filtered_df[filtered_df["Intent"] == intent_filter]

# --- KPIs ---
col1, col2, col3 = st.columns(3)
col1.metric("🗨️ Total Interactions", len(filtered_df))
col2.metric("👥 Unique Guests/Sessions", filtered_df["Session ID"].nunique())
col3.metric("🔍 Detected Intents", filtered_df["Intent"].nunique())

st.markdown("---")

# --- 📊 Distribution by Source (WhatsApp, Web, etc.) ---
st.subheader("📊 Channel Distribution")
source_counts = filtered_df["Source"].value_counts().reset_index()
source_counts.columns = ["Channel", "Messages"]
fig = px.pie(source_counts, names="Channel", values="Messages", title="Interaction Share by Channel")
st.plotly_chart(fig, use_container_width=True)

# --- 📈 Volume by Day ---
st.subheader("📅 Daily Interaction Volume")
daily = filtered_df.groupby("Date").size().reset_index(name="Messages")
fig2 = px.line(daily, x="Date", y="Messages", markers=True, title="Daily Guest Interactions")
st.plotly_chart(fig2, use_container_width=True)

# --- 📊 Top Intents (Bookings, Wake-Up Calls, Spa, etc.) ---
st.subheader("🎯 Guest Needs Breakdown")
intent_counts = filtered_df["Intent"].value_counts().reset_index()
intent_counts.columns = ["Intent", "Count"]
fig3 = px.bar(intent_counts, x="Intent", y="Count", title="Most Requested Services", color="Intent")
st.plotly_chart(fig3, use_container_width=True)

# --- 🧾 Session Activity ---
st.subheader("📈 Engagement by Guest Sessions")
session_counts = filtered_df["Session ID"].value_counts().reset_index()
session_counts.columns = ["Session ID", "Messages"]
fig4 = px.bar(session_counts, x="Session ID", y="Messages", title="Activity Per Guest Session")
st.plotly_chart(fig4, use_container_width=True)

# --- 📜 Raw Logs ---
st.subheader("📜 Guest Interaction Log")
st.dataframe(filtered_df)

# --- 📥 Export Logs ---
st.download_button("📥 Download Logs as CSV", filtered_df.to_csv(index=False), file_name="LUXORIA_logs.csv")

# --- 🧠 Conversation Summaries (if available) ---
st.subheader("🧠 Guest Session Summaries & Follow-up Emails")

if os.path.exists(SUMMARY_PATH):
    summaries = []
    with open(SUMMARY_PATH, "r", encoding="ISO-8859-1") as f:
        for line in f:
            try:
                summaries.append(json.loads(line.strip()))
            except Exception:
                continue

    if summaries:
        summary_df = pd.DataFrame(summaries)
        summary_df["summary"] = summary_df["summary"].str.strip()
        summary_df["follow_up_email"] = summary_df["follow_up_email"].str.strip()

        for _, row in summary_df.iterrows():
            with st.expander(f"🛏️ Guest Session: {row['session_id']}"):
                st.markdown("**📝 Summary of Conversation:**")
                st.markdown(row["summary"])
                st.markdown("**📧 Follow-up Email Sent:**")
                st.markdown(f"> {row['follow_up_email']}")

        st.download_button(
            "📥 Download All Summaries",
            summary_df.to_csv(index=False),
            file_name="LUXORIA_session_summaries.csv"
        )
    else:
        st.info("No guest session summaries generated yet.")
else:
    st.warning("Summary file not found. Please run `summarizer.py` first.")
