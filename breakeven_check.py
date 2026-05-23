import os
import json
import requests
from datetime import datetime
from twilio.rest import Client

# ============================================================
# SECRETS FROM GITHUB
# ============================================================
TWILIO_ACCOUNT_SID = os.environ["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN  = os.environ["TWILIO_AUTH_TOKEN"]
TWILIO_FROM_NUMBER = os.environ["TWILIO_FROM_NUMBER"]
YOUR_PHONE_NUMBER  = os.environ["YOUR_PHONE_NUMBER"]
TELEGRAM_TOKEN     = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID   = os.environ["TELEGRAM_CHAT_ID"]
GITHUB_TOKEN       = os.environ["GITHUB_TOKEN"]
GITHUB_REPO        = os.environ["GITHUB_REPO"]

LEVELS_FILE  = "levels.json"
ALERTED_FILE = "alerted_levels.json"

def load_levels():
    if os.path.exists(LEVELS_FILE):
        with open(LEVELS_FILE, "r") as f:
            return json.load(f)
    return {}

def save_levels(levels):
    with open(LEVELS_FILE, "w") as f:
        json.dump(levels, f)

def load_alerted():
    if os.path.exists(ALERTED_FILE):
        with open(ALERTED_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_alerted(alerted):
    with open(ALERTED_FILE, "w") as f:
        json.dump(list(alerted), f)

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
            print(f"[PRICE] BTC = ${float(price):,.2f}")
            return float(price)
        except Exception as e:
            print(f"[WARN] API failed: {e}")
    print("[ERROR] All APIs failed.")
    return None

def send_telegram(msg):
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": msg, "parse_mode": "Markdown"},
            timeout=5
        )
        print("[TELEGRAM] Sent.")
    except Exception as e:
        print(f"[ERROR] Telegram: {e}")

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
        print(f"[CALL] Triggered! SID: {call.sid}")
    except Exception as e:
        print(f"[ERROR] Call: {e}")

def process_telegram_commands():
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
            params={"limit": 20, "timeout": 2},
            timeout=10
        )
        updates = r.json().get("result", [])
        levels  = load_levels()
        alerted = load_alerted()
        changed = False
        last_update_id = None

        for update in updates:
            last_update_id = update["update_id"]
            msg  = update.get("message", {})
            text = msg.get("text", "").strip()
            chat_id = str(msg.get("chat", {}).get("id", ""))

            if chat_id != TELEGRAM_CHAT_ID:
                continue

            print(f"[CMD] {text}")

            if text.lower().startswith("/addlevel"):
                parts = text.split()
                if len(parts) >= 2:
                    try:
                        price_val = int(float(parts[1]))
                        label = " ".join(parts[2:]) if len(parts) > 2 else f"Breakeven at {price_val:,}"
                        levels[str(price_val)] = label
                        changed = True
                        send_telegram(
                            f"✅ *Level Added!*\n"
                            f"📍 ${price_val:,} → {label}\n"
                            f"Total levels: {len(levels)}"
                        )
                    except:
                        send_telegram("❌ Use: `/addlevel 74000` or `/addlevel 74000 My Label`")

            elif text.lower().startswith("/removelevel"):
                parts = text.split()
                if len(parts) >= 2:
                    try:
                        price_val = str(int(float(parts[1])))
                        if price_val in levels:
                            lbl = levels.pop(price_val)
                            alerted.discard(int(price_val))
                            changed = True
                            send_telegram(f"🗑 *Removed:* ${int(price_val):,} → {lbl}")
                        else:
                            send_telegram(f"⚠️ ${price_val} not found.")
                    except:
                        send_telegram("❌ Use: `/removelevel 74000`")

            elif text.lower().startswith("/listlevels"):
                if levels:
                    lines = ["📋 *Active Breakeven Levels:*\n"]
                    for p, l in sorted(levels.items(), key=lambda x: int(x[0])):
                        status = "✅ alerted" if int(p) in alerted else "🔔 watching"
                        lines.append(f"• ${int(p):,} → {l} [{status}]")
                    send_telegram("\n".join(lines))
                else:
                    send_telegram("📋 No levels set.\nUse `/addlevel 74000` to add!")

            elif text.lower().startswith("/clearalerts"):
                alerted = set()
                changed = True
                send_telegram("🔄 *Alerts reset!* All levels will trigger again.")

            elif text.lower().startswith("/help") or text.lower().startswith("/start"):
                send_telegram(
                    "🤖 *JK Crypto Breakeven Alert Bot*\n\n"
                    "📌 *Commands:*\n"
                    "`/addlevel 74000` — Add level\n"
                    "`/addlevel 74000 Long SL` — Add with label\n"
                    "`/removelevel 74000` — Remove level\n"
                    "`/listlevels` — Show all levels\n"
                    "`/clearalerts` — Reset all alerts\n\n"
                    "📞 Voice call + Telegram when price hits!"
                )

        if changed:
            save_levels(levels)
            save_alerted(alerted)
            push_to_github(LEVELS_FILE, json.dumps(levels))
            push_to_github(ALERTED_FILE, json.dumps(list(alerted)))

        if last_update_id:
            requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": last_update_id + 1},
                timeout=5
            )

    except Exception as e:
        print(f"[ERROR] Commands: {e}")

def push_to_github(filepath, content):
    try:
        import base64
        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filepath}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}
        r = requests.get(api_url, headers=headers, timeout=5)
        sha = r.json().get("sha", "")
        encoded = base64.b64encode(content.encode()).decode()
        requests.put(api_url, headers=headers,
                     json={"message": f"Auto-update {filepath}", "content": encoded, "sha": sha},
                     timeout=10)
        print(f"[GITHUB] {filepath} updated.")
    except Exception as e:
        print(f"[ERROR] GitHub push: {e}")

def main():
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Running...")

    process_telegram_commands()

    levels  = load_levels()
    alerted = load_alerted()

    if not levels:
        print("[INFO] No levels set. Send /addlevel 74000 in Telegram!")
        return

    price = get_btc_price()
    if not price:
        return

    TOLERANCE = 200
    triggered = False

    for level_str, label in levels.items():
        level = int(level_str)
        if (level - TOLERANCE) <= price <= (level + TOLERANCE):
            if level not in alerted:
                print(f"HIT: {label} @ ${price:,.2f}")
                send_telegram(
                    f"🚨 *BREAKEVEN ALERT* 🚨\n"
                    f"📍 {label}\n"
                    f"💰 Price: ${price:,.2f}\n"
                    f"🕐 {datetime.now().strftime('%d-%b %H:%M:%S')} IST\n"
                    f"📞 Calling your mobile now!"
                )
                make_voice_call(label, price)
                alerted.add(level)
                triggered = True
            else:
                print(f"[SKIP] ${level:,} already alerted.")

    if triggered:
        save_alerted(alerted)
        push_to_github(ALERTED_FILE, json.dumps(list(alerted)))

    print("[DONE]\n")

if __name__ == "__main__":
    main()
