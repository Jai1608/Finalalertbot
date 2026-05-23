import os
import requests
import json
from datetime import datetime
from twilio.rest import Client

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER")
YOUR_PHONE_NUMBER = os.getenv("YOUR_PHONE_NUMBER")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
LEVELS_FILE = "breakeven_levels.json"

def load_levels():
    if os.path.exists(LEVELS_FILE):
        try:
            with open(LEVELS_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def get_btc_price():
    apis = [
        ("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
         lambda r: r["bitcoin"]["usd"]),
        ("https://api.kraken.com/0/public/Ticker?pair=XBTUSD",
         lambda r: float(r["result"]["XXBTZUSD"]["c"][0])),
    ]
    for url, parser in apis:
        try:
            r = requests.get(url, timeout=5)
            price = parser(r.json())
            print(f"[PRICE] BTC = ${price:,.2f}")
            return float(price)
        except Exception as e:
            print(f"[WARN] API failed: {e}")
    print("[ERROR] All price APIs failed")
    return None

def send_telegram_message(text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        data = {"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}
        requests.post(url, data=data, timeout=5)
        print(f"[TELEGRAM] Message sent")
    except Exception as e:
        print(f"[ERROR] Telegram failed: {e}")

def make_voice_call(message):
    try:
        twiml = f''
        call = twilio_client.calls.create(
            to=YOUR_PHONE_NUMBER,
            from_=TWILIO_FROM_NUMBER,
            twiml=twiml
        )
        print(f"[TWILIO] Call made: {call.sid}")
        return True
    except Exception as e:
        print(f"[ERROR] Twilio failed: {e}")
        return False

def check_and_alert(current_price, levels):
    for level_str, description in levels.items():
        try:
            level = float(level_str)
            tolerance = level * 0.005
            if abs(current_price - level) <= tolerance:
                timestamp = datetime.now().strftime("%d-%b %H:%M:%S IST")
                telegram_msg = f"🚨 BREAKEVEN ALERT 🚨\n📍 Level: ${level:,.0f}\n💰 Price: ${current_price:,.2f}\n⏰ Time: {timestamp}\n📞 Voice call triggered!"
                voice_msg = f"Alert: BTC breakeven at {level} dollars. Current price is {current_price} dollars."
                send_telegram_message(telegram_msg)
                make_voice_call(voice_msg)
                print(f"[ALERT] Level {level} triggered at ${current_price}")
        except:
            pass

def main():
    print(f"[START] Checking breakeven levels...")
    btc_price = get_btc_price()
    if btc_price is None:
        print("[ERROR] Could not fetch BTC price")
        return
    levels = load_levels()
    if not levels:
        print("[INFO] No levels set")
        return
    print(f"[LEVELS] Watching {len(levels)} levels")
    check_and_alert(btc_price, levels)

if __name__ == "__main__":
    main()
