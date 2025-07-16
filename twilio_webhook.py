from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from app.agents.qa_agent import ConciergeBot  # your bot logic
from app.services.logger import log_chat

app = Flask(__name__)
bot = ConciergeBot()

@app.route("/whatsapp", methods=["POST"])
def whatsapp_reply():
    incoming_msg = request.form.get('Body')
    user_number = request.form.get('From')

    print(f"[📩 Incoming from {user_number}]: {incoming_msg}")

    if incoming_msg:
        response = bot.ask(incoming_msg)
    else:
        response = "Sorry, I didn't receive a valid message."
    
    log_chat("Whatsapp", user_number, incoming_msg, response)

    msg = MessagingResponse()
    msg.message(response)

    return str(msg)


# Function to append every Whatsapp interaction to a csv


if __name__ == "__main__":
    app.run(debug=True, port=5002)
