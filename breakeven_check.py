import os
import json
import requests
from datetime import datetime
from twilio.rest import Client

# ============================================================
# ✅ THESE COME FROM GITHUB SECRETS — DON'T PASTE HERE
# ============================================================
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]   # e.g. +12345678901
YOUR_PHONE_NUMBER  = os.environ["YOUR_PHONE_NUMBER"]    # e.g. +919876543210
TELEGRAM_TOKEN     = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]

# ============================================================
# ✅ ADD YOUR BREAKEVEN LEVELS HERE — UNLIMITED!
# Format: { price: "label" }
# ============================================================
BREAKEVEN_LEVELS = {
    83000: "BTC Long Breakeven at 83,000",
    73000: "BTC Short Breakeven at 73,000",
    90000: "BTC Target at 90,000",
    65000: "BTC Support at 65,000",
    # ADD MORE:
    # 100000: "BTC 1 Lakh Target",
    # 50000:  "BTC 50K Level",
}

TOLERANCE_PERCENT = 0.005   # 0.5% tolerance around each level
ALERTED_FILE      = "alerted_levels.json"   # stored in repo to avoid duplicate calls

# ============================================================
# LOAD already-alerted levels (from previous runs)
# ============================================================
def load_alerted():
    if os.path.exists(ALERTED_FILE):
        with open(ALERTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_alerted(alerted):
    with open(ALERTED_FILE, "w") as f:
        json.dump(list(alerted), f)

# ============================================================
# FETCH BTC PRICE from Binance (free, no API key)
# ============================================================
def get_btc_price():
    try:
        r = requests.get(
            "https://api.binance.com/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"},
            timeout=5
        )
        return float(r.json()["price"])
    except Exception as e:
        print(f"[ERROR] Price fetch failed: {e}")
        return None

# ============================================================
# MAKE VOICE CALL via Twilio
# ============================================================
def make_voice_call(label, price):
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

        speech = (
            f"Alert! Alert! Breakeven level reached. "
            f"{label}. "
            f"Current Bitcoin price is {int(price)} U S D T. "
            f"Please check your positions immediately. "
            f"This is JK Crypto Capital automated alert."
        )

        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice" language="en-IN" loop="3">{speech}</Say>
</Response>"""

        call = client.calls.create(
            twiml=twiml,
            to=YOUR_PHONE_NUMBER,
            from_=TWILIO_FROM_NUMBER
        )
        print(f"[CALL] ✅ Voice call triggered! SID: {call.sid}")
        return True
    except Exception as e:
        print(f"[ERROR] Call failed: {e}")
        return False

# ============================================================
# SEND TELEGRAM ALERT
# ============================================================
def send_telegram(label, price):
    try:
        msg = (
            f"🚨 *BREAKEVEN ALERT* 🚨\n"
            f"📍 {label}\n"
            f"💰 Price: ${price:,.2f}\n"
            f"🕐 Time: {datetime.now().strftime('%d-%b %H:%M:%S')} IST\n"
            f"📞 Voice call triggered to your mobile!"
        )
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5
        )
        print(f"[TELEGRAM] ✅ Alert sent.")
    except Exception as e:
        print(f"[ERROR] Telegram failed: {e}")

# ============================================================
# MAIN — single run (GitHub Actions calls this every 5 min)
# ============================================================
def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 🔍 Checking BTC price...")

    price = get_btc_price()
    if not price:
        print("[ABORT] Could not fetch price.")
        return

    print(f"[PRICE] BTC = ${price:,.2f}")

    alerted = load_alerted()

    triggered_any = False

    for level, label in BREAKEVEN_LEVELS.items():
        tolerance = level * TOLERANCE_PERCENT
        if (level - tolerance) <= price <= (level + tolerance):
            if level not in alerted:
                print(f"\n🔥 HIT: {label} @ ${price:,.2f}")
                send_telegram(label, price)
                make_voice_call(label, price)
                alerted.add(level)
                triggered_any = True
            else:
                print(f"[SKIP] ${level:,} already alerted previously.")

    if triggered_any:
        save_alerted(alerted)

    print("[DONE] Check complete.\n")

if __name__ == "__main__":
    main()
