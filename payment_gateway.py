import stripe
from config import Config

# Stripe setup
stripe.api_key = Config.STRIPE_SECRET_KEY
if not stripe.api_key:
    raise Exception("STRIPE_SECRET_KEY not found")

YOUR_DOMAIN = 'http://localhost:8501'  # Change for production

# Room pricing (INR per night)
ROOM_PRICING = {
    "standard": 12500,
    "deluxe": 17000,
    "executive": 23000,
    "suite": 34000,
    "family": 27500
}

# Add-on pricing (INR)
EXTRA_PRICING = {
    # Spa services
    "spa_massage": 3000,
    "spa_aromatherapy": 3500,
    "spa_hot_stone": 4000,

    # Food & drink
    "juice": 510,
    "mocktail": 935,
    "cocktail": 1275,
    "milkshake": 595,
    "smoothie": 595,
    "bbq_sliders": 595,
    "masai_spiced_nuts": 510,
    "cheese_platter": 765,
    "chocolate_brownie": 510,
    "cheesecake": 510,
    "banana_spring_roll": 510,
    "stuffed_mini_peppers": 595,
    "vegetable_skewers": 595
}

# Complimentary items
COMPLIMENTARY_ITEMS = [
    "tea", "coffee", "earl_grey", "green_tea", "espresso", "latte",
    "americano", "cappuccino", "masala_tea", "jasmine_tea", "darjeeling"
]

# ---------------------------------------
# ✅ 1. Room Booking Only (Initial Step)
# ---------------------------------------
def create_checkout_session(session_id, room_type, nights, cash=False, extras=None):
    try:
        room_type = room_type.lower()
        nights = int(nights)
        extras = extras or []

        price_per_night = ROOM_PRICING.get(room_type)
        if not price_per_night:
            raise ValueError(f"Invalid room type: {room_type}")

        # Base amount (₹2000 advance for cash mode)
        room_amount = 2000 if cash else price_per_night * nights
        total_amount = room_amount

        # Base room line item
        line_items = [{
            'price_data': {
                'currency': 'inr',
                'product_data': {
                    'name': f"{room_type.title()} Room Booking",
                    'description': f"{nights} night(s) stay with breakfast, pool & gym access"
                },
                'unit_amount': room_amount * 100
            },
            'quantity': 1
        }]

        # Optional add-ons
        for extra in extras:
            key = extra.lower().replace(" ", "_")
            if key in COMPLIMENTARY_ITEMS:
                print(f"[Info] Skipped complimentary item: {extra}")
                continue

            extra_price = EXTRA_PRICING.get(key)
            if extra_price:
                total_amount += extra_price
                line_items.append({
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {
                            'name': extra.replace("_", " ").title(),
                            'description': "Optional add-on service"
                        },
                        'unit_amount': extra_price * 100
                    },
                    'quantity': 1
                })
            else:
                print(f"[Warning] Unknown add-on: {extra}")

        # Stripe session creation
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f"{YOUR_DOMAIN}?payment=success&session_id={session_id}",
            cancel_url=f"{YOUR_DOMAIN}?payment=cancel&session_id={session_id}",
        )

        print("✅ Room booking Stripe session created:", checkout_session.url)
        return checkout_session.url

    except Exception as e:
        print(f"[Stripe Checkout Error] {e}")
        return None

# ---------------------------------------
# ✅ 2. Later Add-on Booking (Separate)
# ---------------------------------------
def create_addon_checkout_session(session_id, extras):
    try:
        extras = extras or []
        total_amount = 0
        line_items = []

        for extra in extras:
            key = extra.lower().replace(" ", "_")
            if key in COMPLIMENTARY_ITEMS:
                print(f"[Info] Skipped complimentary item: {extra}")
                continue

            extra_price = EXTRA_PRICING.get(key)
            if extra_price:
                total_amount += extra_price
                line_items.append({
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {
                            'name': extra.replace("_", " ").title(),
                            'description': "Optional Add-on"
                        },
                        'unit_amount': extra_price * 100
                    },
                    'quantity': 1
                })
            else:
                print(f"[Warning] Unknown add-on: {extra}")

        if not line_items:
            print("[Error] No valid add-ons selected.")
            return None

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f"{YOUR_DOMAIN}?payment=success&session_id={session_id}",
            cancel_url=f"{YOUR_DOMAIN}?payment=cancel&session_id={session_id}",
        )

        print("✅ Add-on Stripe session created:", checkout_session.url)
        return checkout_session.url

    except Exception as e:
        print(f"[Stripe Add-on Error] {e}")
        return None
