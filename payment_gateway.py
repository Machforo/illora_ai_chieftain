# app/services/payment_gateway.py

import stripe
import os
import dotenv
from config import Config

stripe.api_key = Config.STRIPE_SECRET_KEY
if not stripe.api_key:
    raise Exception(" STRIPE_SECRET_KEY not found")

ROOM_PRICING = {
    "deluxe": 4000,
    "executive": 6000,
    "family": 8000
}

YOUR_DOMAIN = 'http://localhost:8501'
def create_checkout_session(session_id, room_type, nights, cash):
    try:
        price_per_night = ROOM_PRICING.get(room_type.lower(), 0)
        if price_per_night == 0:
            raise ValueError("Invalid room type")

        amount = 2000 if cash else price_per_night * nights

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {
                            'name': f"{room_type.title()} Room Booking",
                            'description': "Includes breakfast, pool & gym access",
                        },
                        'unit_amount': amount * 100,
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=f"{YOUR_DOMAIN}?payment=success&session_id={session_id}",
            cancel_url=f"{YOUR_DOMAIN}?payment=cancel&session_id={session_id}",

        
        )

        print("✅ Stripe session created:", checkout_session.url)
        
        return checkout_session.url

    except Exception as e:
        print(f"[Stripe Checkout Error] {e}")
        return None
