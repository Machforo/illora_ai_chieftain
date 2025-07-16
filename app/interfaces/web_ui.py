import streamlit as st
import uuid

# in order to access all files in the project directory
import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

# essential packages
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

# --- TTS ---
def speak(text):
    tts = gTTS(text)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        path = fp.name
        tts.save(path)
    

    pygame.mixer.init()
    pygame.mixer.music.load(path)
    pygame.mixer.music.play()
    
    # Wait until it's done speaking
    while pygame.mixer.music.get_busy():
        continue


    pygame.mixer.quit()
    os.remove(path)

# --- STT ---
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

st.title("🛎️ AI Chieftain – Hotel Concierge")

# Assign a unique session ID once per user session
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.markdown("Ask anything about your hotel stay! Type or use voice below 👇")

# --- QR Code ---

st.subheader("📱 Scan to Open on Mobile")
qr_image = generate_qr_code(QR_LINK)
qr_buf = BytesIO()
qr_image.save(qr_buf, format="PNG")
st.image(qr_buf.getvalue(), width=180, caption="Scan on the same Wi-Fi")

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

# --- Handle Input ---
if user_input:
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append(("user", user_input))

    with st.spinner("🤖 Thinking..."):
        predicted_intent = classify_intent(user_input)
        response = st.session_state.bot.ask(user_input)
        log_chat(coming_from, st.session_state.session_id, user_input, response, predicted_intent )

    st.chat_message("assistant").markdown(response)
    speak(response)
    st.session_state.chat_history.append(("assistant", response))
