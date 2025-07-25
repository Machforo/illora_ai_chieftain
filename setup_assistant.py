import streamlit as st
import json
import os
from qa_generator import generate_qa_pairs

st.set_page_config(page_title="Hotel Setup Assistant", layout="centered")

st.title("🏨 Hotel Concierge Bot Setup")

st.markdown("Fill in your hotel details below. We’ll generate 50 Q&A pairs for your custom concierge bot.")

with st.form("hotel_form"):
    name = st.text_input("Hotel Name")
    room_types = st.text_input("Room types and pricing (e.g., Deluxe ₹4000, Suite ₹7000)")
    amenities = st.text_input("Amenities (e.g., Spa, Gym, Pool)")
    check_in_out = st.text_input("Check-in and Check-out times (e.g., 2 PM / 11 AM)")
    restaurant = st.text_input("Do you have a restaurant? What cuisines are served?")
    transport = st.text_input("Do you provide airport pickup/drop?")
    custom_notes = st.text_area("Other policies or services")

    submitted = st.form_submit_button("Generate Q&A Dataset")

if submitted:
    hotel_info = {
        "name": name,
        "room_types": room_types,
        "amenities": amenities,
        "check_in_out": check_in_out,
        "restaurant": restaurant,
        "transport": transport,
        "custom_notes": custom_notes
    }

    with st.spinner("Generating Q&A pairs using Groq AI..."):
        try:
            qa_pairs = generate_qa_pairs(hotel_info)

            #os.makedirs("data", exist_ok=True)
            with open("data/qa_generator.csv", "w", encoding="utf-8") as f:
                for line in qa_pairs:
                    f.write(line.strip() + "\n")

            st.success("✅ Q&A dataset generated and saved as `data/qa_generator.csv`")
            st.download_button("📥 Download Q&A CSV", data="\n".join(qa_pairs), file_name="qa_generator.csv")

        except Exception as e:
            st.error(f"❌ Error: {e}")
