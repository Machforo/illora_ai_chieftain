# web_ui.py (UPDATED — uses illora.checkin_app.models as single source-of-truth)
import os
import uuid
import qrcode
import base64
from io import BytesIO
from datetime import datetime, date
from pathlib import Path

import streamlit as st
from PIL import Image
from logger import log_chat

# existing project imports (kept; adjusted)
from illora.checkin_app.payment import create_stripe_checkout_for_booking as create_checkout_session
from payment_gateway import create_addon_checkout_session
from qa_agent import ConciergeBot
from intent_classifier import classify_intent

# SINGLE source-of-truth models & DB session
from illora.checkin_app.models import Room, Booking, BookingStatus
from illora.checkin_app.pricing import calculate_price_for_room as calculate_price
from illora.checkin_app.database import SessionLocal   # must already exist in your project

# --- Page Config ---
st.set_page_config(page_title="ILLORA Retreat – AI Concierge", page_icon="🛎️", layout="wide")

# --- Branding & constants ---
LOGO_PATH = "logo.jpg"
BACKGROUND_IMAGE = "illora_retreats.jpg"
QR_LINK = "https://machforo-illora-ai-chieftain-web-ui-mll3bb.streamlit.app/"
WHATSAPP_LINK = "https://wa.me/919876543210"

# Static dir for local QR images
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)

# Add-on options
AVAILABLE_EXTRAS = {
    "Spa Massage": "spa_massage",
    "Aromatherapy": "spa_aromatherapy",
    "Hot Stone Therapy": "spa_hot_stone",
    "Mocktail": "mocktail",
    "Juice": "juice",
    "Cheese Platter": "cheese_platter",
    "Chocolate Brownie": "chocolate_brownie"
}

# --- Helpers ----------------------------------------------------------------

def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        return base64.b64encode(f.read()).decode()

def generate_qr_code_bytes(link: str) -> bytes:
    """Return PNG bytes of a QR for a given link (temporary checkout QR)."""
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()

def save_qr_to_static(link: str, filename: str):
    """Save QR PNG under static/ and return local path and public path if MEDIA_BASE_URL set."""
    img_bytes = generate_qr_code_bytes(link)
    path = STATIC_DIR / filename
    with open(path, "wb") as f:
        f.write(img_bytes)
    media_base = os.getenv("MEDIA_BASE_URL")
    public = f"{media_base.rstrip('/')}/static/{filename}" if media_base else str(path)
    return str(path), public

def _checkout_url_from_session(sess):
    """Given a returned checkout object or URL, normalize to a URL string (best-effort)."""
    if sess is None:
        return None
    # if function returned a URL directly
    if isinstance(sess, str):
        return sess
    # stripe.Session object often has .url attr in newer libs
    if hasattr(sess, "url"):
        return getattr(sess, "url")
    # dict-like
    try:
        if isinstance(sess, dict):
            if "url" in sess:
                return sess["url"]
            if "checkout_url" in sess:
                return sess["checkout_url"]
    except Exception:
        pass
    # fallback: try client_secret -> build a payment url? Not reliable
    return None

# --- Minimal YouTube / Instagram preview helpers -----------------------------

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
INSTAGRAM_ACCESS_TOKEN = os.getenv("INSTAGRAM_ACCESS_TOKEN")

def youtube_thumbnail(video_url: str):
    """Return YouTube thumbnail URL (fast fallback) or None if parse fails."""
    try:
        if "youtu.be/" in video_url:
            vid = video_url.split("youtu.be/")[-1].split("?")[0]
        else:
            import urllib.parse as up
            q = up.urlparse(video_url).query
            params = up.parse_qs(q)
            vid = params.get("v", [None])[0]
        if not vid:
            return None
        return f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"
    except Exception:
        return None

def instagram_oembed_thumb(insta_url: str):
    """Try Instagram oEmbed endpoint (may need app-level config). Return thumbnail or None."""
    try:
        oembed = f"https://graph.facebook.com/v16.0/instagram_oembed?url={insta_url}"
        r = __import__("requests").get(oembed, timeout=6)
        if r.status_code == 200:
            data = r.json()
            return data.get("thumbnail_url")
    except Exception:
        pass
    return None

# --- Styling (preserve your existing style) ---------------------------------
if os.path.exists(BACKGROUND_IMAGE):
    bin_str = get_base64_of_bin_file(BACKGROUND_IMAGE)
    page_bg_img = f"""
    <style>
    .stApp {{
        background-image: url("data:image/jpg;base64,{bin_str}");
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
        color: #fff;
        font-weight: 500;
    }}
    .stApp::before {{
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0,0,0,0.55);
        backdrop-filter: blur(4px);
        z-index: -1;
    }}
    section[data-testid="stSidebar"] {{
        background: rgba(30, 30, 30, 0.6) !important;
        backdrop-filter: blur(10px);
        color: white !important;
    }}
    .main-content-box {{
        background: rgba(255,255,255,0.08);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 30px rgba(0,0,0,0.2);
        border: 1px solid rgba(255,255,255,0.2);
    }}
    .stChatMessage {{
        background-color: rgba(255,255,255,0.12);
        padding: 12px;
        border-radius: 12px;
        margin: 6px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        font-weight: 500;
    }}
    .stButton>button {{
        background: linear-gradient(90deg, #4CAF50 0%, #2e7d32 100%);
        color: white;
        border-radius: 8px;
        padding: 8px 16px;
        border: none;
        font-weight: bold;
        transition: transform 0.2s ease, background 0.3s ease;
    }}
    .stButton>button:hover {{
        transform: scale(1.05);
        background: linear-gradient(90deg, #66bb6a 0%, #388e3c 100%);
    }}
    h1, h2, h3, h4 {{
        font-weight: 700 !important;
        color: #fff !important;
        text-shadow: 0 2px 4px rgba(0,0,0,0.6);
    }}
    p, label, .stMarkdown {{
        color: #f0f0f0 !important;
    }}
    </style>
    """
    st.markdown(page_bg_img, unsafe_allow_html=True)

# --- Session state init -----------------------------------------------------
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
# booking-specific state
if "booking_details" not in st.session_state:
    st.session_state.booking_details = {}
if "show_room_options" not in st.session_state:
    st.session_state.show_room_options = False
if "checkout_info" not in st.session_state:
    st.session_state.checkout_info = None

# --- Sidebar ----------------------------------------------------------------
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=180)
    st.markdown("### 🧾 Guest Status")
    with st.form("guest_status_form"):
        guest_option = st.radio("Are you staying at ILLORA Retreat?", ["Yes", "No"])
        if st.form_submit_button("Submit"):
            st.session_state.guest_status = guest_option
    st.markdown("---")
    st.markdown("### 📞 Connect on WhatsApp")
    wa_qr = generate_qr_code_bytes(WHATSAPP_LINK)
    st.image(wa_qr, width=160, caption="Chat with us on WhatsApp")

# --- Main layout ------------------------------------------------------------
with st.container():
    st.markdown('<div class="main-content-box">', unsafe_allow_html=True)
    st.title("🏨 ILLORA Retreat – Your AI Concierge")
    st.markdown("#### _Welcome to ILLORA Retreat, where luxury meets the wilderness._")
    st.markdown("---")

    st.markdown("### 📱 Access this Assistant on Mobile")
    qr_img = generate_qr_code_bytes(QR_LINK)
    st.image(qr_img, width=180, caption="Scan to open on your phone")
    st.markdown("---")

    # show chat history
    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)

    # chat input
    st.markdown("### 💬 Concierge Chat")
    user_input = st.chat_input("Ask me anything about ILLORA Retreat")
    coming_from = "Web"

    if user_input:
        st.session_state.user_input = user_input
        st.session_state.predicted_intent = classify_intent(user_input)
        st.chat_message("user").markdown(user_input)
        st.session_state.chat_history.append(("user", user_input))

        # detect add-on mentions
        message_lower = user_input.lower()
        addon_matches = [k for k in AVAILABLE_EXTRAS if k.lower() in message_lower]
        st.session_state.pending_addon_request = addon_matches if addon_matches else []

        with st.spinner("🤖 Thinking..."):
            is_guest = st.session_state.guest_status == "Yes"
            response = st.session_state.bot.ask(user_input, user_type=is_guest)
            st.session_state.response = response
            log_chat(coming_from, st.session_state.session_id, user_input, response,
                     st.session_state.predicted_intent, is_guest)

        st.chat_message("assistant").markdown(response)
        st.session_state.chat_history.append(("assistant", response))

    # --- Add-on quick flow (existing) ---------------------------------------
    if st.session_state.get("pending_addon_request"):
        st.markdown("### 🧾 Confirm Add-on Services")
        st.info(f"Would you like to pay for: {', '.join(st.session_state.pending_addon_request)}?")
        col1, col2 = st.columns(2)
        with col1:
            confirm = st.button("💳 Yes, generate payment link")
        with col2:
            cancel = st.button("❌ No, maybe later")
        if confirm:
            extra_keys = [AVAILABLE_EXTRAS[k] for k in st.session_state.pending_addon_request]
            addon_url = create_addon_checkout_session(session_id=st.session_state.session_id, extras=extra_keys)
            if addon_url:
                st.success("🧾 Add-on payment link generated.")
                st.markdown(f"[💳 Pay for Add-ons]({addon_url})", unsafe_allow_html=True)
            else:
                st.error("⚠️ Could not generate payment link.")
            st.session_state.pending_addon_request = []
        if cancel:
            st.session_state.pending_addon_request = []

    # --- Pre-check-in booking intent handling --------------------------------
    if st.session_state.get("predicted_intent") in ("payment_request", "booking_request"):
        st.markdown("### 🛏️ Start Booking (Pre-check-in)")
        with st.form("booking_dates_form"):
            check_in = st.date_input("Check-in Date", value=date.today())
            check_out = st.date_input("Check-out Date", value=date.today())
            guests = st.number_input("Number of guests", min_value=1, step=1, value=2)
            preferences = st.text_input("Preferences (e.g., king bed, vegetarian breakfast)")
            collect_whatsapp = st.text_input("WhatsApp number (optional, E.164, e.g. +9198... )", value="")
            submitted = st.form_submit_button("Show available rooms")
            if submitted:
                st.session_state.booking_details = {
                    "check_in": check_in,
                    "check_out": check_out,
                    "guests": guests,
                    "preferences": preferences,
                    "whatsapp_number": collect_whatsapp.strip()
                }
                st.session_state.show_room_options = True

    # --- Show room options using DB + dynamic pricing ------------------------
    if st.session_state.get("show_room_options"):
        st.markdown("### 🏨 Available Rooms & Media Previews")
        db = SessionLocal()
        
        try:

            rooms = db.query(Room).all()
            if not rooms:
                st.warning("No rooms found in DB. Seed rooms first.")
            else:
                ci = st.session_state.booking_details["check_in"]
                co = st.session_state.booking_details["check_out"]
                # ensure date objects
                if isinstance(ci, str):
                    ci = datetime.fromisoformat(ci).date()
                if isinstance(co, str):
                    co = datetime.fromisoformat(co).date()

                for r in rooms:
                    try:
                        price, nights = calculate_price(db, r, ci, co)  # using your app/pricing.py
                    except Exception:
                        price, nights = r.base_price, 1

                    cols = st.columns([1, 2])
                    with cols[0]:
                        first_media = (r.media or [None])[0]
                        if first_media:
                            if "youtube" in first_media or "youtu.be" in first_media:
                                thumb = youtube_thumbnail(first_media)
                                if thumb:
                                    st.image(thumb, caption=f"{r.name} — ₹{price} total ({nights} nights)")
                                else:
                                    st.write(f"{r.name} — ₹{price} total ({nights} nights)")
                            else:
                                thumb = instagram_oembed_thumb(first_media)
                                if thumb:
                                    st.image(thumb, caption=f"{r.name} — ₹{price} total ({nights} nights)")
                                else:
                                    st.image(first_media, caption=f"{r.name} — ₹{price} total ({nights} nights)")
                        else:
                            st.write(f"**{r.name}** — ₹{price} total ({nights} nights)")

                    with cols[1]:
                        st.write(f"**{r.name}** — {r.room_type}")
                        st.write(f"Capacity: {r.capacity}  • Units: {r.total_units}")
                        st.write(f"**Total: ₹{price}** for {nights} nights")
                        # show youtube inline player if present
                        for m in (r.media or []):
                            if "youtube" in m or "youtu.be" in m:
                                # show video (Streamlit will embed)
                                st.video(m)
                        # booking action
                        if st.button(f"Book {r.name} — ₹{price}", key=f"book_{r.id}"):
                            # create a pending booking record and create a checkout session
                            booking_id = str(uuid.uuid4())
                            booking = Booking(
                                id=booking_id,
                                guest_name=(st.session_state.get("user_input") or "Guest"),
                                guest_phone=st.session_state.booking_details.get("whatsapp_number", ""),
                                room_id=r.id,
                                check_in=ci,
                                check_out=co,
                                price=price,
                                status=BookingStatus.pending,
                                channel="web",
                                channel_user=st.session_state.booking_details.get("whatsapp_number", "") or None
                            )
                            db.add(booking)
                            db.commit()
                            # create checkout session (robust call that accepts either object or URL)
                            try:
                                # try the canonical call (booking_id, amount)
                                sess_obj = None
                                try:
                                    sess_obj = create_checkout_session(booking_id, price)
                                except TypeError:
                                    # try keyword form (some implementations expect booking_id=..., amount=...)
                                    sess_obj = create_checkout_session(booking_id=booking_id, amount=price)
                                checkout_url = _checkout_url_from_session(sess_obj)
                                # if function returned a URL str directly, sess_obj might be str
                                if checkout_url is None and isinstance(sess_obj, str):
                                    checkout_url = sess_obj
                                # if still none, try to get id and build fallback url (not guaranteed)
                                if checkout_url is None and hasattr(sess_obj, "id"):
                                    booking.stripe_session_id = getattr(sess_obj, "id")
                                    db.commit()
                                    # some setups cannot provide direct checkout url; ask user to open stripe dashboard
                                    checkout_url = None
                                else:
                                    # save session id if present
                                    if hasattr(sess_obj, "id"):
                                        booking.stripe_session_id = getattr(sess_obj, "id")
                                        db.commit()
                            except Exception as e:
                                st.error(f"Failed to create checkout session: {e}")
                                db.rollback()
                                db.close()
                                st.stop()

                            # Generate a temporary clickable QR that links to the checkout page (if we have a URL)
                            qr_filename = f"checkout_{booking_id}.png"
                            local_qr_path, public_qr = None, None
                            if checkout_url:
                                local_qr_path, public_qr = save_qr_to_static(checkout_url, qr_filename)
                                st.success("Checkout created — complete payment to confirm booking.")
                                st.markdown(f"[💳 Proceed to payment]({checkout_url})", unsafe_allow_html=True)
                                st.image(generate_qr_code_bytes(checkout_url), width=240, caption="Scan to open payment on mobile (temporary)")
                            else:
                                st.warning("Checkout session created but no public URL was returned. Complete payment via Stripe Dashboard (or update create_checkout_session to return url).")

                            # store checkout_info in session so web UI can show summary
                            st.session_state.checkout_info = {
                                "booking_id": booking_id,
                                "room_name": r.name,
                                "price": price,
                                "nights": nights,
                                "checkout_url": checkout_url,
                                "qr_local": local_qr_path,
                                "qr_public": public_qr
                            }
        finally:
            db.close()

    # --- Show checkout summary if created -----------------------------------
    if st.session_state.get("checkout_info"):
        info = st.session_state.checkout_info
        st.markdown("---")
        st.markdown("### ✅ Booking Created (Pending Payment)")
        st.write(f"Booking ID: `{info['booking_id']}`")
        st.write(f"Room: **{info['room_name']}**")
        st.write(f"Amount: ₹{info['price']}")
        st.markdown("Complete payment using the link above. After successful payment Stripe will call your webhook and finalize the booking (generate final QR & send WhatsApp if WhatsApp number provided).")

    # --- Fallback booking form (keeps previous behaviour) --------------------
    if st.session_state.get("predicted_intent") == "payment_request" and not st.session_state.get("pending_addon_request"):
        st.markdown("### 🛏️ Book a Room / Add-on Services (Fallback)")
        with st.form("booking_form"):
            room_type = st.selectbox("Room Type (optional)", ["None", "Standard", "Deluxe", "Executive", "Family", "Suite"])
            nights = st.number_input("Number of nights", min_value=1, step=1, value=1)
            payment_method = st.radio("Payment Method", ["Online", "Cash on Arrival"])
            price_map = {"Standard":12500,"Deluxe":17000,"Executive":23000,"Family":27500,"Suite":34000}
            if room_type != "None":
                st.markdown(f"💰 **Room Total: ₹{price_map[room_type] * nights}**")
            else:
                st.markdown("💡 You can skip room booking and only pay for add-ons.")
            st.markdown("### 🧖‍♀️ Optional Add-ons")
            selected_extras = st.multiselect("Choose your add-ons:", list(AVAILABLE_EXTRAS.keys()))
            if st.form_submit_button("✅ Proceed"):
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

    st.markdown('</div>', unsafe_allow_html=True)
