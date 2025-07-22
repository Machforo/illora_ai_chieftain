# app/twilio_webhook.py

from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from app.agents.qa_agent import ConciergeBot
from app.services.payment_gateway import create_checkout_session
from app.logger import log_chat
from app.services.intent_classifier import classify_intent

app = Flask(__name__)  # ✅ Fixed

bot = ConciergeBot()
session_data = {}

ROOM_PRICES = {"Deluxe": 4000, "Executive": 6000, "Family": 8000}
ROOM_OPTIONS = ["Deluxe", "Executive", "Family"]

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.form.get('Body', "").strip()
    user_number = request.form.get('From')
    print(incoming_msg)
    msg = MessagingResponse()
    response = ""

    if user_number not in session_data:
        session_data[user_number] = {"stage": "start"}

    user_session = session_data[user_number]
    stage = user_session["stage"]
    print(stage)

    # Step 1: Triggered by payment intent
    if stage == "start":
        intent = classify_intent(incoming_msg.lower())
        if intent == "payment_request":
            user_session["stage"] = "room"
            response = (
                "🏨 Welcome to *LUXORIA SUITES* – a premium stay experience.\n\n"
                "Please choose your room type:\n"
                "1️⃣ Deluxe Room – ₹4000/night\n"
                "2️⃣ Executive Room – ₹6000/night\n"
                "3️⃣ Family Room – ₹8000/night\n\n"
                "Reply with *1*, *2*, or *3* to proceed."
            )
        else:
            response = bot.ask(incoming_msg)

    # Step 2: Room type selection
    elif stage == "room":
        if incoming_msg in ["1", "2", "3"]:
            selected_room = ROOM_OPTIONS[int(incoming_msg) - 1]
            user_session["room_type"] = selected_room
            user_session["stage"] = "nights"
            response = (
                f"🕒 Great choice! How many nights would you like to stay in our *{selected_room} Room*?\n"
                "Please reply with a number."
            )
        else:
            response =  bot.ask(incoming_msg)

    # Step 3: Nights input
    elif stage == "nights":
        if incoming_msg.isdigit() and int(incoming_msg) > 0:
            user_session["nights"] = int(incoming_msg)
            user_session["stage"] = "payment"
            response = (
                "💳 How would you like to pay?\n"
                "1️⃣ Online Payment\n"
                "2️⃣ Cash on Arrival\n\n"
                "Reply with *1* or *2*."
            )
        else:
            response =  bot.ask(incoming_msg)

    # Step 4: Payment method
    elif stage == "payment":
        if incoming_msg in ["1", "2"]:
            payment_mode = "Online" if incoming_msg == "1" else "Cash"
            user_session["payment"] = payment_mode
            user_session["stage"] = "confirm"

            room = user_session["room_type"]
            nights = user_session["nights"]
            price = ROOM_PRICES[room] * nights
            user_session["price"] = price

            response = (
                f"🧾 *Booking Summary:*\n"
                f"🏨 Room: *{room}*\n"
                f"🌙 Nights: *{nights}*\n"
                f"💰 Payment: *{payment_mode}*\n"
                f"💵 Total: ₹{price}\n\n"
                f"✅ Please reply with *Yes* to confirm your booking."
            )
        else:
            response =  bot.ask(incoming_msg)

    # Step 5: Confirmation
    elif stage == "confirm":
        if incoming_msg.lower() == "yes":
            room = user_session["room_type"]
            nights = user_session["nights"]
            payment_mode = user_session["payment"]

            pay_url = create_checkout_session(
                session_id=user_number,
                room_type=room,
                nights=nights,
                cash=(payment_mode == "Cash")
            )

            if pay_url:
                response = (
                    f"🎉 *Your booking at LUXORIA SUITES is confirmed!*\n\n"
                    f"To complete the process, please follow this link:\n{pay_url}"
                )
            else:
                response = "⚠ Payment link could not be generated. Please try again."

            # Reset session
            session_data[user_number] = {"stage": "start"}
        else:
            response =  bot.ask(incoming_msg)
    # Fallback for unexpected input
    else:
        response = bot.ask(incoming_msg)
    
    print(response)

    log_chat("Whatsapp", user_number, incoming_msg, response)
    msg.message(response)
    return str(msg)

# ✅ Fixed incorrect block
if __name__ == "__main__":
    app.run(debug=True, port=5002)
