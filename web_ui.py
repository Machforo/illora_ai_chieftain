import streamlit as st
import uuid
import qrcode
import os
from io import BytesIO
from PIL import Image
from payment_gateway import create_checkout_session, create_addon_checkout_session
from logger import log_chat
from qa_agent import ConciergeBot
from intent_classifier import classify_intent

# --- Branding ---
LOGO_PATH = "logo.jpg"
QR_LINK = "https://machforo-illora-ai-chieftain-web-ui-mll3bb.streamlit.app/"
WHATSAPP_LINK = "https://wa.me/919876543210"  # Replace with actual WhatsApp number or group link

# --- Add-on Options ---
AVAILABLE_EXTRAS = {
    "Spa Massage": "spa_massage",
    "Aromatherapy": "spa_aromatherapy",
    "Hot Stone Therapy": "spa_hot_stone",
    "Mocktail": "mocktail",
    "Juice": "juice",
    "Cheese Platter": "cheese_platter",
    "Chocolate Brownie": "chocolate_brownie"
}

# --- QR Generator ---
def generate_qr_code(link: str) -> Image.Image:
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    return qr.make_image(fill="black", back_color="white")

# --- Session State Initialization ---
if "bot" not in st.session_state:
    st.session_state.bot = ConciergeBot()
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "guest_status" not in st.session_state:
    st.session_state.guest_status = None
if "pending_addon_request" not in st.session_state:
    st.session_state.pending_addon_request = []

# --- Page Config ---
st.set_page_config(
    page_title="ILLORA Retreat – AI Concierge",
    page_icon="🛎️",
    layout="wide"
)

# --- Sidebar: Logo, Guest Identity, WhatsApp QR ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=180)
    st.markdown("### 🧾 Guest Status")
    with st.form("guest_status_form"):
        guest_option = st.radio("Are you staying at ILLORA Retreat?", ["Yes", "No"])
        submit_guest = st.form_submit_button("Submit")
        if submit_guest:
            st.session_state.guest_status = guest_option

    st.markdown("---")
    st.markdown("### 📞 Connect on WhatsApp")
    wa_qr = generate_qr_code(WHATSAPP_LINK)
    buf = BytesIO()
    wa_qr.save(buf, format="PNG")
    st.image(buf.getvalue(), width=160, caption="Chat with us on WhatsApp")

# --- Header Section ---
st.title("🏨 ILLORA Retreat – Your AI Concierge")
st.markdown("#### _Welcome to ILLORA Retreat, where luxury meets the wilderness._")
st.markdown("---")

# --- QR to Open on Mobile ---
st.markdown("### 📱 Access this Assistant on Mobile")
qr_img = generate_qr_code(QR_LINK)
qr_buf = BytesIO()
qr_img.save(qr_buf, format="PNG")
st.image(qr_buf.getvalue(), width=180, caption="Scan to open on your phone")

st.markdown("---")

# --- Chat History Display ---
for role, msg in st.session_state.chat_history:
    with st.chat_message(role):
        st.markdown(msg)

# --- Chat Input ---
st.markdown("### 💬 Concierge Chat")
user_input = st.chat_input("Ask me anything about ILLORA Retreat")
coming_from = "Web"

# --- Chat Logic ---
if user_input:
    st.session_state.user_input = user_input
    st.session_state.predicted_intent = classify_intent(user_input)
    st.chat_message("user").markdown(user_input)
    st.session_state.chat_history.append(("user", user_input))

    message_lower = user_input.lower()
    addon_matches = [key for key in AVAILABLE_EXTRAS if key.lower() in message_lower]
    st.session_state.pending_addon_request = addon_matches if addon_matches else []

    with st.spinner("🤖 Thinking..."):
        is_guest = st.session_state.guest_status == "Yes"
        response = st.session_state.bot.ask(user_input, user_type=is_guest)
        st.session_state.response = response
        log_chat(coming_from, st.session_state.session_id, user_input, response,
                 st.session_state.predicted_intent, is_guest)

    st.chat_message("assistant").markdown(response)
    st.session_state.chat_history.append(("assistant", response))

# --- Add-on Confirmation ---
if st.session_state.get("pending_addon_request"):
    st.markdown("### 🧾 Confirm Add-on Services")
    st.info(f"Would you like to pay for the following service(s)?\n👉 {', '.join(st.session_state.pending_addon_request)}")

    col1, col2 = st.columns(2)
    with col1:
        confirm = st.button("💳 Yes, generate payment link")
    with col2:
        cancel = st.button("❌ No, maybe later")

    if confirm:
        extra_keys = [AVAILABLE_EXTRAS[k] for k in st.session_state.pending_addon_request]
        addon_url = create_addon_checkout_session(
            session_id=st.session_state.session_id,
            extras=extra_keys
        )
        if addon_url:
            st.success("🧾 Add-on payment link generated.")
            st.markdown(f"[💳 Pay for Add-ons]({addon_url})", unsafe_allow_html=True)
        else:
            st.error("⚠️ Could not generate payment link.")
        st.session_state.pending_addon_request = []

    if cancel:
        st.session_state.pending_addon_request = []

# --- Room/Addon Payment Form ---
if st.session_state.get("predicted_intent") == "payment_request" and not st.session_state.get("pending_addon_request"):
    st.markdown("### 🛏️ Book a Room / Add-on Services")

    with st.form("booking_form"):
        room_type = st.selectbox("Room Type (optional)", ["None", "Standard", "Deluxe", "Executive", "Family", "Suite"])
        nights = st.number_input("Number of nights", min_value=1, step=1, value=1)
        payment_method = st.radio("Payment Method", ["Online", "Cash on Arrival"])

        price_map = {
            "Standard": 12500,
            "Deluxe": 17000,
            "Executive": 23000,
            "Family": 27500,
            "Suite": 34000
        }

        if room_type != "None":
            base_price = price_map[room_type] * nights
            st.markdown(f"💰 **Room Total: ₹{base_price}**")
        else:
            st.markdown("💡 You can skip room booking and only pay for add-ons.")

        st.markdown("### 🧖‍♀️ Optional Add-ons")
        selected_extras = st.multiselect("Choose your add-ons:", list(AVAILABLE_EXTRAS.keys()))
        submit_booking = st.form_submit_button("✅ Proceed")

        if submit_booking:
            room_selected = room_type != "None"
            any_addon_selected = len(selected_extras) > 0

            if room_selected:
                room_url = create_checkout_session(
                    session_id=st.session_state.session_id,
                    room_type=room_type,
                    nights=nights,
                    cash=(payment_method == "Cash on Arrival"),
                    extras=[]
                )
                if room_url:
                    st.success("✅ Room booking link generated.")
                    st.markdown(f"[💳 Pay for Room Booking]({room_url})", unsafe_allow_html=True)
                else:
                    st.error("⚠️ Room payment link generation failed.")

            if any_addon_selected:
                extra_keys = [AVAILABLE_EXTRAS[item] for item in selected_extras]
                addon_url = create_addon_checkout_session(
                    session_id=st.session_state.session_id,
                    extras=extra_keys
                )
                if addon_url:
                    st.success("🧾 Add-on payment link generated.")
                    st.markdown(f"[💳 Pay for Add-ons]({addon_url})", unsafe_allow_html=True)
                else:
                    st.error("⚠️ Add-on payment link generation failed.")

            if not room_selected and not any_addon_selected:
                st.warning("⚠️ Please select a room or at least one add-on to proceed.")
