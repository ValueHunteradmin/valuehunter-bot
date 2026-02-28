import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import requests
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request, abort
import os
import hmac
import hashlib

# ================= CONFIG =================

TOKEN = "8767848071:AAHjxT7945VO-X7iCI3kG-0fIqC_giqX7Z8"
ADMIN_ID = 8328070177

FOOTBALL_API_KEY = "2f8c79b66ceed85aaf20322308f11e5a"
ODDS_API_KEY = "e55ba3ebd10f1d12494c0c10f1bfdb32"
NOWPAY_API_KEY = "ZB43Y23-F3E4XKG-K83X2GC-MPAAHZ5"
NOWPAY_IPN_SECRET = "c499iDAdX1fyUeQ+eahI77PsZ3Kg8gAe"

VIP_LIMIT = 150

WEBHOOK_URL = "https://valuehunter-bot-production.up.railway.app/payment-webhook"

bot = telebot.TeleBot(TOKEN, parse_mode="HTML")
app = Flask(__name__)

# ================= DATABASE =================

db = sqlite3.connect("vip.db", check_same_thread=False)
cursor = db.cursor()

cursor.execute("PRAGMA journal_mode=WAL")

cursor.execute("""
CREATE TABLE IF NOT EXISTS vip_users(
user_id INTEGER PRIMARY KEY,
plan TEXT,
expire INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS pending_payments(
user_id INTEGER PRIMARY KEY,
created INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS verified_payments(
user_id INTEGER PRIMARY KEY
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS sent_matches(
key TEXT PRIMARY KEY
)
""")

db.commit()
db_lock = threading.Lock()

# ================= SAFE SEND =================

def safe_send(uid, text):
    try:
        bot.send_message(uid, text)
    except:
        pass

# ================= VIP FUNCTIONS =================

def add_vip(user_id, plan, days):
    expire = int(time.time()) + days * 86400
    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO vip_users VALUES (?,?,?)",
                       (user_id, plan, expire))
        db.commit()

def vip_count():
    now = int(time.time())
    with db_lock:
        cursor.execute("SELECT COUNT(*) FROM vip_users WHERE expire > ?", (now,))
        return cursor.fetchone()[0]

# ================= PAYMENT =================

def create_payment(amount, user_id):

    if vip_count() >= VIP_LIMIT:
        return None

    with db_lock:
        cursor.execute("INSERT OR REPLACE INTO pending_payments VALUES (?,?)",
                       (user_id, int(time.time())))
        db.commit()

    url = "https://api.nowpayments.io/v1/invoice"
    headers = {
        "x-api-key": NOWPAY_API_KEY,
        "Content-Type": "application/json"
    }

    data = {
        "price_amount": amount,
        "price_currency": "eur",
        "order_id": str(user_id),
        "order_description": "ValueHunter VIP",
        "ipn_callback_url": WEBHOOK_URL
    }

    r = requests.post(url, json=data, headers=headers, timeout=20)

    return r.json().get("invoice_url")

# ================= WEBHOOK VERIFICATION =================

def verify_nowpayments_signature(request):
    signature = request.headers.get("x-nowpayments-sig")
    if not signature:
        return False

    body = request.data
    generated = hmac.new(
        NOWPAY_IPN_SECRET.encode(),
        body,
        hashlib.sha512
    ).hexdigest()

    return hmac.compare_digest(generated, signature)

# ================= PAYMENT WEBHOOK =================

@app.route('/payment-webhook', methods=['POST'])
def payment_webhook():

    if not verify_nowpayments_signature(request):
        abort(403)

    data = request.json
    status = data.get("payment_status")
    user_id = int(data.get("order_id", 0))
    amount = float(data.get("price_amount", 0))

    with db_lock:
        row = cursor.execute("SELECT created FROM pending_payments WHERE user_id=?", (user_id,)).fetchone()

    if not row:
        return "UNKNOWN ORDER"

    if time.time() - row[0] > 7200:
        return "EXPIRED ORDER"

    if status != "finished":
        return "IGNORED"

    with db_lock:
        if cursor.execute("SELECT 1 FROM verified_payments WHERE user_id=?", (user_id,)).fetchone():
            return "ALREADY VERIFIED"

        cursor.execute("INSERT INTO verified_payments VALUES (?)", (user_id,))
        cursor.execute("DELETE FROM pending_payments WHERE user_id=?", (user_id,))
        db.commit()

    if abs(amount - 50) < 1:
        add_vip(user_id, "BASIC", 30)
    elif abs(amount - 100) < 1:
        add_vip(user_id, "PRO", 30)
    elif abs(amount - 15) < 1:
        add_vip(user_id, "PRO", 1)
    else:
        return "UNKNOWN AMOUNT"

    safe_send(user_id,
        "👑 VIP ενεργοποιήθηκε!\nΤα bets θα αποστέλλονται καθημερινά.")

    return "OK"

# ================= AUTO BETS =================

def auto_bets():

    last_day = None

    while True:

        now = datetime.utcnow()

        if now.hour == 12 and last_day != now.day:

            with db_lock:
                users = cursor.execute(
                    "SELECT user_id, plan FROM vip_users WHERE expire > ?",
                    (int(time.time()),)
                ).fetchall()

            for uid, plan in users:

                key = f"{uid}-{now.day}"

                with db_lock:
                    if cursor.execute("SELECT 1 FROM sent_matches WHERE key=?", (key,)).fetchone():
                        continue
                    cursor.execute("INSERT INTO sent_matches VALUES (?)", (key,))
                    db.commit()

                safe_send(uid, "🔥 VIP BET σήμερα διαθέσιμο.")

            last_day = now.day

        time.sleep(60)

# ================= BUTTONS =================

@bot.callback_query_handler(func=lambda c: c.data == "vip")
def vip_menu(c):

    m = InlineKeyboardMarkup()

    m.add(InlineKeyboardButton("🥉 BASIC — 50€", callback_data="basic"))
    m.add(InlineKeyboardButton("🥇 PRO — 100€", callback_data="pro"))
    m.add(InlineKeyboardButton("⚡ DAY PASS — 15€", callback_data="day"))

    bot.send_message(c.message.chat.id,
                     "👑 VIP ΠΑΚΕΤΑ",
                     reply_markup=m)

@bot.callback_query_handler(func=lambda c: c.data in ["basic","pro","day"])
def buy(c):

    prices = {"basic":50, "pro":100, "day":15}

    link = create_payment(prices[c.data], c.message.chat.id)

    if not link:
        bot.send_message(c.message.chat.id,
                         "🚫 Οι VIP θέσεις έχουν καλυφθεί.")
        return

    bot.send_message(c.message.chat.id,
                     f"💳 Πλήρωσε εδώ:\n{link}")

# ================= MENU =================

def main_menu():
    m = InlineKeyboardMarkup(row_width=2)
    m.add(
        InlineKeyboardButton("💎 VIP", callback_data="vip"),
    )
    return m

@bot.message_handler(commands=['start'])
def start(msg):

    seats_left = VIP_LIMIT - vip_count()

    text = f"""🏛️ VALUEHUNTER ELITE

⚠️ Διαθέσιμες VIP θέσεις: {seats_left}/{VIP_LIMIT}
🔒 Πρόσβαση μόνο σε ενεργά μέλη."""

    bot.send_message(msg.chat.id, text, reply_markup=main_menu())

# ================= RUN =================

def run_web():
    port = int(os.environ.get("PORT", 8000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()
threading.Thread(target=auto_bets, daemon=True).start()

bot.infinity_polling()