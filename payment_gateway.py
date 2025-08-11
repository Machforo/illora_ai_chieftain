# payment_gateway.py (fixed)
import stripe
from config import Config

stripe.api_key = Config.STRIPE_SECRET_KEY
if not stripe.api_key:
    raise Exception("STRIPE_SECRET_KEY not found")

YOUR_DOMAIN = getattr(Config, "BASE_URL", "http://localhost:8501")
if not (YOUR_DOMAIN.startswith("http://") or YOUR_DOMAIN.startswith("https://")):
    raise ValueError("Config.BASE_URL must be an absolute URL (http(s)://...)")

# Room pricing (INR per night) -- canonicalized to lowercase keys
RAW_ROOM_PRICING = {
    "Safari Tent": 12000,
    "Star Bed Suite": 18000,
    "double room": 10000,
    "suite": 34000,
    "family": 27500
}
# create lowercase-key map for robust lookups
ROOM_PRICING = {k.lower(): v for k, v in RAW_ROOM_PRICING.items()}

# Add-on pricing (INR)
EXTRA_PRICING = {
    "spa_massage": 3000, "spa_aromatherapy": 3500, "spa_hot_stone": 4000,
    "juice": 510, "mocktail": 935, "cocktail": 1275, "milkshake": 595,
    "smoothie": 595, "bbq_sliders": 595, "masai_spiced_nuts": 510,
    "cheese_platter": 765, "chocolate_brownie": 510, "cheesecake": 510,
    "banana_spring_roll": 510, "stuffed_mini_peppers": 595, "vegetable_skewers": 595
}

COMPLIMENTARY_ITEMS = [
    "tea", "coffee", "earl_grey", "green_tea", "espresso", "latte",
    "americano", "cappuccino", "masala_tea", "jasmine_tea", "darjeeling"
]

def create_checkout_session(session_id, room_type, nights, cash=False, extras=None):
    try:
        extras = extras or []
        nights = int(nights)

        # normalize room_type for lookup
        lookup_key = (room_type or "").strip().lower()
        price_per_night = ROOM_PRICING.get(lookup_key)
        if price_per_night is None:
            raise ValueError(f"Invalid room_type for pricing lookup: {room_type!r}")

        room_amount = 2000 if cash else price_per_night * nights

        total_amount = room_amount
        line_items = [{
            'price_data': {
                'currency': 'inr',
                'product_data': {
                    'name': f"{room_type} Room Booking",
                    'description': f"{nights} night(s) stay"
                },
                'unit_amount': int(room_amount * 100)
            },
            'quantity': 1
        }]

        for extra in extras:
            key = extra.lower().replace(" ", "_")
            if key in COMPLIMENTARY_ITEMS:
                continue
            extra_price = EXTRA_PRICING.get(key)
            if extra_price:
                total_amount += extra_price
                line_items.append({
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {'name': extra.replace("_", " ").title()},
                        'unit_amount': int(extra_price * 100)
                    },
                    'quantity': 1
                })

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f"{YOUR_DOMAIN}?payment=success&session_id={session_id}",
            cancel_url=f"{YOUR_DOMAIN}?payment=cancel&session_id={session_id}",
        )

        return checkout_session.url  # always return the URL (string)

    except Exception as e:
        print(f"[Stripe Checkout Error] {e}")
        return None


def create_addon_checkout_session(session_id, extras):
    try:
        extras = extras or []
        line_items = []
        for extra in extras:
            key = extra.lower().replace(" ", "_")
            if key in COMPLIMENTARY_ITEMS:
                continue
            extra_price = EXTRA_PRICING.get(key)
            if extra_price:
                line_items.append({
                    'price_data': {
                        'currency': 'inr',
                        'product_data': {'name': extra.replace("_", " ").title()},
                        'unit_amount': int(extra_price * 100)
                    },
                    'quantity': 1
                })
        if not line_items:
            return None

        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=f"{YOUR_DOMAIN}?payment=success&session_id={session_id}",
            cancel_url=f"{YOUR_DOMAIN}?payment=cancel&session_id={session_id}",
        )
        return checkout_session.url

    except Exception as e:
        print(f"[Stripe Add-on Error] {e}")
        return None
