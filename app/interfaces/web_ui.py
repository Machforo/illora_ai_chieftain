import streamlit as st
import uuid
import stripe
# in order to access all files in the project directory
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# essential packages
from app.services.payment_gateway import create_checkout_session
from app.logger import log_chat
from app.agents.qa_agent import ConciergeBot
import qrcode
from io import BytesIO
from PIL import Image
import speech_recognition as sr
from gtts import gTTS
from pydub import AudioSegment
from pydub.playback import play
import tempfile
import streamlit.components.v1 as components
import pygame
import subprocess
import requests
import time
from app.services.intent_classifier import classify_intent




### function to create a local tunnel so any device can access my site
import subprocess

def start_localtunnel(port=8501):
    try:
        # Full path to lt.cmd
        lt_path = r"C:\\Users\\Atharv\\AppData\\Roaming\\npm\\lt.cmd"
        output = subprocess.check_output([lt_path, "--port", str(port)], stderr=subprocess.STDOUT, text=True)
        for line in output.splitlines():
            if "https://" in line:
                return line.strip()
    except subprocess.CalledProcessError as e:
        print("LocalTunnel Error:", e.output)
    except FileNotFoundError as e:
        print("LocalTunnel not found:", e)

    return None

#public_url = start_localtunnel()
#print("Public URL:", public_url)


######################################



# --- Config ---
LOGO_PATH = os.path.join("app", "assets", "logo.jpg")
QR_LINK = "http://localhost:8501"  # Update if you host elsewhere

coming_from = ''  # source of the request voice, QR or text adment to the admin dashboard

# --- QR Code Generator ---
def generate_qr_code(link: str) -> Image.Image:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    return img

# --- TTS --- Text To Speech
def speak(text):
    tts = gTTS(text)  # Using google text to speech library

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        path = fp.name
        tts.save(path)
    

    pygame.mixer.init()           # initilaize the audio file
    pygame.mixer.music.load(path) # loads the audio file 
    pygame.mixer.music.play()     # starts playing the audio file    
    
    # Wait until it's done speaking
    while pygame.mixer.music.get_busy():
        continue


    pygame.mixer.quit()
    os.remove(path)

# -------------------------S

# --- STT --- Speech to Text ---
import speech_recognition as sr

def listen(device_index=None):
    recognizer = sr.Recognizer()

    try:
        with sr.Microphone() as source:
            st.info("🎙️ Adjusting for ambient noise...")
            recognizer.adjust_for_ambient_noise(source, duration=1)

            st.info("🎙️ Listening... Please speak clearly within 10 seconds.")
            audio = recognizer.listen(source, timeout=10, phrase_time_limit=10)

            st.success("🔍 Recognizing...")
            text = recognizer.recognize_google(audio)
            return text

    except sr.WaitTimeoutError:
        st.error("⏰ Timeout: No speech detected.")
    except sr.UnknownValueError:
        st.error("😕 Could not understand audio. Please try again.")
    except sr.RequestError as e:
        st.error(f"❌ API request error: {e}")
    except Exception as e:
        st.error(f"⚠️ Unexpected error: {e}")

    return None

#-----------------------------




# --- Init bot ---
if "bot" not in st.session_state:
    st.session_state.bot = ConciergeBot()

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# --- UI Layout ---
st.set_page_config(page_title="AI Chieftain – Concierge Bot", page_icon="🛎️")

# --- Branding ---
if os.path.exists(LOGO_PATH):
    st.image(LOGO_PATH, width=150)

st.title("🏨 LUXORIA SUITES – Your AI Concierge")
st.markdown("_Welcome to LUXORIA SUITES, where elegance meets intelligence._")


# Assign a unique session ID once per user session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.markdown("How can I assist you during your stay at LUXORIA SUITES?")

# --- QR Code ---

st.subheader("📱 Scan to Open on Mobile")
qr_image = generate_qr_code(QR_LINK)
qr_buf = BytesIO()   # for stroing memory as bytes to temporarily store binary data
qr_image.save(qr_buf, format="PNG")
st.image(qr_buf.getvalue(), width=180, caption="Scan to explore LUXORIA SUITES on your phone")

# --- Chat messages ---
for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

# --- Text Input ---
user_input = st.chat_input("Type your question or click below to speak")
coming_from = 'Web'

# --- Voice Input Button ---
st.markdown("### 🎤 Or use voice:")
if st.button("🎙️ Talk to the Bot"):
    spoken_text = listen()
    if spoken_text:
        user_input = spoken_text
        coming_from = 'Voice'
        st.chat_message("user").markdown(f"🗣️ {spoken_text}")
        st.session_state.chat_history.append(("user", spoken_text))

ROOM_PRICING = {
    "deluxe": 4000,
    "executive": 6000,
    "family": 8000
}

# --- Handle Input ---

# Save chat and detect intent
if user_input:
    st.session_state.user_input = user_input
    st.session_state.predicted_intent = classify_intent(user_input)
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append(("user", user_input))

    with st.spinner("🤖 Thinking..."):
        response = st.session_state.bot.ask(user_input)
        st.session_state.response = response  # Save for next rerun
        log_chat(coming_from, st.session_state.session_id, user_input, response, st.session_state.predicted_intent)

    st.chat_message("assistant").markdown(st.session_state.response)
    speak(st.session_state.response)
    st.session_state.chat_history.append(("assistant", st.session_state.response))


# --- Payment Form if predicted intent is payment_request ---
if st.session_state.get("predicted_intent") == "payment_request":

    st.info("LUXORIA SUITES accepts online payments or cash.")

    with st.form("booking_form"):
        room_type = st.selectbox("🏨 Select Room Type", ["Deluxe", "Executive", "Family"])
        nights = st.number_input("🕒 Number of nights", min_value=1, step=1)
        payment_method = st.radio("💳 Payment Method", ["Online", "Cash on Arrival"])

        # Calculate total price
        price_per_night = {"Deluxe": 4000, "Executive": 6000, "Family": 8000}
        total_price = price_per_night[room_type] * nights
        st.info(f"💵 Total: ₹{total_price} for {nights} night(s) in {room_type} Room. Includes breakfast, gym, and pool access.")

        submitted = st.form_submit_button("✅ Confirm and Pay")

    if submitted:
        if payment_method == "Online":
            pay_url = create_checkout_session(
                session_id=st.session_state.session_id,
                room_type=room_type,
                nights=nights,
                cash=False
            )
            if pay_url:
                st.success("✅ Payment link generated!")
                st.markdown(f"[Click here to Pay]({pay_url})", unsafe_allow_html=True)
            else:
                st.error("⚠️ Failed to generate payment link. Please try again.")
        
        if payment_method == 'Cash on Arrival':
            st.info('You will have to pay Rs.2000 as advanced for the room booking and then pay the remaing via cash')
            pay_url = create_checkout_session(
                session_id=st.session_state.session_id,
                room_type=room_type,
                nights=nights,
                cash=True
            )
            if pay_url:
                st.success("✅ Payment link generated!")
                st.markdown(f"[Click here to Pay]({pay_url})", unsafe_allow_html=True)
            else:
                st.error("⚠️ Failed to generate payment link. Please try again.")



        # Reset intent after form is submitted
        st.session_state.predicted_intent = None

