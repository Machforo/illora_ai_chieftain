# web_ui.py (UPDATED — uses illora.checkin_app.models as single source-of-truth)
import os
import uuid
import qrcode
import base64
import sqlite3
import json
from io import BytesIO
from datetime import datetime, date
from pathlib import Path

import streamlit as st
from PIL import Image
from logger import log_chat

# existing project imports (kept; adjusted)
from payment_gateway import create_checkout_session, create_addon_checkout_session
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

# Static dirs
STATIC_DIR = Path("static")
STATIC_DIR.mkdir(parents=True, exist_ok=True)
UPLOAD_DIR = Path("uploads/id_proofs")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MENU_FILE = Path(__file__).parent / "menu.json"
with open(MENU_FILE, "r", encoding="utf-8") as f:
    MENU = json.load(f)

# Flatten items for UI selection
AVAILABLE_EXTRAS = {}
EXTRAS_PRICE_BY_KEY = {}
for category, items in MENU.items():
    if category == "complimentary":
        continue
    for display_name, _price in items.items():
        label = display_name.replace("_", " ").title()
        key = display_name.lower().replace(" ", "_")
        AVAILABLE_EXTRAS[label] = key
        EXTRAS_PRICE_BY_KEY[key] = _price

# --- Minimal user db (SQLite; tiny, non-invasive) ---------------------------
USER_DB_PATH = "illora_user_gate.db"

def init_user_db():
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS users(
        uid TEXT PRIMARY KEY,
        username TEXT,
        booked INTEGER DEFAULT 0,
        id_proof_uploaded INTEGER DEFAULT 0,
        due_items TEXT DEFAULT '[]'   -- JSON array of addon keys queued as Pay Later
    )""")
    conn.commit()
    conn.close()

def get_user_row(uid):
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("SELECT uid, username, booked, id_proof_uploaded, due_items FROM users WHERE uid=?", (uid,))
    row = c.fetchone()
    conn.close()
    return row

def ensure_user(uid, username):
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users(uid, username) VALUES(?,?)", (uid, username))
    conn.commit()
    conn.close()

def set_booked(uid, booked: int):
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET booked=? WHERE uid=?", (booked, uid))
    conn.commit()
    conn.close()

def set_id_proof(uid, uploaded: int = 1):
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET id_proof_uploaded=? WHERE uid=?", (uploaded, uid))
    conn.commit()
    conn.close()

def get_due_items(uid) -> list:
    row = get_user_row(uid)
    if not row:
        return []
    try:
        return json.loads(row[4] or "[]")
    except Exception:
        return []

def add_due_items(uid, new_items: list):
    current = get_due_items(uid)
    current.extend(new_items)
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET due_items=? WHERE uid=?", (json.dumps(current), uid))
    conn.commit()
    conn.close()

def clear_due_items(uid):
    conn = sqlite3.connect(USER_DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET due_items='[]' WHERE uid=?", (uid,))
    conn.commit()
    conn.close()

def due_total_from_items(items: list) -> int:
    return sum(EXTRAS_PRICE_BY_KEY.get(k, 0) for k in items)

# --- Helpers ----------------------------------------------------------------
def get_base64_of_bin_file(bin_file):
    with open(bin_file, "rb") as f:
        return base64.b64encode(f.read()).decode()

def generate_qr_code_bytes(link: str) -> bytes:
    """Return PNG bytes of a QR for a given link (temporary checkout QR)."""
    qr = qrcode.QRCode(version=1, box_size=6, border=2)
    qr.add_data(link)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
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
    if isinstance(sess, str):
        return sess
    if hasattr(sess, "url"):
        try:
            return getattr(sess, "url")
        except Exception:
            pass
    try:
        if isinstance(sess, dict):
            if "url" in sess:
                return sess["url"]
            if "checkout_url" in sess:
                return sess["checkout_url"]
    except Exception:
        pass
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
        background-color: rgba(30, 30, 30, 0.6);
        padding: 12px;
        border-radius: 12px;
        margin: 6px 0;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        font-weight: 700;
    }}
    .stButton>button {{
        background: linear-gradient(135deg, #4CAF50, #2E8B57); /* green gradient */
        color: white !important;  /* text color */
        border-radius: 12px;
        padding: 10px 20px;
        border: none;
        font-weight: bold;
        font-size: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.25);
        transition: transform 0.2s ease, background 0.3s ease;
    }}
    .stButton>button:hover {{
        transform: scale(1.08);
        background: linear-gradient(135deg, #45a049, #1e7a46); /* hover effect */
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
# staged booking confirmation
if "booking_to_confirm" not in st.session_state:
    st.session_state.booking_to_confirm = None
# user gate
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None

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

    # ---- USERNAME + UID GATE (minimal, additive) ---------------------------
    init_user_db()
    if not st.session_state.user_profile:
        st.markdown("### 🔐 Identify Yourself")
        with st.form("user_gate_form"):
            in_username = st.text_input("Username")
            in_uid = st.text_input("UID")
            proceed = st.form_submit_button("Continue")
        if not proceed:
            st.info("👉 Please enter your **Username** and **UID** to continue.")
            st.markdown('</div>', unsafe_allow_html=True)
            st.stop()
        if in_username and in_uid:
            ensure_user(in_uid, in_username)
            row = get_user_row(in_uid)
            st.session_state.user_profile = {
                "uid": row[0],
                "username": row[1],
                "booked": int(row[2] or 0),
                "id_proof_uploaded": int(row[3] or 0),
            }
        else:
            st.warning("Please fill both Username and UID.")
            st.markdown('</div>', unsafe_allow_html=True)
            st.stop()

    uid = st.session_state.user_profile["uid"]
    username = st.session_state.user_profile["username"]
    booked_flag = int(st.session_state.user_profile["booked"])
    id_uploaded_flag = int(st.session_state.user_profile["id_proof_uploaded"])

    # status row
    due_items_now = get_due_items(uid)
    due_total_now = due_total_from_items(due_items_now)
    st.markdown(
        f"**User:** `{username}` • **UID:** `{uid}`  |  "
        f"**Booked:** {'✅' if booked_flag else '❌'}  |  "
        f"**ID Proof:** {'✅' if id_uploaded_flag else '❌'}  |  "
        f"**Pending Balance:** ₹{due_total_now}"
    )
    st.markdown("---")

    # ---- Mobile access QR
    st.markdown("### 📱 Access this Assistant on Mobile")
    qr_img = generate_qr_code_bytes(QR_LINK)
    st.image(qr_img, width=180, caption="Scan to open on your phone")
    st.markdown("---")

    # show chat history
    for role, msg in st.session_state.chat_history:
        with st.chat_message(role):
            st.markdown(msg)

    # ---- Concierge Chat (generic until ID proof uploaded)
    st.markdown("### 💬 Concierge Chat")
    user_input = st.chat_input("Ask me anything about ILLORA Retreat")
    coming_from = "Web"

    if user_input:
        st.session_state.user_input = user_input
        st.session_state.predicted_intent = classify_intent(user_input)
        st.chat_message("user").markdown(user_input)
        st.session_state.chat_history.append(("user", user_input))

        # detect add-on mentions (kept)
        message_lower = user_input.lower()
        addon_matches = [k for k in AVAILABLE_EXTRAS if k.lower() in message_lower]
        st.session_state.pending_addon_request = addon_matches if addon_matches else []

        # generic answers if ID proof not uploaded; full otherwise
        with st.spinner("🤖 Thinking..."):
            is_guest = st.session_state.guest_status == "Yes"
            response = st.session_state.bot.ask(user_input, user_type=is_guest)
            # (Note: keeping bot behavior intact; we simply gate add-on/pay actions elsewhere)
            st.session_state.response = response
            log_chat(coming_from, st.session_state.session_id, user_input, response,
                     st.session_state.get("predicted_intent"), is_guest)

        # If ID not uploaded, prepend a small note
        if not id_uploaded_flag:
            response = "*(Generic access — please complete ID verification after booking to unlock full features.)*\n\n" + str(response)

        
        st.session_state.chat_history.append(("assistant", response))
        st.chat_message("assistant").markdown(response)

    # --- Add-on quick flow (extended with Pay Later) -------------------------
    if st.session_state.get("pending_addon_request"):
        st.markdown("### 🧾 Confirm Add-on Services")
        chosen_labels = st.session_state.pending_addon_request
        st.info(f"Would you like to proceed with: {', '.join(chosen_labels)}?")
        col1, col2, col3 = st.columns(3)
        with col1:
            confirm = st.button("💳 Pay Now (generate link)")
        with col2:
            pay_later = st.button("⏳ Pay Later")
        with col3:
            cancel = st.button("❌ Cancel")

        extra_keys = [AVAILABLE_EXTRAS[k] for k in chosen_labels]

        if confirm:
            addon_url = create_addon_checkout_session(session_id=st.session_state.session_id, extras=extra_keys)
            if addon_url:
                st.success("🧾 Add-on payment link generated.")
                st.markdown(f"[💳 Pay for Add-ons]({addon_url})", unsafe_allow_html=True)
            else:
                st.error("⚠️ Could not generate payment link.")
            st.session_state.pending_addon_request = []

        if pay_later:
            # accumulate in user DB; sum will be computed from MENU at checkout time
            add_due_items(uid, extra_keys)
            total_now = due_total_from_items(get_due_items(uid))
            st.success(f"⏳ Added to your tab. Current pending balance: ₹{total_now}")
            st.session_state.pending_addon_request = []

        if cancel:
            st.session_state.pending_addon_request = []

    # --- Pre-check-in booking intent handling (kept) -------------------------
    # Allowed even before ID upload (per test flow). Booking unlocks ID step.
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

    # --- Show room options using DB + dynamic pricing (kept) -----------------
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
                if isinstance(ci, str):
                    ci = datetime.fromisoformat(ci).date()
                if isinstance(co, str):
                    co = datetime.fromisoformat(co).date()

                for r in rooms:
                    try:
                        price, nights = calculate_price(db, r, ci, co)
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
                        for m in (r.media or []):
                            if "youtube" in m or "youtu.be" in m:
                                st.video(m)

                        # ---------- Booking: start (stage) ----------
                        start_key = f"start_book_{r.id}"
                        if st.button(f"Book {r.name} — ₹{price}", key=start_key):
                            st.session_state.booking_to_confirm = {
                                "booking_id": str(uuid.uuid4()),
                                "room_id": r.id,
                                "room_name": r.name,
                                "check_in": ci.isoformat(),
                                "check_out": co.isoformat(),
                                "price": price,
                                "nights": nights,
                                "guest_name": (st.session_state.get("user_input") or username or "Guest"),
                                "guest_phone": st.session_state.booking_details.get("whatsapp_number", "")
                            }

                        # ---------- If staged booking matches this room, show confirm UI ----------
                        btc = st.session_state.get("booking_to_confirm")
                        if btc and btc.get("room_id") == r.id:
                            st.markdown("---")
                            st.markdown(f"**Confirm booking for**: **{btc['room_name']}**  •  ₹{btc['price']}  •  {btc['nights']} nights")
                            payment_method = st.selectbox("Payment Method", ["Online", "Cash on Arrival"], key=f"pm_{r.id}")
                            notes = st.text_input("Special requests (optional)", value=st.session_state.booking_details.get("preferences",""), key=f"notes_{r.id}")

                            col_confirm, col_cancel = st.columns([1,1])
                            with col_confirm:
                                if st.button("✅ Confirm & Create Payment", key=f"confirm_{r.id}"):
                                    booking_id = btc["booking_id"]
                                    try:
                                        booking = Booking(
                                            id=booking_id,
                                            guest_name=btc["guest_name"],
                                            guest_phone=btc["guest_phone"],
                                            room_id=btc["room_id"],
                                            check_in=datetime.fromisoformat(btc["check_in"]).date(),
                                            check_out=datetime.fromisoformat(btc["check_out"]).date(),
                                            price=btc["price"],
                                            status=BookingStatus.pending,
                                            channel="web",
                                            channel_user=btc["guest_phone"] or None
                                        )
                                        db.add(booking)
                                        db.commit()
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Failed to create booking record: {e}")
                                        st.session_state.booking_to_confirm = None
                                        raise

                                    checkout_url = None
                                    stripe_session_id = None
                                    try:
                                        with st.spinner("Creating payment session..."):
                                            stripe_sess = create_checkout_session(
                                                session_id=booking_id,
                                                room_type=r.name,
                                                nights=btc["nights"],
                                                cash=(payment_method == "Cash on Arrival"),
                                                extras=[]
                                            )
                                            checkout_url = _checkout_url_from_session(stripe_sess)
                                            if hasattr(stripe_sess, "id"):
                                                stripe_session_id = getattr(stripe_sess, "id")
                                            elif isinstance(stripe_sess, dict) and "id" in stripe_sess:
                                                stripe_session_id = stripe_sess.get("id")
                                    except Exception as e:
                                        db.rollback()
                                        st.error(f"Failed to create checkout session: {e}")
                                        st.session_state.booking_to_confirm = None
                                        raise

                                    try:
                                        if stripe_session_id:
                                            if hasattr(booking, "stripe_session_id"):
                                                booking.stripe_session_id = stripe_session_id
                                            else:
                                                setattr(booking, "stripe_session_id", stripe_session_id)
                                            db.commit()
                                    except Exception:
                                        db.rollback()

                                    local_qr_path = None
                                    public_qr = None
                                    if checkout_url:
                                        try:
                                            qr_filename = f"checkout_{booking_id}.png"
                                            local_qr_path, public_qr = save_qr_to_static(checkout_url, qr_filename)
                                            try:
                                                if hasattr(booking, "qr_path"):
                                                    booking.qr_path = public_qr
                                                else:
                                                    setattr(booking, "qr_path", public_qr)
                                                db.commit()
                                            except Exception:
                                                db.rollback()
                                        except Exception:
                                            pass

                                        st.success("Checkout created — complete payment to confirm booking.")
                                        st.markdown(f"[💳 Proceed to payment]({checkout_url})", unsafe_allow_html=True)
                                        st.image(generate_qr_code_bytes(checkout_url), width=240, caption="Scan to open payment on mobile")

                                        # --- NEW (minimal): testing flow -> ask for ID proof right after link ---
                                        st.info("🔒 For testing: please upload your ID proof to unlock full bot access.")
                                        id_file = st.file_uploader("Upload ID proof (JPG/PNG/PDF)", type=["jpg","jpeg","png","pdf"], key=f"id_{booking_id}")
                                        if id_file is not None:
                                            # save file locally with uid + timestamp
                                            ext = Path(id_file.name).suffix.lower() or ".bin"
                                            save_path = UPLOAD_DIR / f"{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                                            with open(save_path, "wb") as f:
                                                f.write(id_file.read())
                                            set_id_proof(uid, 1)
                                            st.session_state.user_profile["id_proof_uploaded"] = 1
                                            st.success("✅ ID proof submitted. Full access enabled!")

                                        # mark user as 'booked' (per requested testing flow)
                                        set_booked(uid, 1)
                                        st.session_state.user_profile["booked"] = 1
                                    else:
                                        st.warning("Checkout created but no public URL was returned. Check your payment gateway implementation or Stripe SDK version.")

                                    st.session_state.checkout_info = {
                                        "booking_id": booking_id,
                                        "room_name": r.name,
                                        "price": btc["price"],
                                        "nights": btc["nights"],
                                        "checkout_url": checkout_url,
                                        "qr_local": local_qr_path,
                                        "qr_public": public_qr
                                    }
                                    st.session_state.booking_to_confirm = None

                            with col_cancel:
                                if st.button("❌ Cancel booking", key=f"cancel_{r.id}"):
                                    st.session_state.booking_to_confirm = None
                                    st.info("Booking cancelled.")

        finally:
            db.close()

    # --- Show checkout summary if created (kept) -----------------------------
    if st.session_state.get("checkout_info"):
        info = st.session_state.checkout_info
        st.markdown("---")
        st.markdown("### ✅ Booking Created (Pending Payment)")
        st.write(f"Booking ID: `{info['booking_id']}`")
        st.write(f"Room: **{info['room_name']}**")
        st.write(f"Amount: ₹{info['price']}")
        if info.get("checkout_url"):
            st.markdown(f"[Click here to pay]({info['checkout_url']})")
        st.markdown("After successful payment Stripe will call your webhook and finalize the booking (generate final QR & send WhatsApp if WhatsApp number provided).")

    # --- Fallback booking form (kept intact) --------------------------------
    if st.session_state.get("predicted_intent") == "payment_request" and not st.session_state.get("pending_addon_request"):
        st.markdown("### 🛏️ Book a Room / Add-on Services (Fallback)")
        with st.form("booking_form"):
            room_type = st.selectbox("Room Type (optional)", ["None", "Safari Tent", "Star Bed Suite", "double Room", "family", "suite"])
            nights = st.number_input("Number of nights", min_value=1, step=1, value=1)
            payment_method = st.radio("Payment Method", ["Online", "Cash on Arrival"])
            price_map = {
                "Safari Tent": 12000, "Star Bed Suite": 18000,
                "double room": 10000, "suite": 34000, "family": 27500
            }
            if room_type != "None":
                price_key = room_type if room_type in price_map else room_type.lower()
                room_price = price_map.get(price_key, None)
                if room_price is None:
                    st.warning("Price not found for selected room (check fallback price_map keys).")
                else:
                    st.markdown(f"💰 **Room Total: ₹{room_price * nights}**")
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
                        # ask ID proof (testing) here as well
                        st.info("🔒 For testing: please upload your ID proof to unlock full bot access.")
                        id_file_fb = st.file_uploader("Upload ID proof (JPG/PNG/PDF)", type=["jpg","jpeg","png","pdf"], key="id_fb")
                        if id_file_fb is not None:
                            ext = Path(id_file_fb.name).suffix.lower() or ".bin"
                            save_path = UPLOAD_DIR / f"{uid}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
                            with open(save_path, "wb") as f:
                                f.write(id_file_fb.read())
                            set_id_proof(uid, 1)
                            st.session_state.user_profile["id_proof_uploaded"] = 1
                            st.success("✅ ID proof submitted. Full access enabled!")
                        set_booked(uid, 1)
                        st.session_state.user_profile["booked"] = 1
                    else:
                        st.error("⚠️ Room payment link generation failed.")
                if any_addon_selected:
                    extra_keys = [AVAILABLE_EXTRAS[item] for item in selected_extras]
                    # Offer Pay Now or Pay Later choices (compact)
                    subcol1, subcol2 = st.columns(2)
                    with subcol1:
                        addon_url = create_addon_checkout_session(session_id=st.session_state.session_id, extras=extra_keys)
                        if addon_url:
                            st.success("🧾 Add-on payment link generated.")
                            st.markdown(f"[💳 Pay for Add-ons]({addon_url})", unsafe_allow_html=True)
                        else:
                            st.error("⚠️ Add-on payment link generation failed.")
                    with subcol2:
                        if st.button("⏳ Pay Later (add to tab)"):
                            add_due_items(uid, extra_keys)
                            st.success(f"Added to your tab. Current pending balance: ₹{due_total_from_items(get_due_items(uid))}")
                if not room_selected and not any_addon_selected:
                    st.warning("⚠️ Please select a room or at least one add-on to proceed.")

    # --- NEW: Checkout Pending Balance --------------------------------------
    st.markdown("---")
    st.markdown("### 🚪 Checkout — Pay Remaining Balance")
    due_items = get_due_items(uid)
    if due_items:
        pending_amt = due_total_from_items(due_items)
        st.info(f"🧾 You have **₹{pending_amt}** pending for: {', '.join(due_items)}")
        if st.button("💳 Pay Pending Balance"):
            # Use the same gateway; pass aggregated due_items so pricing comes from MENU
            due_url = create_addon_checkout_session(session_id=st.session_state.session_id, extras=due_items)
            if due_url:
                st.success("✅ Payment link generated for pending balance.")
                st.markdown(f"[Pay Pending Balance]({due_url})")
                # Do NOT clear immediately; clear after webhook confirms payment in real flows.
                # For testing/demo, you may clear immediately:
                # clear_due_items(uid)
            else:
                st.error("⚠️ Could not generate payment link for pending balance.")
    else:
        st.success("No pending balance. You're all set!")

    st.markdown('</div>', unsafe_allow_html=True)
