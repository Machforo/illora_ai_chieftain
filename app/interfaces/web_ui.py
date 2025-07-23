import streamlit as st
import uuid
import stripe
import sys
import os
import qrcode
from io import BytesIO
from PIL import Image
import tempfile
import pygame
import subprocess
from gtts import gTTS
import speech_recognition as sr
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))


from app.services.payment_gateway import create_checkout_session
from app.logger import log_chat
from app.agents.qa_agent import ConciergeBot
from app.services.intent_classifier import classify_intent


# --- Branding ---
LOGO_PATH = os.path.join("app", "assets", "logo.jpg")
QR_LINK = "http://localhost:8501"

ROOM_PRICING = {
    "deluxe": 4000,
    "executive": 6000,
    "family": 8000
}

# --- Audio ---
def speak(text):
    tts = gTTS(text)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        path = fp.name
        tts.save(path)

    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy():
        continue
    pygame.mixer.quit()
    os.remove(path)

# --- QR Generator ---
def generate_qr_code(link: str) -> Image.Image:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    return img

# --- Speech Recognition ---
def listen(device_index=None):
    recognizer = sr.Recognizer()
    try:
        with sr.Microphone() as source:
            st.info("🎙️ Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)
            st.info("🎙️ Listening... Please speak clearly within 10 seconds.")
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)
            st.success("🔍 Recognizing...")
            return recognizer.recognize_google(audio)
    except Exception as e:
        st.error(f"⚠️ Audio Error: {e}")
        return None

# --- Init Bot & Session ---
if "bot" not in st.session_state:
    st.session_state.bot = ConciergeBot()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "guest_status" not in st.session_state:
    st.session_state.guest_status = None

# --- Page Layout ---
st.set_page_config(page_title="AI Chieftain – Concierge Bot", page_icon="🛎️")
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=150)
st.title("🏨 LUXORIA SUITES – Your AI Concierge")
st.markdown("_Welcome to LUXORIA SUITES, where elegance meets intelligence._")

# --- Sidebar Guest Type Form ---
with st.sidebar.form("guest_status_form"):
    st.markdown("### 🧾 Tell us who you are:")
    guest_option = st.radio("Are you a guest staying at Luxoria Suites?", ["Yes", "No"])
    submit_guest = st.form_submit_button("Submit")

    if submit_guest:
        st.session_state.guest_status = guest_option

if st.session_state.guest_status is None:
    st.warning("Please specify whether you're a guest or non-guest from the sidebar to continue.")
    st.stop()

# --- QR Code ---
st.subheader("📱 Scan to Open on Mobile")
qr_img = generate_qr_code(QR_LINK)
qr_buf = BytesIO()
qr_img.save(qr_buf, format="PNG")
st.image(qr_buf.getvalue(), width=180, caption="Scan to explore LUXORIA SUITES on your phone")

# --- Display Chat History ---
for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

# --- User Input ---
st.markdown("### 💬 Type your message or speak below:")
user_input = st.chat_input("Ask me anything about LUXORIA SUITES")
coming_from = "Web"

st.markdown("### 🎤 Or use voice:")
if st.button("🎙️ Talk to the Bot"):
    spoken_text = listen()
    if spoken_text:
        user_input = spoken_text
        coming_from = "Voice"
        st.chat_message("user").markdown(f"🗣️ {spoken_text}")
        st.session_state.chat_history.append(("user", spoken_text))

# --- Handle Bot Interaction ---
if user_input:
    st.session_state.user_input = user_input
    st.session_state.predicted_intent = classify_intent(user_input)
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append(("user", user_input))

    with st.spinner("🤖 Thinking..."):
        is_guest = st.session_state.guest_status == "Yes"
        response = st.session_state.bot.ask(user_input, user_type=is_guest)
        st.session_state.response = response
        log_chat(coming_from, st.session_state.session_id, user_input, response, st.session_state.predicted_intent,is_guest)

    st.chat_message("assistant").markdown(response)
    speak(response)
    st.session_state.chat_history.append(("assistant", response))

# --- Payment Flow ---
if st.session_state.get("predicted_intent") == "payment_request" and st.session_state.guest_status == "Yes":
    st.info("LUXORIA SUITES accepts online payments or cash.")

    with st.form("booking_form"):
        room_type = st.selectbox("🏨 Select Room Type", ["Deluxe", "Executive", "Family"])
        nights = st.number_input("🕒 Number of nights", min_value=1, step=1)
        payment_method = st.radio("💳 Payment Method", ["Online", "Cash on Arrival"])

        price_per_night = {"Deluxe": 4000, "Executive": 6000, "Family": 8000}
        total_price = price_per_night[room_type] * nights
        st.info(f"💵 Total: ₹{total_price} for {nights} night(s) in {room_type} Room. Includes all premium amenities.")

        submitted = st.form_submit_button("✅ Confirm and Pay")

        if submitted:
            pay_url = create_checkout_session(
                session_id=st.session_state.session_id,
                room_type=room_type,
                nights=nights,
                cash=(payment_method == "Cash on Arrival")
            )
            if pay_url:
                st.success("✅ Payment link generated!")
                st.markdown(f"[Click here to Pay]({pay_url})", unsafe_allow_html=True)
            else:
                st.error("⚠️ Failed to generate payment link.")

    st.session_state.predicted_intent = None  # Reset
elif st.session_state.get("predicted_intent") == "payment_request":
    st.warning("⚠️ Only hotel guests can proceed with room booking and payments.")
